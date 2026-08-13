# -*- coding: utf-8 -*-
import json, glob, os
from collections import defaultdict

BASE = r"C:\finances\data\sba_loans\bunching_fullrange"
VENDORS = {
    "00": "AmerisourceBergen Drug Corp",
    "01": "Atlantic Diving Supply, Inc.",
    "02": "McKesson Corporation",
    "03": "Noble Supply & Logistics, LLC",
    "04": "W S Darley & Co",
    "05": "SupplyCore LLC",
    "06": "ASRC Federal Facilities Logistics, LLC",
    "07": "Lazarus Energy Holdings LLC",
}

all_clusters = []
vendor_summary = []

for idx, vname in VENDORS.items():
    records = []
    for page in range(1, 6):
        path = os.path.join(BASE, f"{idx}_page{page}.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        records.extend(d.get("results", []))

    def parent_idv(rec):
        gid = rec.get("generated_internal_id", "") or ""
        parts = gid.split("_")
        if len(parts) >= 5:
            parent = parts[-2]
            return parent if parent not in ("NONE", "-NONE-") else None
        return None

    for r in records:
        r["_parent_idv"] = parent_idv(r)

    groups = defaultdict(list)
    for r in records:
        date = r.get("Base Obligation Date")
        agency = r.get("Awarding Sub Agency")
        amt = r.get("Award Amount")
        if date is None or amt is None:
            continue
        groups[(date, agency)].append(r)

    vendor_clusters = []
    for (date, agency), items in groups.items():
        if len(items) >= 2:
            total = sum(i["Award Amount"] for i in items)
            parents = set(i["_parent_idv"] for i in items)
            same_vehicle = len(parents) == 1 and None not in parents
            vendor_clusters.append({
                "vendor": vname, "date": date, "agency": agency,
                "n_awards": len(items), "total": total,
                "would_exceed_sat": total > 350000,
                "same_parent_vehicle": same_vehicle,
                "n_distinct_parents": len(parents),
                "awards": [{"id": i.get("Award ID"), "amount": i["Award Amount"], "parent": i["_parent_idv"]} for i in items],
            })

    vendor_clusters.sort(key=lambda c: -c["total"])
    all_clusters.extend(vendor_clusters)

    n_exceed = sum(1 for c in vendor_clusters if c["would_exceed_sat"])
    n_standalone = sum(1 for c in vendor_clusters if c["would_exceed_sat"] and not c["same_parent_vehicle"])
    vendor_summary.append({
        "vendor": vname, "total_records": len(records),
        "same_day_agency_clusters": len(vendor_clusters),
        "clusters_that_wouldve_exceeded_sat": n_exceed,
        "clusters_under_same_parent_vehicle": n_exceed - n_standalone,
        "clusters_standalone_or_mixed_parents": n_standalone,
        "dollars_in_exceeding_clusters": sum(c["total"] for c in vendor_clusters if c["would_exceed_sat"]),
        "dollars_in_standalone_clusters": sum(c["total"] for c in vendor_clusters if c["would_exceed_sat"] and not c["same_parent_vehicle"]),
    })

print("=== VENDOR SUMMARY (full range) ===")
for v in sorted(vendor_summary, key=lambda x: -x["clusters_standalone_or_mixed_parents"]):
    print(f"{v['vendor']:42s} records={v['total_records']:4d}  clusters={v['same_day_agency_clusters']:4d}  same-vehicle={v['clusters_under_same_parent_vehicle']:4d}  STANDALONE={v['clusters_standalone_or_mixed_parents']:4d}  $standalone={v['dollars_in_standalone_clusters']:,.0f}")

standalone = sorted([c for c in all_clusters if c["would_exceed_sat"] and not c["same_parent_vehicle"]], key=lambda c: -c["total"])
print(f"\ntotal standalone clusters: {len(standalone)}")
print(f"total standalone dollars: {sum(c['total'] for c in standalone):,.0f}")

with open(r"C:\finances\data\sba_loans\_bunching_analysis_fullrange.json", "w") as f:
    json.dump({"vendor_summary": vendor_summary, "clusters": standalone}, f)
