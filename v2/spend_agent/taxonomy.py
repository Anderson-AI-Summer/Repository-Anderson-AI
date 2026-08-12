"""Keyword-based spend taxonomy classification.

Rule-based rather than model-based on purpose: for a finance workflow,
an auditor needs to see exactly why a line was classified a certain way.
Rows that match nothing fall into "Uncategorized" for manual review rather
than being guessed at.
"""

import json
from typing import Dict, List, NamedTuple

UNCATEGORIZED = "Uncategorized"


class Category(NamedTuple):
    name: str
    keywords: List[str]


def load_taxonomy(path: str) -> List[Category]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return [
        Category(name=entry["name"], keywords=[kw.lower() for kw in entry["keywords"]])
        for entry in data["categories"]
    ]


def classify(vendor: str, description: str, taxonomy: List[Category]) -> str:
    text = f"{vendor} {description}".lower()
    for category in taxonomy:
        if any(keyword in text for keyword in category.keywords):
            return category.name
    return UNCATEGORIZED


def load_preferred_suppliers(path: str) -> Dict[str, str]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
