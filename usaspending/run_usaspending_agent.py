"""Runs the spend agent against a raw USASpending.gov contract award CSV.

Converts the raw file (recipient-as-vendor, PSC/NAICS-as-category) into the
generic transaction schema, then reuses spend_agent's existing pipeline and
reports unchanged. Accepts either a "Custom Award Data" bulk download from
usaspending.gov/download_center or a CSV export of the Award Search API's
`spending_by_award` results — see spend_agent/usaspending_adapter.py for the
exact columns recognized.

No preferred-supplier policy is asserted by default
(config/usaspending_preferred_suppliers.json is empty) for the same reason
ppp/ ships no preferred-lender policy: asserting one against real award data
without an actual agency policy to check against would misrepresent the
output as a compliance finding. usaspending/data/sample_preferred_suppliers.json
is a fictional, clearly-labeled illustrative policy for the bundled synthetic
sample only (usaspending/data/sample_contracts.csv) — do not point it at
real award data.

Usage:
    python3 usaspending/run_usaspending_agent.py usaspending/data/sample_contracts.csv \
        --suppliers usaspending/data/sample_preferred_suppliers.json \
        --outdir usaspending/out

    # Against a real usaspending.gov download, with no supplier policy asserted:
    python3 usaspending/run_usaspending_agent.py path/to/usaspending_export.csv --outdir usaspending/out
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spend_agent.pipeline import run_pipeline
from spend_agent.usaspending_adapter import convert_usaspending_csv
from spend_agent.report import write_all_reports


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", help="Path to a raw USASpending.gov award CSV")
    parser.add_argument(
        "--taxonomy", default="config/usaspending_taxonomy.json",
        help="Path to category taxonomy (default: config/usaspending_taxonomy.json)",
    )
    parser.add_argument(
        "--suppliers", default="config/usaspending_preferred_suppliers.json",
        help="Path to preferred-supplier policy (default: empty, config/usaspending_preferred_suppliers.json)",
    )
    parser.add_argument(
        "--aliases", default="config/vendor_aliases.json",
        help="Path to known vendor-abbreviation seed table (default: config/vendor_aliases.json)",
    )
    parser.add_argument("--outdir", default="usaspending/out", help="Directory to write reports to")
    args = parser.parse_args(argv)

    os.makedirs(args.outdir, exist_ok=True)
    transactions_path = os.path.join(args.outdir, "converted_transactions.csv")
    row_count = convert_usaspending_csv(args.input, transactions_path)
    print(f"Converted {row_count} USASpending.gov award records to transaction schema.")

    results, clusters = run_pipeline(
        transactions_path,
        args.taxonomy,
        args.suppliers,
        args.aliases,
    )
    paths = write_all_reports(args.outdir, results, clusters)

    multi_alias = sum(1 for c in clusters.values() if len(c.aliases) > 1)
    print(f"Processed {len(results)} award records.")
    print(f"Recipients resolved into {len(clusters)} identities ({multi_alias} with multiple aliases).")
    print("Reports written to:")
    for label, path in paths.items():
        print(f"  {label}: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
