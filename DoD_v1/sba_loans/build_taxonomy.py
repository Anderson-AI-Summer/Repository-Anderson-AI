import json

with open(r"C:\finances\data\sba_loans\dod_naics_fy25.json") as f:
    d = json.load(f)

results = d["results"]
amt = {r["code"]: r["amount"] for r in results}
top100_sum = sum(amt.values())

TOTAL_DOD_FY25 = 501544127665.41
CONTRACTS_FY25 = 491670911929.61
GRANTS_FY25 = 9444059446.25
OTHER_FY25 = 425137235.55
DIRECT_PAY_FY25 = 4019054.0

buckets = {
    "Aircraft & Aviation Systems": [
        "336411","336413","336412","488190","481212","481211","611512"
    ],
    "Shipbuilding & Maritime": [
        "336611","483111"
    ],
    "Missiles, Space & Satellite Systems": [
        "336414","336419","336415","517410"
    ],
    "Ground Vehicles & Combat Equipment": [
        "336992","336212","333120"
    ],
    "Weapons, Ammunition & Ordnance": [
        "332993","332994","325920","332992"
    ],
    "Electronics, Sensors & Guidance/Comm Systems": [
        "334511","334220","334290","334111","334419","334412","335999","334519","334515","332510"
    ],
    "R&D and Engineering Services": [
        "541715","541712","541330","541714"
    ],
    "IT, Software & Computing Services": [
        "541512","541519","541511","511210","513210","541513","518210","517110","517111","561621"
    ],
    "Construction & Facilities Infrastructure": [
        "236220","237990","561210","237130","236210","238220","237120","237110","238990","221310","221122"
    ],
    "Professional, Management & Consulting Services": [
        "541990","541611","541614","561990","541690","541211","541219","561611","611430","541810"
    ],
    "Healthcare & Medical": [
        "524114","325411","424210","423450","622110"
    ],
    "Fuel, Energy & Petroleum": [
        "324110"
    ],
    "Industrial Supplies, Equipment & MRO": [
        "423850","339999","332410","811219","333310","333618","811210","811310","332999","333999","333613","423610"
    ],
    "Transportation & Logistics/Warehousing": [
        "493190","493110","492110"
    ],
    "Food & Subsistence": [
        "722310","311812","311999","311991","311421"
    ],
    "Environmental & Waste Management": [
        "562119","562910","562211"
    ],
    "Apparel & Textiles": [
        "315210","315990"
    ],
    "Base Support Services (janitorial/landscaping/security)": [
        "561720","561730","561612"
    ],
}

used_codes = set()
bucket_sums = {}
for name, codes in buckets.items():
    s = 0.0
    for c in codes:
        if c in amt:
            s += amt[c]
            used_codes.add(c)
    bucket_sums[name] = s

captured = sum(bucket_sums.values())
remainder = TOTAL_DOD_FY25 - captured

print(f"Total DoD FY2025 obligations: ${TOTAL_DOD_FY25:,.0f}")
print(f"Top-100 NAICS codes sum: ${top100_sum:,.0f} ({top100_sum/TOTAL_DOD_FY25*100:.1f}% of total)")
print(f"Codes used in buckets: {len(used_codes)} / {len(amt)}")
print()
print(f"{'Category':55s} {'Amount':>18s} {'% of Total':>10s}")
print("-"*90)
for name, s in sorted(bucket_sums.items(), key=lambda x: -x[1]):
    print(f"{name:55s} ${s:>16,.0f} {s/TOTAL_DOD_FY25*100:>9.1f}%")
print("-"*90)
print(f"{'Other / Long-tail NAICS + Grants + Other Assistance':55s} ${remainder:>16,.0f} {remainder/TOTAL_DOD_FY25*100:>9.1f}%")
print("-"*90)
print(f"{'TOTAL':55s} ${TOTAL_DOD_FY25:>16,.0f} {100.0:>9.1f}%")
