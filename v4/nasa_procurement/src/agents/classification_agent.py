"""Agent 2: Spend Classification Agent.

Only called for transactions the deterministic PSC/NAICS/keyword pass
(src/taxonomy.py) could not classify. Never one call per transaction across
the whole dataset -- only the ambiguous remainder, and identical
(psc, naics, description) combinations share a cache entry.
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field

from src.agents.base import AgentRunStats, call_claude, run_agent
from src.taxonomy import (
    NEEDS_REVIEW_SUBCATEGORY,
    UNCLASSIFIED_CATEGORY,
    load_taxonomy,
    taxonomy_version,
    validate_classification,
)

PROMPT_VERSION = "classification-agent-v1"


def _system_prompt() -> str:
    taxonomy = load_taxonomy()["categories"]
    cat_lines = []
    for cat, spec in taxonomy.items():
        subs = ", ".join(spec["subcategories"].keys())
        cat_lines.append(f"- {cat}: [{subs}]")
    catalog = "\n".join(cat_lines)
    return f"""You are a spend classifier for NASA prime-contract transactions. Classify the
transaction into exactly one category and one subcategory from this taxonomy (do not invent
new categories):

{catalog}

If the evidence is too weak or generic to confidently pick a specific category, respond with
category "{UNCLASSIFIED_CATEGORY}" and subcategory "{NEEDS_REVIEW_SUBCATEGORY}", and set
needs_review true. Never fabricate details not present in the evidence given.

Respond with ONLY a JSON object matching this schema, no other text:
{{"category": string, "subcategory": string, "confidence": float (0-1), "evidence": string (<=200 chars), "needs_review": bool}}
"""


class ClassificationOutput(BaseModel):
    category: str
    subcategory: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str
    needs_review: bool = False


def classify(
    psc_code: str | None,
    psc_description: str | None,
    naics_code: str | None,
    naics_description: str | None,
    description: str | None,
    stats: AgentRunStats,
) -> ClassificationOutput:
    key_payload = {
        "prompt_version": PROMPT_VERSION,
        "taxonomy_version": taxonomy_version(),
        "psc_code": psc_code,
        "naics_code": naics_code,
        "description": (description or "")[:300],
    }

    def live_fn() -> str:
        user = json.dumps({
            "psc_code": psc_code,
            "psc_description": psc_description,
            "naics_code": naics_code,
            "naics_description": naics_description,
            "transaction_description": description,
        })
        return call_claude(_system_prompt(), user, max_tokens=300)

    def fallback_fn() -> ClassificationOutput:
        return ClassificationOutput(
            category=UNCLASSIFIED_CATEGORY,
            subcategory=NEEDS_REVIEW_SUBCATEGORY,
            confidence=0.3,
            evidence="No confident deterministic PSC/NAICS/keyword match; no live agent available (DETERMINISTIC_FALLBACK mode)",
            needs_review=True,
        )

    result, _mode = run_agent(stats, "classification_agent", key_payload, ClassificationOutput, live_fn, fallback_fn)

    if not validate_classification(result.category, result.subcategory):
        result = ClassificationOutput(
            category=UNCLASSIFIED_CATEGORY,
            subcategory=NEEDS_REVIEW_SUBCATEGORY,
            confidence=min(result.confidence, 0.3),
            evidence=f"Agent output failed taxonomy validation ({result.category}/{result.subcategory}); routed to review",
            needs_review=True,
        )
    return result
