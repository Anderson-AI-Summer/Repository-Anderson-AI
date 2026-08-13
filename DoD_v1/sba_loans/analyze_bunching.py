# -*- coding: utf-8 -*-
import json, glob, os
from collections import defaultdict

BASE = r"C:\finances\data\sba_loans\bunching"
VENDORS = {
    "00": "AmerisourceBergen Drug Corp",
    "01": "Atlantic Diving Supply, Inc.",
    "02": "W S Darley & Co",
    "03": "Noble Supply & Logistics, LLC",
    "04": "SupplyCore LLC",
    "05": "Lazarus Energy Holdings LLC",
    "06": "ASRC Federal Facilities Logistics, LLC",
    "07": "Leidos, Inc.",
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
        # CONT_AWD_<award>_<agency>_<parentIDV>_<agency>
        if len(parts) >= 5:
            parent = parts[-2]
            return parent if parent not in ("NONE", "-NONE-") else None
        return None

    for r in records:
        r["_parent_idv"] = parent_idv(r)

    # group by (date, awarding sub agency)
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
                "vendor": vname,
                "date": date,
                "agency": agency,
                "n_awards": len(items),
                "total": total,
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
        "vendor": vname,
        "total_records": len(records),
        "same_day_agency_clusters": len(vendor_clusters),
        "clusters_that_wouldve_exceeded_sat": n_exceed,
        "clusters_under_same_parent_vehicle": n_exceed - n_standalone,
        "clusters_standalone_or_mixed_parents": n_standalone,
        "dollars_in_exceeding_clusters": sum(c["total"] for c in vendor_clusters if c["would_exceed_sat"]),
        "dollars_in_standalone_clusters": sum(c["total"] for c in vendor_clusters if c["would_exceed_sat"] and not c["same_parent_vehicle"]),
    })

print("=== VENDOR SUMMARY ===")
for v in sorted(vendor_summary, key=lambda x: -x["clusters_standalone_or_mixed_parents"]):
    print(f"{v['vendor']:42s} records={v['total_records']:4d}  clusters={v['same_day_agency_clusters']:4d}  same-vehicle(normal)={v['clusters_under_same_parent_vehicle']:4d}  STANDALONE(flag)={v['clusters_standalone_or_mixed_parents']:4d}  $standalone={v['dollars_in_standalone_clusters']:,.0f}")

print()
print("=== STANDALONE CLUSTERS ONLY (different/no parent vehicle — the real signal) ===")
standalone = sorted([c for c in all_clusters if c["would_exceed_sat"] and not c["same_parent_vehicle"]], key=lambda c: -c["total"])
for c in standalone[:40]:
    print(f"{c['vendor']:38s} {c['date']}  {c['agency']:32s} n={c['n_awards']}  sum=${c['total']:,.0f}  parents={c['n_distinct_parents']}")
print(f"\ntotal standalone clusters: {len(standalone)}")

with open(r"C:\finances\data\sba_loans\_bunching_analysis.json", "w") as f:
    json.dump({"vendor_summary": vendor_summary, "clusters": standalone}, f)
