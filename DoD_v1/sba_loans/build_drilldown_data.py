# -*- coding: utf-8 -*-
import json
from collections import Counter

with open(r"C:\finances\data\sba_loans\_singlebid_under_sat.json") as f:
    d = json.load(f)

records = d["records"]

BRANCH_SHORT = {
    "Department of the Army": "Army",
    "Department of the Air Force": "Air Force",
    "Department of the Navy": "Navy",
    "Defense Logistics Agency": "DLA",
    "Washington Headquarters Services": "WHS",
    "Defense Contract Management Agency": "DCMA",
    "Defense Commissary Agency": "DeCA",
    "Defense Health Agency": "DHA",
    "Defense Threat Reduction Agency": "DTRA",
    "U.S. Special Operations Command": "SOCOM",
    "Missile Defense Agency": "MDA",
    "Department of Defense Education Activity": "DoDEA",
    "Defense Advanced Research Projects Agency": "DARPA",
    "Defense Human Resources Activity": "DHRA",
}

def titlecase_vendor(name):
    if not name:
        return name
    small_caps = {"LLC", "INC", "CORP", "LTD", "LP", "PC", "PLLC"}
    parts = name.split()
    out = []
    for p in parts:
        core = p.strip(",.")
        if core.upper() in small_caps:
            out.append(p.capitalize() if False else p[0] + p[1:].lower())
        else:
            out.append(p.capitalize())
    return " ".join(out)

table_rows = []
for r in records:
    table_rows.append({
        "vendor": titlecase_vendor(r["recipient"]),
        "award_id": r["award_id"],
        "amount": r["amount"],
        "extent_competed": r["extent_competed"].title(),
        "branch": BRANCH_SHORT.get(r["sub_agency"], r["sub_agency"] or "Unknown"),
        "branch_full": r["sub_agency"] or "Unknown",
        "date": r["date"],
        "near_threshold": r["near_threshold"],
        "psc": r.get("psc"),
    })

table_rows.sort(key=lambda x: -x["amount"])

branch_counts_near = Counter(r["branch"] for r in table_rows if r["near_threshold"])
branch_counts_all = Counter(r["branch"] for r in table_rows)

leland_records = sorted(
    [r for r in table_rows if r["vendor"].upper().startswith("LELAND LIMITED")],
    key=lambda x: x["date"]
)

with open(r"C:\finances\data\sba_loans\_drilldown_final.json", "w") as f:
    json.dump({
        "rows": table_rows,
        "total_count": d["total_count"],
        "total_value": d["total_value"],
        "near_threshold_count": d["near_threshold_count"],
        "near_threshold_value": d["near_threshold_value"],
        "branch_counts_near": branch_counts_near.most_common(),
        "branch_counts_all": branch_counts_all.most_common(),
        "leland_records": leland_records,
    }, f)

print("Rows:", len(table_rows))
print("Branch counts (near-threshold):", branch_counts_near.most_common())
print("Leland records:", len(leland_records))
for lr in leland_records:
    print(" ", lr)
