"""Adapts raw SBA PPP loan CSVs into the generic Date/Vendor/Description/Amount
schema the rest of spend_agent already knows how to ingest.

The lender is treated as the "vendor" (so vendor_resolution can catch lender
name variants), and the NAICS code is embedded in the description so the
keyword taxonomy classifier (config/ppp_taxonomy.json) can route each loan
to an industry sector by matching on the "naics <2-digit prefix>" substring.

Handles both public PPP FOIA file variants: the under-$150K files (numeric
"LoanAmount" column, no borrower name) and the $150K+ file (bucketed
"LoanRange" column, e.g. "e $150,000-350,000", plus "BusinessName").
"""

import csv
import re
from typing import Optional


def _parse_amount(row: dict) -> Optional[float]:
    if row.get("LoanAmount"):
        try:
            return float(row["LoanAmount"].replace(",", "").strip())
        except ValueError:
            return None

    loan_range = row.get("LoanRange", "")
    numbers = re.findall(r"[\d,]+(?:\.\d+)?", loan_range)
    if not numbers:
        return None
    lower_bound = float(numbers[0].replace(",", ""))
    if "million" in loan_range.lower():
        lower_bound *= 1_000_000
    return lower_bound


def convert_ppp_csv(input_path: str, output_path: str) -> int:
    """Convert a raw PPP FOIA CSV to the generic transaction schema.

    Returns the number of rows written.
    """
    written = 0
    with open(input_path, newline="", encoding="utf-8-sig") as fin, open(
        output_path, "w", newline="", encoding="utf-8"
    ) as fout:
        reader = csv.DictReader(fin)
        writer = csv.writer(fout)
        writer.writerow(["Date", "Vendor", "Description", "Amount"])

        for row in reader:
            vendor = (row.get("Lender") or "").strip()
            amount = _parse_amount(row)
            if not vendor or not amount:
                continue

            naics = (row.get("NAICSCode") or "").strip()
            business_type = (row.get("BusinessType") or "").strip()
            business_name = (row.get("BusinessName") or "").strip()

            description_parts = [p for p in [business_name, f"naics {naics}", business_type] if p]
            description = " - ".join(description_parts)

            writer.writerow(
                [
                    (row.get("DateApproved") or "").strip(),
                    vendor,
                    description,
                    f"{amount:.2f}",
                ]
            )
            written += 1

    return written
