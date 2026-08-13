# -*- coding: utf-8 -*-
import csv, glob, os
from collections import defaultdict

FILES = glob.glob(r"C:\finances\data\sba_loans\offers_fullrange\*.csv")

rows = []
for path in FILES:
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

print("Total definitive contract records:", len(rows))

# dedupe by award unique key in case of overlap
seen = set()
deduped = []
for r in rows:
    key = r.get("award_id_piid") or r.get("contract_award_unique_key")
    if key in seen:
        continue
    seen.add(key)
    deduped.append(r)
print("After dedupe:", len(deduped))

def to_int(v):
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None

def to_float(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None

populated = [r for r in deduped if to_int(r.get("number_of_offers_received")) is not None]
print("Rows with offers count populated:", len(populated), f"({len(populated)/len(deduped)*100:.1f}%)")

# extent competed field name check
sample = deduped[0]
ec_fields = [k for k in sample.keys() if 'compet' in k.lower()]
print("extent-competed-related fields:", ec_fields)

GENUINELY_COMPETED = {"FULL AND OPEN COMPETITION", "FULL AND OPEN COMPETITION AFTER EXCLUSION OF SOURCES", "COMPETED UNDER SAP"}

single_bid = []
for r in populated:
    offers = to_int(r["number_of_offers_received"])
    ec = (r.get("extent_competed") or "").strip().upper()
    amt = to_float(r.get("total_dollars_obligated") or r.get("current_total_value_of_award") or r.get("potential_total_value_of_award"))
    if offers == 1 and ec in GENUINELY_COMPETED:
        single_bid.append({
            "recipient": r.get("recipient_name"),
            "award_id": r.get("award_id_piid"),
            "amount": amt,
            "extent_competed": ec,
            "date": r.get("period_of_performance_start_date") or r.get("action_date"),
            "office": r.get("awarding_office_name"),
        })

print()
from collections import Counter
print("extent_competed distribution among offers=1 records:")
ec_dist = Counter((r.get("extent_competed") or "").strip().upper() for r in populated if to_int(r["number_of_offers_received"]) == 1)
for k, v in ec_dist.most_common():
    print(f"  {k}: {v}")
print()
print("Distribution of offers received:")
dist = defaultdict(int)
for r in populated:
    o = to_int(r["number_of_offers_received"])
    bucket = str(o) if o is not None and o <= 5 else "6+"
    dist[bucket] += 1
for k in sorted(dist.keys(), key=lambda x: (x=="6+", x)):
    print(f"  {k}: {dist[k]}")

print()
print(f"Single-bid 'competed' contracts found: {len(single_bid)}")
single_bid_valued = [s for s in single_bid if s["amount"]]
single_bid_valued.sort(key=lambda s: -(s["amount"] or 0))
total_single_bid_value = sum(s["amount"] for s in single_bid_valued)
print(f"Total value of single-bid competed contracts: ${total_single_bid_value:,.0f}")
print()
print("Top 25 by value:")
for s in single_bid_valued[:25]:
    print(f"  ${s['amount']:>14,.0f}  {s['recipient'][:40]:40s}  {s['award_id']:20s}  {s['extent_competed']}")

# Context: what share of ALL genuinely-competed contracts got only 1 offer?
all_competed = [r for r in populated if (r.get("extent_competed") or "").strip().upper() in GENUINELY_COMPETED]
all_competed_valued = [to_float(r.get("total_dollars_obligated") or r.get("current_total_value_of_award") or r.get("potential_total_value_of_award")) for r in all_competed]
all_competed_value = sum(v for v in all_competed_valued if v)
print(f"All genuinely-competed definitive contracts: {len(all_competed)}, total value ${all_competed_value:,.0f}")
print(f"Single-bid share of competed contracts: {len(single_bid)/len(all_competed)*100:.1f}% by count, {total_single_bid_value/all_competed_value*100:.1f}% by value")

# Vendor rollup
vendor_totals = defaultdict(lambda: {"count": 0, "value": 0.0})
for s in single_bid_valued:
    vendor_totals[s["recipient"]]["count"] += 1
    vendor_totals[s["recipient"]]["value"] += s["amount"] or 0

vendor_rollup = sorted(
    [{"vendor": k, "count": v["count"], "value": v["value"]} for k, v in vendor_totals.items()],
    key=lambda x: -x["value"]
)
print()
print("Top 20 vendors by single-bid competed contract value:")
for v in vendor_rollup[:20]:
    print(f"  ${v['value']:>14,.0f}  n={v['count']:3d}  {v['vendor']}")

import json
with open(r"C:\finances\data\sba_loans\_single_bid_results.json", "w") as f:
    json.dump({
        "total_records": len(deduped),
        "populated": len(populated),
        "single_bid_count": len(single_bid),
        "single_bid_total_value": total_single_bid_value,
        "top_single_bid": single_bid_valued[:50],
        "offers_distribution": dict(dist),
        "all_competed_count": len(all_competed),
        "all_competed_value": all_competed_value,
        "vendor_rollup": vendor_rollup[:30],
    }, f)
