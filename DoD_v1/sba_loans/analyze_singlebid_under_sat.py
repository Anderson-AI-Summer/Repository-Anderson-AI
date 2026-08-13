# -*- coding: utf-8 -*-
import csv, glob, json
from collections import defaultdict, Counter

FILES = glob.glob(r"C:\finances\data\sba_loans\offers_monthly\*.csv")

rows = []
for path in FILES:
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows.extend(list(reader))

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

GENUINELY_COMPETED = {"FULL AND OPEN COMPETITION", "FULL AND OPEN COMPETITION AFTER EXCLUSION OF SOURCES", "COMPETED UNDER SAP"}

single_bid_under_sat = []
for r in rows:
    offers = to_int(r.get("number_of_offers_received"))
    ec = (r.get("extent_competed") or "").strip().upper()
    amt = to_float(r.get("total_dollars_obligated") or r.get("current_total_value_of_award") or r.get("potential_total_value_of_award"))
    if offers == 1 and ec in GENUINELY_COMPETED and amt is not None and 0 < amt < 350000:
        single_bid_under_sat.append({
            "recipient": r.get("recipient_name"),
            "award_id": r.get("award_id_piid"),
            "amount": amt,
            "extent_competed": ec,
            "date": r.get("period_of_performance_start_date") or r.get("action_date"),
            "office": r.get("awarding_office_name"),
            "sub_agency": r.get("awarding_sub_agency_name"),
            "psc": r.get("product_or_service_code_description"),
            "naics": r.get("naics_description"),
            "pricing_type": r.get("type_of_contract_pricing"),
            "near_threshold": amt >= 300000,
        })

single_bid_under_sat.sort(key=lambda x: -x["amount"])

print(f"Total single-bid competed contracts under $350K: {len(single_bid_under_sat)}")
total_value = sum(s["amount"] for s in single_bid_under_sat)
print(f"Total value: ${total_value:,.0f}")

near = [s for s in single_bid_under_sat if s["near_threshold"]]
print(f"Of those, in the $300K-$349,999 'near-threshold' band: {len(near)}  (${sum(s['amount'] for s in near):,.0f})")

print()
print("Extent competed breakdown:")
ec_dist = Counter(s["extent_competed"] for s in single_bid_under_sat)
for k, v in ec_dist.most_common():
    print(f"  {k}: {v}")

print()
print("Vendor concentration (vendors with 2+ single-bid sub-SAT awards):")
vendor_counts = defaultdict(lambda: {"count": 0, "value": 0.0})
for s in single_bid_under_sat:
    vendor_counts[s["recipient"]]["count"] += 1
    vendor_counts[s["recipient"]]["value"] += s["amount"]
repeat_vendors = sorted(
    [(k, v) for k, v in vendor_counts.items() if v["count"] >= 2],
    key=lambda x: -x[1]["count"]
)
for name, v in repeat_vendors[:20]:
    print(f"  n={v['count']:2d}  ${v['value']:>10,.0f}  {name}")
print(f"  ... {len(repeat_vendors)} vendors total with 2+ awards; {len(vendor_counts)} unique vendors overall")

print()
print("Top 30 by dollar value:")
for s in single_bid_under_sat[:30]:
    print(f"  ${s['amount']:>9,.0f}  {s['recipient'][:35]:35s}  {s['award_id']:18s}  {s['extent_competed']:22s}  {s['sub_agency']}")

with open(r"C:\finances\data\sba_loans\_singlebid_under_sat.json", "w") as f:
    json.dump({
        "records": single_bid_under_sat,
        "total_count": len(single_bid_under_sat),
        "total_value": total_value,
        "near_threshold_count": len(near),
        "near_threshold_value": sum(s["amount"] for s in near),
        "repeat_vendors": [{"name": k, **v} for k, v in repeat_vendors],
    }, f)
