"""Scores raw SBA PPP loan records with the heuristic risk-indicator model
in spend_agent/ppp_risk_score.py and writes a CSV + summary.

This is NOT a fraud determination — see spend_agent/ppp_risk_score.py's
module docstring for what each indicator means and does not mean. Loans
under $150K carry no borrower name in the public data, so nothing here
identifies or accuses a specific business; patterns are at the
lender/date/amount/NAICS level only.

Usage:
    python3 ppp/run_ppp_risk_score.py <raw_ppp_csv> --outdir ppp/out
"""

import argparse
import csv
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spend_agent.ppp_risk_score import INDICATORS, MAX_SCORE, score_loans
from spend_agent.vendor_resolution import build_vendor_registry, load_vendor_aliases


def _naics_category_map(taxonomy_path: str) -> dict:
    with open(taxonomy_path, encoding="utf-8") as fh:
        data = json.load(fh)
    prefix_to_category = {}
    for entry in data["categories"]:
        for kw in entry["keywords"]:
            prefix = kw.replace("naics ", "").strip()
            prefix_to_category[prefix] = entry["name"]
    return prefix_to_category


def load_raw_loans(path: str) -> list:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Path to a raw SBA PPP FOIA CSV (under-$150K tier)")
    parser.add_argument("--outdir", default="ppp/out", help="Directory to write output to")
    args = parser.parse_args(argv)

    os.makedirs(args.outdir, exist_ok=True)

    raw_rows = load_raw_loans(args.input)
    prefix_to_category = _naics_category_map("config/ppp_taxonomy.json")
    aliases = load_vendor_aliases("config/vendor_aliases.json")
    raw_to_cluster_id, clusters = build_vendor_registry(
        (r["Lender"].strip() for r in raw_rows if r.get("Lender")), aliases
    )

    loans = []
    skipped = 0
    for r in raw_rows:
        lender_raw = (r.get("Lender") or "").strip()
        amount_raw = (r.get("LoanAmount") or "").strip()
        if not lender_raw or not amount_raw:
            skipped += 1
            continue
        naics = (r.get("NAICSCode") or "").strip()
        category = prefix_to_category.get(naics[:2], "Uncategorized")
        jobs_raw = (r.get("JobsRetained") or "").strip()
        jobs_retained = float(jobs_raw) if jobs_raw else None
        cluster = clusters[raw_to_cluster_id[lender_raw]]
        loans.append(
            {
                "date": (r.get("DateApproved") or "").strip(),
                "lender_raw": lender_raw,
                "lender": cluster.canonical_name,
                "city": (r.get("City") or "").strip(),
                "naics": naics,
                "category": category,
                "jobs_retained": jobs_retained,
                "amount": float(amount_raw),
            }
        )

    results = score_loans(loans)

    out_path = os.path.join(args.outdir, "risk_scored_loans.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["date", "lender", "city", "naics", "category", "jobs_retained", "amount",
             "risk_score", "risk_tier", "risk_flags"]
        )
        for loan, res in zip(loans, results):
            writer.writerow(
                [
                    loan["date"], loan["lender"], loan["city"], loan["naics"], loan["category"],
                    loan["jobs_retained"] if loan["jobs_retained"] is not None else "",
                    f'{loan["amount"]:.2f}', res.score, res.tier, ";".join(res.flags),
                ]
            )

    tier_counts = Counter(res.tier for res in results)
    flag_counts = Counter(f for res in results for f in res.flags)
    avg_score = sum(res.score for res in results) / len(results) if results else 0

    print(f"Scored {len(loans)} loans ({skipped} skipped for missing lender/amount).")
    print(f"Max possible score: {MAX_SCORE}. Average score: {avg_score:.1f}.")
    print("Tier distribution:")
    for tier in ["Very High", "High", "Elevated", "Low"]:
        print(f"  {tier}: {tier_counts.get(tier, 0)}")
    print("Indicator trigger counts:")
    for name in INDICATORS:
        print(f"  {name}: {flag_counts.get(name, 0)}")
    print(f"Output written to: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
