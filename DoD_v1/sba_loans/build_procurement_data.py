# -*- coding: utf-8 -*-
import json

# ---------- Monthly obligation pattern ----------
def load_monthly(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    out = {}
    for r in d["results"]:
        out[int(r["time_period"]["month"])] = r["aggregated_amount"]
    return out

all_m = load_monthly(r"C:\finances\data\sba_loans\_monthly_all.json")
nc_m = load_monthly(r"C:\finances\data\sba_loans\_monthly_noncompete.json")
sat_m = load_monthly(r"C:\finances\data\sba_loans\_monthly_satband.json")

labels = {10: "Oct", 11: "Nov", 12: "Dec", 1: "Jan", 2: "Feb", 3: "Mar",
          4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep"}
order = [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]

monthly_rows = []
for m in order:
    t = all_m.get(m, 0)
    nc = nc_m.get(m, 0)
    sat = sat_m.get(m, 0)
    monthly_rows.append({
        "month": labels[m],
        "total": t,
        "noncompete": nc,
        "noncompete_pct": nc / t * 100 if t else 0,
        "sat_tier": sat,
    })

avg = sum(r["total"] for r in monthly_rows) / 12
for r in monthly_rows:
    r["vs_avg_pct"] = (r["total"] / avg - 1) * 100

with open(r"C:\finances\data\sba_loans\_monthly_final.json", "w") as f:
    json.dump({"rows": monthly_rows, "avg": avg}, f)

print("Monthly avg:", avg)
for r in monthly_rows:
    print(r["month"], f"${r['total']/1e9:.2f}B", f"{r['vs_avg_pct']:+.0f}%", f"NC={r['noncompete_pct']:.1f}%")

# ---------- Cost-type mix by vendor ----------
with open(r"C:\finances\data\sba_loans\_costtype_by_vendor.json") as f:
    ct_rows = json.load(f)

# sort by share desc, keep only vendors with meaningful cost-type exposure or full context
ct_sorted = sorted(ct_rows, key=lambda r: -r["cost_type_share"])
with open(r"C:\finances\data\sba_loans\_costtype_final.json", "w") as f:
    json.dump(ct_sorted, f)

TOTAL_COST_TYPE = 145237923820.19
TOTAL_FIXED = 342221714944.87
TOTAL_TM = 1588139899.39
TOTAL_CONTRACTS = 491670911929.61

print()
print("Cost-type total:", TOTAL_COST_TYPE, TOTAL_COST_TYPE/TOTAL_CONTRACTS*100)
print("Fixed-price total:", TOTAL_FIXED, TOTAL_FIXED/TOTAL_CONTRACTS*100)

# ---------- Bunching summary ----------
with open(r"C:\finances\data\sba_loans\_bunching_analysis.json") as f:
    bunch = json.load(f)
print()
print("Bunching vendor summary:")
for v in bunch["vendor_summary"]:
    print(v["vendor"], v["clusters_standalone_or_mixed_parents"], v["dollars_in_standalone_clusters"])
