"""Optional LLM-based fallback classifier for rows the keyword-based
taxonomy classifier (`spend_agent.taxonomy`) leaves as "Uncategorized".

The base pipeline is rule-based by design (see `taxonomy.py`): an auditor
needs to see exactly why a line was classified a certain way, so unmatched
rows are left for manual review rather than guessed at. This module is an
opt-in extension of that same idea rather than a replacement for it — for
the minority of rows a fixed keyword list can't resolve (ambiguous vendor
names, terse descriptions, novel businesses), it asks Claude to pick the
best fit from the *same* taxonomy and records its reasoning alongside the
call, so the decision stays auditable even though it isn't a keyword match.

Nothing else in the package imports this module. It is only reached via
the `--llm-fallback` CLI flag, and it fails soft — returning `None` (same
as leaving the row Uncategorized) — whenever the `anthropic` package isn't
installed, no API key is configured, or the call itself fails for any
reason. The base package's "no third-party dependencies" claim in the
README stays true for anyone who doesn't opt in.
"""

import json
import os
from typing import List, NamedTuple, Optional

from spend_agent.taxonomy import Category, UNCATEGORIZED

MODEL = "claude-opus-5"


class LlmClassification(NamedTuple):
    category: str
    reasoning: str


def is_available() -> bool:
    """Whether the optional LLM fallback can actually run here."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def classify_with_llm(
    vendor: str,
    description: str,
    taxonomy: List[Category],
    client=None,
) -> Optional[LlmClassification]:
    """Ask Claude to pick a category for a row the keyword classifier missed.

    Returns an `LlmClassification` naming one of `taxonomy`'s categories (or
    UNCATEGORIZED if the model judges none genuinely fit) plus its stated
    reasoning, or `None` if the fallback can't run or the call failed —
    callers should treat `None` the same as leaving the row Uncategorized.
    """
    if client is None:
        try:
            import anthropic
        except ImportError:
            return None
        try:
            client = anthropic.Anthropic()
        except Exception:
            return None

    category_names = [c.name for c in taxonomy]
    allowed = category_names + [UNCATEGORIZED]

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=(
                "You are classifying a single business expense line into one "
                "spend category for an audit report. Pick the single "
                "best-fitting category from the provided list, based only on "
                "the vendor name and description given. If nothing genuinely "
                "fits, say so rather than guessing — an incorrect category is "
                f"worse than an honest '{UNCATEGORIZED}'."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Vendor: {vendor}\n"
                        f"Description: {description}\n\n"
                        "Categories:\n" + "\n".join(f"- {name}" for name in category_names)
                    ),
                }
            ],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "enum": allowed},
                            "reasoning": {"type": "string"},
                        },
                        "required": ["category", "reasoning"],
                        "additionalProperties": False,
                    },
                }
            },
        )
    except Exception:
        return None

    text = next((block.text for block in response.content if block.type == "text"), None)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None

    category = data.get("category")
    reasoning = data.get("reasoning", "")
    if category not in allowed:
        return None
    return LlmClassification(category=category, reasoning=reasoning)
