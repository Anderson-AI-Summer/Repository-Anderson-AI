"""Deterministic PSC/NAICS/keyword-based spend classification.

Evidence order (per spec): PSC code/description, then NAICS code/description,
then transaction description keywords, then other structured fields. Signals
are scoped per-*subcategory* (not just per-category) so a match maps to the
specific subcategory it is evidence for. A record that matches nothing
deterministic is left "Other or Unclassified" / "Needs Review" rather than
guessed -- ambiguous records are the classification agent's job
(src/agents/classification_agent.py).
"""
from __future__ import annotations

import json
from functools import lru_cache

from src.config import TAXONOMY_VERSION_PATH

UNCLASSIFIED_CATEGORY = "Other or Unclassified"
UNCLASSIFIED_SUBCATEGORY = "Unclassified Spend"
NEEDS_REVIEW_SUBCATEGORY = "Needs Review — Ambiguous Evidence"


@lru_cache(maxsize=1)
def load_taxonomy() -> dict:
    with open(TAXONOMY_VERSION_PATH) as f:
        return json.load(f)


def taxonomy_version() -> str:
    return load_taxonomy()["version"]


def valid_categories() -> set[str]:
    return set(load_taxonomy()["categories"].keys())


def valid_subcategories(category: str) -> set[str]:
    cats = load_taxonomy()["categories"]
    return set(cats.get(category, {}).get("subcategories", {}).keys())


def validate_classification(category: str, subcategory: str) -> bool:
    if category not in valid_categories():
        return False
    return subcategory in valid_subcategories(category)


def _iter_subcategories(taxonomy: dict):
    for cat, spec in taxonomy.items():
        for sub, sub_spec in spec.get("subcategories", {}).items():
            yield cat, sub, sub_spec


def classify_deterministic(
    psc_code: str | None,
    psc_description: str | None,
    naics_code: str | None,
    naics_description: str | None,
    description: str | None,
) -> tuple[str, str, float, str] | None:
    """Return (category, subcategory, confidence, evidence) or None if no
    deterministic rule matched (caller should route to agent / Needs Review).
    """
    taxonomy = load_taxonomy()["categories"]

    # 1. PSC code prefix match (longest prefix wins, scoped per subcategory)
    if psc_code:
        code = psc_code.upper()
        best: tuple[str, str, str] | None = None
        best_len = 0
        for cat, sub, spec in _iter_subcategories(taxonomy):
            for prefix in spec.get("psc_prefixes", []):
                if code.startswith(prefix.upper()) and len(prefix) > best_len:
                    best = (cat, sub, prefix)
                    best_len = len(prefix)
        if best:
            cat, sub, prefix = best
            return cat, sub, 0.9, f"PSC code {psc_code} matches prefix '{prefix}' ({sub})"

    # 2. NAICS code exact match
    if naics_code:
        for cat, sub, spec in _iter_subcategories(taxonomy):
            if naics_code in spec.get("naics_codes", []):
                return cat, sub, 0.85, f"NAICS code {naics_code} ({naics_description or ''}) matches {sub}"

    # 3. Keyword match on descriptions (PSC desc, NAICS desc, transaction desc)
    haystack = " ".join(filter(None, [psc_description, naics_description, description])).lower()
    if haystack:
        for cat, sub, spec in _iter_subcategories(taxonomy):
            for kw in spec.get("keywords", []):
                if kw in haystack:
                    return cat, sub, 0.6, f"description keyword '{kw}' matched {sub}"

    return None
