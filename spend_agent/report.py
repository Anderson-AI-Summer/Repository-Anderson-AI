"""Renders pipeline output as CSV/Markdown reports."""

import csv
import os
from collections import defaultdict
from typing import Dict, List

from spend_agent.models import ClassifiedTransaction
from spend_agent.vendor_resolution import VendorCluster


def write_classified_csv(path: str, results: List[ClassifiedTransaction]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "row_id", "date", "vendor_raw", "canonical_vendor", "description",
                "amount", "category", "preferred_supplier", "bypassed_preferred_supplier",
            ]
        )
        for r in results:
            t = r.transaction
            writer.writerow(
                [
                    t.row_id, t.date, t.vendor_raw, r.canonical_vendor, t.description,
                    f"{t.amount:.2f}", r.category, r.preferred_supplier or "",
                    "yes" if r.bypassed_preferred_supplier else "no",
                ]
            )


def write_vendor_alias_report(path: str, clusters: Dict[int, VendorCluster]) -> None:
    multi_alias = [c for c in clusters.values() if len(c.aliases) > 1]
    multi_alias.sort(key=lambda c: -len(c.aliases))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Vendor Alias Report\n\n")
        if not multi_alias:
            fh.write("No vendors with multiple name variants were detected.\n")
            return
        fh.write(
            f"Detected {len(multi_alias)} vendor(s) appearing under multiple names.\n\n"
        )
        for cluster in multi_alias:
            fh.write(f"## {cluster.canonical_name} ({len(cluster.aliases)} aliases)\n")
            for alias in cluster.aliases:
                fh.write(f"- {alias}\n")
            fh.write("\n")


def write_maverick_report(path: str, results: List[ClassifiedTransaction]) -> None:
    flagged = [r for r in results if r.bypassed_preferred_supplier]
    flagged.sort(key=lambda r: -r.transaction.amount)
    total = sum(r.transaction.amount for r in flagged)

    by_category: Dict[str, float] = defaultdict(float)
    for r in flagged:
        by_category[r.category] += r.transaction.amount

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Maverick Spend Report\n\n")
        fh.write("Purchases in categories with a designated preferred supplier, ")
        fh.write("routed to a different vendor instead.\n\n")
        if not flagged:
            fh.write("No maverick spend detected.\n")
            return
        fh.write(f"**Total flagged: ${total:,.2f} across {len(flagged)} transaction(s)**\n\n")
        fh.write("## By category\n\n")
        for category, amount in sorted(by_category.items(), key=lambda kv: -kv[1]):
            fh.write(f"- {category}: ${amount:,.2f}\n")
        fh.write("\n## Transactions\n\n")
        fh.write("| Date | Vendor | Category | Preferred Supplier | Amount |\n")
        fh.write("|---|---|---|---|---|\n")
        for r in flagged:
            t = r.transaction
            fh.write(
                f"| {t.date} | {r.canonical_vendor} | {r.category} | "
                f"{r.preferred_supplier} | ${t.amount:,.2f} |\n"
            )


def write_all_reports(
    outdir: str, results: List[ClassifiedTransaction], clusters: Dict[int, VendorCluster]
) -> Dict[str, str]:
    os.makedirs(outdir, exist_ok=True)
    paths = {
        "classified_csv": os.path.join(outdir, "classified_transactions.csv"),
        "vendor_aliases_md": os.path.join(outdir, "vendor_alias_report.md"),
        "maverick_md": os.path.join(outdir, "maverick_spend_report.md"),
    }
    write_classified_csv(paths["classified_csv"], results)
    write_vendor_alias_report(paths["vendor_aliases_md"], clusters)
    write_maverick_report(paths["maverick_md"], results)
    return paths
