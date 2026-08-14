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
    parser.add_argument(
        "--llm-fallback",
        action="store_true",
        help=(
            "Ask Claude to classify rows the keyword taxonomy leaves Uncategorized "
            "(requires the `anthropic` package and an ANTHROPIC_API_KEY). Optional; "
            "the base pipeline is fully rule-based without it."
        ),
    )
    args = parser.parse_args(argv)

    if args.llm_fallback:
        from spend_agent.llm_classifier import is_available

        if not is_available():
            print(
                "--llm-fallback requested but unavailable (install `anthropic` and set "
                "ANTHROPIC_API_KEY); continuing without it.",
                file=sys.stderr,
            )

    results, clusters = run_pipeline(
        args.input, args.taxonomy, args.suppliers, args.aliases,
        use_llm_fallback=args.llm_fallback,
    )
    paths = write_all_reports(args.outdir, results, clusters)

    multi_alias = sum(1 for c in clusters.values() if len(c.aliases) > 1)
    flagged = sum(1 for r in results if r.bypassed_preferred_supplier)
    llm_assisted = sum(1 for r in results if r.llm_assisted)

    print(f"Processed {len(results)} transactions.")
    print(f"Vendors resolved into {len(clusters)} identities ({multi_alias} with multiple aliases).")
    print(f"Flagged {flagged} maverick-spend transaction(s).")
    if args.llm_fallback:
        print(f"LLM fallback classified {llm_assisted} previously-Uncategorized transaction(s).")
    print("Reports written to:")
    for label, path in paths.items():
        print(f"  {label}: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
