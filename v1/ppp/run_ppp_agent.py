"""Runs the spend agent against a raw SBA PPP loan CSV.

Converts the raw file (lender-as-vendor, NAICS-as-category) into the generic
transaction schema, then reuses spend_agent's existing pipeline and reports
unchanged. No preferred-lender policy is asserted (config/ppp_preferred_lenders.json
is empty) since that would imply a real compliance judgment about named
businesses; the "bypassed preferred supplier" flag is left available for
whoever supplies an actual policy to fill in.

Usage:
    python3 ppp/run_ppp_agent.py ppp/data/wyoming_ppp_sample.csv --outdir ppp/out
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spend_agent.pipeline import run_pipeline
from spend_agent.ppp_adapter import convert_ppp_csv
from spend_agent.report import write_all_reports


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Path to a raw SBA PPP FOIA CSV")
    parser.add_argument("--outdir", default="ppp/out", help="Directory to write reports to")
    args = parser.parse_args(argv)

    os.makedirs(args.outdir, exist_ok=True)
    transactions_path = os.path.join(args.outdir, "converted_transactions.csv")
    row_count = convert_ppp_csv(args.input, transactions_path)
    print(f"Converted {row_count} PPP loan records to transaction schema.")

    results, clusters = run_pipeline(
        transactions_path,
        "config/ppp_taxonomy.json",
        "config/ppp_preferred_lenders.json",
        "config/vendor_aliases.json",
    )
    paths = write_all_reports(args.outdir, results, clusters)

    multi_alias = sum(1 for c in clusters.values() if len(c.aliases) > 1)
    print(f"Processed {len(results)} loans.")
    print(f"Lenders resolved into {len(clusters)} identities ({multi_alias} with multiple aliases).")
    print("Reports written to:")
    for label, path in paths.items():
        print(f"  {label}: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
