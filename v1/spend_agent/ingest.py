"""Tolerant ingestion of messy transaction files.

Real-world exports rarely agree on column names, so headers are matched
against a set of known aliases (case-insensitive, punctuation-insensitive)
rather than requiring an exact schema.
"""

import csv
import re
from typing import Dict, List, Optional

from spend_agent.models import Transaction

_HEADER_ALIASES = {
    "date": {"date", "transaction date", "txn date", "posted date", "trans date"},
    "vendor": {"vendor", "merchant", "payee", "supplier", "merchant name", "vendor name"},
    "description": {"description", "memo", "details", "notes", "line item"},
    "amount": {"amount", "total", "amt", "cost", "price", "charge"},
}


def _clean_header(header: str) -> str:
    return re.sub(r"[^a-z ]", "", header.strip().lower())


def _map_headers(fieldnames: List[str]) -> Dict[str, str]:
    """Return {canonical_field: original_header} for the fields we recognize."""
    mapping: Dict[str, str] = {}
    for original in fieldnames:
        cleaned = _clean_header(original)
        for canonical, aliases in _HEADER_ALIASES.items():
            if cleaned in aliases and canonical not in mapping:
                mapping[canonical] = original
    missing = set(_HEADER_ALIASES) - set(mapping)
    if missing:
        raise ValueError(
            f"Could not find columns for: {sorted(missing)}. "
            f"Available headers: {fieldnames}"
        )
    return mapping


def _parse_amount(raw_amount: str) -> float:
    cleaned = raw_amount.strip()
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    if not cleaned:
        return 0.0
    value = float(cleaned)
    return -value if negative else value


def load_transactions(path: str) -> List[Transaction]:
    """Parse a messy transaction CSV into a list of normalized Transaction rows.

    Blank rows and rows missing a vendor or amount are skipped rather than
    raising, since real exports commonly contain stray blank lines.
    """
    transactions: List[Transaction] = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            return transactions
        header_map = _map_headers(reader.fieldnames)

        for row_id, row in enumerate(reader, start=1):
            vendor = (row.get(header_map["vendor"]) or "").strip()
            amount_raw = (row.get(header_map["amount"]) or "").strip()
            if not vendor or not amount_raw:
                continue
            transactions.append(
                Transaction(
                    row_id=row_id,
                    date=(row.get(header_map["date"]) or "").strip(),
                    vendor_raw=vendor,
                    description=(row.get(header_map["description"]) or "").strip(),
                    amount=_parse_amount(amount_raw),
                    raw=dict(row),
                )
            )
    return transactions
