"""Generates the self-contained HTML demo dashboard from a pipeline run.

Runs the same spend_agent.pipeline used by the CLI, then renders the
results into dashboard/template.html (a static HTML/CSS/JS shell with a
few `__PLACEHOLDER__` markers) to produce a single self-contained HTML
file — fonts embedded as data URIs, data embedded as inline JSON, no
external requests at view time.

Usage:
    python3 dashboard/generate_dashboard.py \
        data/sample_transactions.csv \
        --taxonomy config/taxonomy.json \
        --suppliers config/preferred_suppliers.json \
        --aliases config/vendor_aliases.json \
        --out dashboard/spend_ledger_dashboard.html
"""

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spend_agent.pipeline import run_pipeline

DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))


def build_dashboard_data(results, clusters):
    rows = []
    for r in results:
        t = r.transaction
        rows.append(
            {
                "row_id": t.row_id,
                "date": t.date,
                "vendor_raw": t.vendor_raw,
                "canonical_vendor": r.canonical_vendor,
                "description": t.description,
                "amount": round(t.amount, 2),
                "category": r.category,
                "preferred_supplier": r.preferred_supplier,
                "bypassed": r.bypassed_preferred_supplier,
                "vendor_alias_count": r.vendor_alias_count,
                "llm_assisted": r.llm_assisted,
            }
        )

    alias_clusters = [
        {"canonical_name": c.canonical_name, "aliases": sorted(c.aliases)}
        for c in clusters.values()
        if len(c.aliases) > 1
    ]
    alias_clusters.sort(key=lambda c: -len(c["aliases"]))

    categories = {}
    for r in rows:
        bucket = categories.setdefault(r["category"], {"count": 0, "amount": 0.0})
        bucket["count"] += 1
        bucket["amount"] += r["amount"]

    summary = {
        "total_transactions": len(rows),
        "total_amount": round(sum(r["amount"] for r in rows), 2),
        "vendor_identities": len(clusters),
        "multi_alias_vendors": len(alias_clusters),
        "maverick_count": sum(1 for r in rows if r["bypassed"]),
        "maverick_amount": round(sum(r["amount"] for r in rows if r["bypassed"]), 2),
        "category_count": len(categories),
        "uncategorized_count": sum(1 for r in rows if r["category"] == "Uncategorized"),
    }

    return {"summary": summary, "rows": rows, "alias_clusters": alias_clusters, "categories": categories}


def render(data, source_label, out_path):
    template = open(os.path.join(DASHBOARD_DIR, "template.html"), encoding="utf-8").read()
    font_faces = open(os.path.join(DASHBOARD_DIR, "fonts", "font-faces.css"), encoding="utf-8").read()

    llm_used = any(r["llm_assisted"] for r in data["rows"])
    run_date = datetime.date.today().strftime("%b %-d, %Y")

    html = template.replace("__FONT_FACES__", font_faces)
    html = html.replace("__DASHBOARD_DATA__", json.dumps(data))
    html = html.replace("__SOURCE_LABEL__", source_label)
    html = html.replace("__ROW_COUNT__", str(data["summary"]["total_transactions"]))
    html = html.replace("__RUN_DATE__", run_date)
    html = html.replace(
        "__LLM_STATUS__",
        "used on this run" if llm_used else "not used on this run — all rows matched by keyword",
    )

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Path to the raw transaction CSV file")
    parser.add_argument("--taxonomy", default="config/taxonomy.json")
    parser.add_argument("--suppliers", default="config/preferred_suppliers.json")
    parser.add_argument("--aliases", default="config/vendor_aliases.json")
    parser.add_argument("--llm-fallback", action="store_true")
    parser.add_argument(
        "--out",
        default=os.path.join(DASHBOARD_DIR, "spend_ledger_dashboard.html"),
        help="Path to write the generated HTML dashboard to",
    )
    args = parser.parse_args(argv)

    results, clusters = run_pipeline(
        args.input, args.taxonomy, args.suppliers, args.aliases,
        use_llm_fallback=args.llm_fallback,
    )
    data = build_dashboard_data(results, clusters)
    render(data, source_label=args.input, out_path=args.out)

    print(f"Dashboard written to {args.out}")
    print(f"  {data['summary']['total_transactions']} transactions, "
          f"{data['summary']['vendor_identities']} vendor identities, "
          f"{data['summary']['maverick_count']} maverick-flagged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
