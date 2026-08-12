"""Generates the multi-dataset spend visualizer from three real pipeline runs.

Unlike generate_dashboard.py (one dataset -> one static table-heavy page),
this renders category/maverick-spend bar charts and a vendor-alias ledger
for three datasets at once (the corporate sample, and the synthetic NASA
and HUD USASpending.gov demos) into one page with a dataset switcher, from
dashboard/visualizer_template.html (a static HTML/CSS/JS shell with one
`__VIZ_DATA__` marker). Every number embedded is a live run of
spend_agent.pipeline.run_pipeline against the checked-in sample data — none
of it is hand-edited.

Usage:
    python3 dashboard/generate_visualizer.py --out dashboard/spend_visualizer.html
"""

import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spend_agent.pipeline import run_pipeline
from spend_agent.usaspending_adapter import convert_usaspending_csv
from spend_agent.taxonomy import UNCATEGORIZED

DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))


def summarize(results, clusters, label, source, note):
    category_totals = {}
    maverick_by_category = {}
    for r in results:
        amt = r.transaction.amount
        c = category_totals.setdefault(r.category, {"category": r.category, "amount": 0.0, "count": 0})
        c["amount"] += amt
        c["count"] += 1
        if r.bypassed_preferred_supplier:
            m = maverick_by_category.setdefault(
                r.category, {"category": r.category, "amount": 0.0, "count": 0}
            )
            m["amount"] += amt
            m["count"] += 1

    category_list = sorted(category_totals.values(), key=lambda x: -x["amount"])
    maverick_list = sorted(maverick_by_category.values(), key=lambda x: -x["amount"])
    for x in category_list:
        x["amount"] = round(x["amount"], 2)
    for x in maverick_list:
        x["amount"] = round(x["amount"], 2)

    alias_clusters = sorted(
        [
            {"canonical_name": c.canonical_name, "aliases": sorted(c.aliases)}
            for c in clusters.values()
            if len(c.aliases) > 1
        ],
        key=lambda x: -len(x["aliases"]),
    )

    maverick_rows = sorted(
        [
            {
                "vendor": r.canonical_vendor,
                "category": r.category,
                "preferred_supplier": r.preferred_supplier,
                "amount": round(r.transaction.amount, 2),
                "date": r.transaction.date,
            }
            for r in results
            if r.bypassed_preferred_supplier
        ],
        key=lambda x: -x["amount"],
    )

    return {
        "label": label,
        "source": source,
        "note": note,
        "summary": {
            "total_transactions": len(results),
            "total_amount": round(sum(r.transaction.amount for r in results), 2),
            "vendor_identities": len(clusters),
            "multi_alias_vendors": len(alias_clusters),
            "maverick_count": sum(1 for r in results if r.bypassed_preferred_supplier),
            "maverick_amount": round(
                sum(r.transaction.amount for r in results if r.bypassed_preferred_supplier), 2
            ),
            "uncategorized_count": sum(1 for r in results if r.category == UNCATEGORIZED),
        },
        "category_totals": category_list,
        "maverick_by_category": maverick_list,
        "maverick_rows": maverick_rows,
        "alias_clusters": alias_clusters,
    }


def build_data():
    datasets = {}

    results, clusters = run_pipeline(
        "data/sample_transactions.csv",
        "config/taxonomy.json",
        "config/preferred_suppliers.json",
        "config/vendor_aliases.json",
    )
    datasets["corporate"] = summarize(
        results, clusters, "Corporate Expense Sample",
        "data/sample_transactions.csv",
        "Illustrative synthetic transaction export (23 rows).",
    )

    usaspending_note = (
        "Synthetic demo, not a live USASpending.gov pull — network access to "
        "usaspending.gov is blocked in this environment. Fictional contractor names."
    )

    tmp = tempfile.mktemp(suffix=".csv")
    convert_usaspending_csv("usaspending/data/sample_nasa_contracts.csv", tmp)
    results, clusters = run_pipeline(
        tmp, "config/usaspending_taxonomy.json",
        "usaspending/data/sample_preferred_suppliers.json", "config/vendor_aliases.json",
    )
    datasets["nasa"] = summarize(
        results, clusters, "NASA", "usaspending/data/sample_nasa_contracts.csv", usaspending_note,
    )

    tmp2 = tempfile.mktemp(suffix=".csv")
    convert_usaspending_csv("usaspending/data/sample_hud_contracts.csv", tmp2)
    results, clusters = run_pipeline(
        tmp2, "config/usaspending_taxonomy.json",
        "usaspending/data/sample_hud_preferred_suppliers.json", "config/vendor_aliases.json",
    )
    datasets["hud"] = summarize(
        results, clusters, "HUD", "usaspending/data/sample_hud_contracts.csv", usaspending_note,
    )

    return datasets


def render(data, out_path):
    template = open(os.path.join(DASHBOARD_DIR, "visualizer_template.html"), encoding="utf-8").read()
    html = template.replace("__VIZ_DATA__", json.dumps(data))
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=os.path.join(DASHBOARD_DIR, "spend_visualizer.html"),
        help="Path to write the generated HTML visualizer to",
    )
    args = parser.parse_args(argv)

    data = build_data()
    render(data, args.out)

    print(f"Visualizer written to {args.out}")
    for key, d in data.items():
        s = d["summary"]
        print(
            f"  {key}: {s['total_transactions']} txns, {s['vendor_identities']} vendor identities "
            f"({s['multi_alias_vendors']} multi-alias), {s['maverick_count']} maverick-flagged"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
