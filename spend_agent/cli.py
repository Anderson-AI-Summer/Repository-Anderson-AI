"""CLI entry point for the spend classification agent."""

import argparse
import sys

from spend_agent.pipeline import run_pipeline
from spend_agent.report import write_all_reports


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Classify a messy transaction file into a spend taxonomy, "
            "resolve vendor name variants, and flag maverick spend."
        )
    )
    parser.add_argument("input", help="Path to the raw transaction CSV file")
    parser.add_argument(
        "--taxonomy", default="config/taxonomy.json", help="Path to taxonomy config"
    )
    parser.add_argument(
        "--suppliers",
        default="config/preferred_suppliers.json",
        help="Path to preferred-supplier config",
    )
    parser.add_argument(
        "--aliases",
        default="config/vendor_aliases.json",
        help="Path to known vendor-abbreviation alias config",
    )
    parser.add_argument("--outdir", default="out", help="Directory to write reports to")
    args = parser.parse_args(argv)

    results, clusters = run_pipeline(args.input, args.taxonomy, args.suppliers, args.aliases)
    paths = write_all_reports(args.outdir, results, clusters)

    multi_alias = sum(1 for c in clusters.values() if len(c.aliases) > 1)
    flagged = sum(1 for r in results if r.bypassed_preferred_supplier)

    print(f"Processed {len(results)} transactions.")
    print(f"Vendors resolved into {len(clusters)} identities ({multi_alias} with multiple aliases).")
    print(f"Flagged {flagged} maverick-spend transaction(s).")
    print("Reports written to:")
    for label, path in paths.items():
        print(f"  {label}: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
