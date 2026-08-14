"""Adapts raw USASpending.gov contract award exports into the generic
Date/Vendor/Description/Amount schema the rest of spend_agent already knows
how to ingest.

USASpending.gov data reaches people through two differently-shaped exports,
so header matching here is tolerant (same approach as `spend_agent.ingest`)
rather than requiring one exact column set:

- **Custom Award Data** bulk CSV downloads (usaspending.gov/download_center),
  which use snake_case columns from the agency's data dictionary, e.g.
  `recipient_name`, `federal_action_obligation`, `naics_description`,
  `product_or_service_code_description`.
- The **Award Search API** (`/api/v2/search/spending_by_award/`), whose
  `fields` come back Title Case, e.g. `Recipient Name`, `Award Amount`,
  `NAICS Description`.

The recipient is treated as the "vendor" (so vendor_resolution can catch the
same contractor appearing under legal-name variants across awards), and the
award's NAICS/PSC/agency descriptions are concatenated into the description
field so the keyword taxonomy classifier (config/usaspending_taxonomy.json)
has real text to match against — federal procurement is categorized by
Product/Service Code and NAICS, not by a free-text memo line, so there's no
single field to lean on the way a bank memo works for `ingest.py`.
"""

import csv
import re
from typing import Dict, List, Optional

_HEADER_ALIASES = {
    "vendor": {
        "recipient name", "recipientname", "recipient",
        "awardeerecipient legal entity name",
    },
    "amount": {
        "federal action obligation", "federalactionobligation",
        "award amount", "awardamount",
        "total dollars obligated", "totaldollarsobligated",
        "current total value of award",
    },
    "date": {
        "action date", "actiondate", "start date", "startdate",
        "period of performance start date",
    },
    "agency": {
        "awarding agency name", "awardingagencyname", "awarding agency",
        "awarding sub agency name", "awarding sub agency",
    },
    "naics_description": {
        "naics description", "naicsdescription",
    },
    "psc_description": {
        "product or service code description",
        "productorservicecodedescription", "psc description",
    },
    "award_description": {
        "award description", "awarddescription", "description",
    },
}


def _clean_header(header: str) -> str:
    return re.sub(r"[^a-z]", "", header.strip().lower())


def _map_headers(fieldnames: List[str]) -> Dict[str, str]:
    """Return {canonical_field: original_header} for the fields we recognize.

    Unlike `ingest._map_headers`, only "vendor" and "amount" are required —
    the description-building fields are each optional since real exports
    vary in which of NAICS/PSC/free-text description columns they include.
    """
    mapping: Dict[str, str] = {}
    for original in fieldnames:
        cleaned = _clean_header(original)
        for canonical, aliases in _HEADER_ALIASES.items():
            normalized_aliases = {_clean_header(a) for a in aliases}
            if cleaned in normalized_aliases and canonical not in mapping:
                mapping[canonical] = original

    required = {"vendor", "amount"}
    missing = required - set(mapping)
    if missing:
        raise ValueError(
            f"Could not find columns for: {sorted(missing)}. "
            f"Available headers: {fieldnames}"
        )
    return mapping


def _parse_amount(raw_amount: str) -> Optional[float]:
    cleaned = raw_amount.strip()
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    if not cleaned or cleaned in {"-", "."}:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return -value if negative else value


def convert_usaspending_csv(input_path: str, output_path: str) -> int:
    """Convert a raw USASpending.gov award CSV to the generic transaction schema.

    Returns the number of rows written. Rows with no recipient name or no
    parseable award amount are skipped, same tolerance-over-strictness
    stance as `ingest.load_transactions` and `ppp_adapter.convert_ppp_csv`.
    """
    written = 0
    with open(input_path, newline="", encoding="utf-8-sig") as fin:
        reader = csv.DictReader(fin)
        if not reader.fieldnames:
            return 0
        header_map = _map_headers(reader.fieldnames)

        with open(output_path, "w", newline="", encoding="utf-8") as fout:
            writer = csv.writer(fout)
            writer.writerow(["Date", "Vendor", "Description", "Amount"])

            for row in reader:
                vendor = (row.get(header_map["vendor"]) or "").strip()
                amount = _parse_amount((row.get(header_map["amount"]) or ""))
                if not vendor or amount is None:
                    continue

                description_parts = [
                    (row.get(header_map[field]) or "").strip()
                    for field in ("psc_description", "naics_description", "award_description", "agency")
                    if field in header_map
                ]
                description = " - ".join(p for p in description_parts if p)

                writer.writerow(
                    [
                        (row.get(header_map["date"]) or "").strip() if "date" in header_map else "",
                        vendor,
                        description,
                        f"{amount:.2f}",
                    ]
                )
                written += 1

    return written
