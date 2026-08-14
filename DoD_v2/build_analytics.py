# -*- coding: utf-8 -*-
"""
Computes the analytics + data_prep payload, adapted from v3's
src/analytics.py + src/dashboard/data_prep.py, for the DoD enriched dataset.
"""
import json, datetime as dt
import pandas as pd
import numpy as np

OUT_DIR = r"C:\finances\DoD_v2\data"
df = pd.read_pickle(f"{OUT_DIR}/enriched.pkl")
TODAY = dt.date(2026, 8, 12)
CURRENT_FY = 2026

def _hhi(shares: pd.Series) -> float:
    pct = shares / shares.sum() * 100 if shares.sum() else shares
    return float((pct ** 2).sum())

# ============================================================
# TOTALS
# ============================================================
net = float(df["amount"].sum())
totals = {
    "net_obligations": net,
    "transaction_count": int(len(df)),
    "unique_awards": int(df["award_id_piid"].nunique()),
    "unique_suppliers": int(df["normalized_supplier"].nunique()),
    "avg_transaction_size": float(df["amount"].mean()),
    "median_transaction_size": float(df["amount"].median()),
    "zero_dollar_action_count": int((df["amount"] == 0).sum()),
}
print("Totals:", totals)

# ============================================================
# ANNUAL SERIES
# ============================================================
annual_rows = []
for fy, g in df.groupby("fiscal_year"):
    annual_rows.append({
        "fiscal_year": int(fy),
        "is_partial_year": bool(fy == CURRENT_FY),
        "net_obligations": float(g["amount"].sum()),
        "transaction_count": int(len(g)),
        "unique_awards": int(g["award_id_piid"].nunique()),
        "unique_suppliers": int(g["normalized_supplier"].nunique()),
    })
annual_rows.sort(key=lambda r: r["fiscal_year"])

yoy = []
for i in range(1, len(annual_rows)):
    prev, cur = annual_rows[i-1], annual_rows[i]
    pct = (cur["net_obligations"] - prev["net_obligations"]) / abs(prev["net_obligations"]) * 100 if prev["net_obligations"] else None
    yoy.append({"from_fy": prev["fiscal_year"], "to_fy": cur["fiscal_year"], "pct_change_net_obligations": pct, "to_fy_is_partial": cur["is_partial_year"]})

# ============================================================
# CATEGORY BREAKDOWN
# ============================================================
cat_rows = []
for (cat, sub), g in df.groupby(["ai_spend_category", "ai_spend_subcategory"]):
    cat_rows.append({
        "category": cat, "subcategory": sub,
        "net_obligations": float(g["amount"].sum()),
        "transaction_count": int(len(g)),
        "unique_suppliers": int(g["normalized_supplier"].nunique()),
    })
cat_rows.sort(key=lambda r: -r["net_obligations"])

cat_yoy = []
for cat, g in df.groupby("ai_spend_category"):
    by_fy = g.groupby("fiscal_year")["amount"].sum().sort_index()
    fys = list(by_fy.index)
    for i in range(1, len(fys)):
        prev_v, cur_v = by_fy.iloc[i-1], by_fy.iloc[i]
        if abs(prev_v) < 1000: continue
        pct = (cur_v - prev_v) / abs(prev_v) * 100
        if abs(pct) >= 25:
            cat_yoy.append({"category": cat, "from_fy": int(fys[i-1]), "to_fy": int(fys[i]), "pct_change": float(pct)})
cat_yoy.sort(key=lambda r: -abs(r["pct_change"]))

# ============================================================
# CONCENTRATION
# ============================================================
supplier_agg = df.groupby("normalized_supplier").agg(
    net_obligations=("amount", "sum"),
    transaction_count=("transaction_id", "count"),
    unique_awards=("award_id_piid", "nunique"),
).reset_index().sort_values("net_obligations", ascending=False)
top_suppliers = supplier_agg.head(25).to_dict("records")

positive_total = supplier_agg["net_obligations"].clip(lower=0).sum()
top5_share = float(supplier_agg.head(5)["net_obligations"].sum() / positive_total) if positive_total else 0.0
top10_share = float(supplier_agg.head(10)["net_obligations"].sum() / positive_total) if positive_total else 0.0
hhi = _hhi(supplier_agg["net_obligations"])

n_suppliers = len(supplier_agg)
head_n = max(1, int(n_suppliers * 0.10))
tail_total = supplier_agg.iloc[head_n:]["net_obligations"].sum()
tail_share = float(tail_total / positive_total) if positive_total else 0.0

concentration_by_year = []
for fy, g in df.groupby("fiscal_year"):
    s = g.groupby("normalized_supplier")["amount"].sum().clip(lower=0)
    total_pos = s.sum()
    concentration_by_year.append({
        "fiscal_year": int(fy), "hhi": _hhi(s),
        "top5_share": float(s.sort_values(ascending=False).head(5).sum() / total_pos) if total_pos else 0.0,
        "unique_suppliers": int(g["normalized_supplier"].nunique()),
    })
concentration_by_year.sort(key=lambda r: r["fiscal_year"])

analytics = {
    "generated_at": TODAY.isoformat(),
    "current_fiscal_year": CURRENT_FY,
    "totals": totals,
    "annual": annual_rows,
    "year_over_year": yoy,
    "category_breakdown": cat_rows,
    "top_suppliers": top_suppliers,
    "concentration": {"hhi": hhi, "top5_share": top5_share, "top10_share": top10_share},
    "tail_spend_share": tail_share,
    "notable_category_yoy_changes": cat_yoy[:6],
    "concentration_by_year": concentration_by_year,
}
print(f"HHI: {hhi:.0f}, top5 share: {top5_share*100:.1f}%, tail spend share: {tail_share*100:.1f}%")

# ============================================================
# SUPPLIER DETAIL (for data_prep._supplier_detail)
# ============================================================
print("Building supplier detail...")
suppliers_detail = {}
for supplier, g in df.groupby("normalized_supplier"):
    annual = [{"fiscal_year": int(fy), "net_obligations": float(gf["amount"].sum())} for fy, gf in g.groupby("fiscal_year")]
    annual.sort(key=lambda r: r["fiscal_year"])
    net = float(g["amount"].sum())
    cat_mix = g.groupby("ai_spend_category")["amount"].sum().sort_values(ascending=False)
    offices = sorted(x for x in g["awarding_office_name"].dropna().unique().tolist())[:10]
    variants = sorted(g["recipient_name_raw"].unique().tolist())
    suppliers_detail[supplier] = {
        "total_net_obligations": net,
        "transaction_count": int(len(g)),
        "unique_awards": int(g["award_id_piid"].nunique()),
        "annual": annual,
        "category_mix": [{"category": c, "net_obligations": float(v)} for c, v in cat_mix.items()],
        "awarding_offices": offices,
        "share_of_agency_obligations": (net / totals["net_obligations"]) if totals["net_obligations"] else 0.0,
        "raw_name_variants": variants,
    }

# ============================================================
# CATEGORY DETAIL
# ============================================================
print("Building category detail...")
categories_detail = {}
for cat, g in df.groupby("ai_spend_category"):
    annual = [{"fiscal_year": int(fy), "net_obligations": float(gf["amount"].sum())} for fy, gf in g.groupby("fiscal_year")]
    annual.sort(key=lambda r: r["fiscal_year"])
    supplier_agg_c = g.groupby("normalized_supplier")["amount"].sum().sort_values(ascending=False)
    total_c = supplier_agg_c.sum()
    hhi_c = _hhi(supplier_agg_c)
    n_c = len(supplier_agg_c)
    head_n_c = max(1, int(n_c * 0.10))
    tail_share_c = float(supplier_agg_c.iloc[head_n_c:].sum() / total_c) if total_c else 0.0
    categories_detail[cat] = {
        "annual": annual,
        "unique_suppliers": int(g["normalized_supplier"].nunique()),
        "leading_suppliers": [{"supplier": s, "net_obligations": float(v)} for s, v in supplier_agg_c.head(10).items()],
        "concentration_hhi": hhi_c,
        "tail_spend_share": tail_share_c,
        "low_confidence_count": int((g["classification_confidence"] < 0.6).sum()),
    }

# ============================================================
# STANDOUT SUPPLIERS
# ============================================================
def standout_suppliers(suppliers_detail, max_results=8):
    candidates = []
    for name, d in suppliers_detail.items():
        annual = sorted(d["annual"], key=lambda r: r["fiscal_year"])
        yoy_pct = None; yoy_from = yoy_to = None
        if len(annual) >= 2:
            prev, cur = annual[-2], annual[-1]
            if abs(prev["net_obligations"]) >= 50_000:
                yoy_pct = (cur["net_obligations"] - prev["net_obligations"]) / abs(prev["net_obligations"]) * 100
                yoy_from, yoy_to = prev["fiscal_year"], cur["fiscal_year"]
        reasons = []
        if yoy_pct is not None and abs(yoy_pct) >= 75:
            direction = "growth" if yoy_pct > 0 else "decline"
            reasons.append({"type": f"rapid_{direction}", "label": f"Rapid year-over-year {direction}",
                "detail": f"Net obligations changed {yoy_pct:+.1f}% from FY{yoy_from} to FY{yoy_to}."})
        candidates.append({
            "supplier": name, "net_obligations": d["total_net_obligations"],
            "concentration_pct": d["share_of_agency_obligations"] * 100,
            "transaction_count": d["transaction_count"], "unique_awards": d["unique_awards"],
            "reasons": reasons,
        })
    candidates.sort(key=lambda c: -c["concentration_pct"])
    standout, seen = [], set()
    for c in candidates[:5]:
        c["reasons"] = [{"type": "high_concentration", "label": "High spend concentration",
            "detail": f"${c['net_obligations']:,.0f} ({c['concentration_pct']:.1f}%) of total DoD net obligations in this dataset."}] + c["reasons"]
        standout.append(c); seen.add(c["supplier"])
    for c in candidates:
        if len(standout) >= max_results: break
        if c["supplier"] in seen: continue
        if c["reasons"]:
            standout.append(c); seen.add(c["supplier"])
    return standout[:max_results]

standout_sup = standout_suppliers(suppliers_detail)

# ============================================================
# AWARD ROWS + STANDOUT AWARDS
# ============================================================
print("Building award rows...")
award_rows = []
for award_id, g in df.groupby("award_id_piid"):
    if not award_id or award_id == "UNKNOWN": continue
    g_sorted = g.sort_values("action_date")
    net = float(g["amount"].sum())
    first_date = g_sorted.iloc[0]["action_date"]
    first_date = first_date.date().isoformat() if pd.notna(first_date) else None
    descriptions = [d for d in g["transaction_description"].tolist() if d]
    description = max(descriptions, key=len) if descriptions else ""
    supplier_counts = g["normalized_supplier"].value_counts()
    category_counts = g["ai_spend_category"].value_counts()
    award_rows.append({
        "award_id": str(award_id),
        "supplier": supplier_counts.idxmax() if not supplier_counts.empty else "Unknown",
        "category": category_counts.idxmax() if not category_counts.empty else "Uncategorized",
        "net_obligations": net,
        "first_date": first_date,
        "transaction_count": int(len(g)),
        "description": description[:400],
        "extent_competed": g_sorted.iloc[-1].get("extent_competed", ""),
        "branch": g_sorted.iloc[-1].get("awarding_sub_agency_name", ""),
    })

def standout_awards(rows, max_results=8):
    candidates = sorted(rows, key=lambda r: -r["net_obligations"])
    standout, seen = [], set()
    for c in candidates[:5]:
        standout.append({**c, "reasons": [{"type": "high_value", "label": "High contract value",
            "detail": f"${c['net_obligations']:,.0f} in net obligations -- one of the largest contracts in this dataset."}]})
        seen.add(c["award_id"])
    return standout[:max_results]

standout_awd = standout_awards(award_rows)
awards_summary = sorted(award_rows, key=lambda r: -r["net_obligations"])[:300]

# ============================================================
# CONSOLIDATION OPPORTUNITIES
# ============================================================
def consolidation_opportunities(categories_detail, max_results=6):
    MIN_SPEND, MIN_SUPPLIERS, HHI_THRESH = 5_000_000, 3, 2500
    candidates = []
    for category, d in categories_detail.items():
        if category == "Other or Unclassified": continue
        total = sum(r["net_obligations"] for r in d["leading_suppliers"])
        if total < MIN_SPEND or d["unique_suppliers"] < MIN_SUPPLIERS: continue
        if d["concentration_hhi"] >= HHI_THRESH: continue
        top = d["leading_suppliers"][0] if d["leading_suppliers"] else None
        top_share = (top["net_obligations"] / total) if (top and total) else 0.0
        candidates.append({
            "category": category, "total_net_obligations": total,
            "unique_suppliers": d["unique_suppliers"], "concentration_hhi": d["concentration_hhi"],
            "top_supplier": top["supplier"] if top else None, "top_supplier_share_pct": top_share * 100,
            "leading_suppliers": d["leading_suppliers"][:5],
            "detail": (f"${total:,.0f} in this category is split across {d['unique_suppliers']} suppliers; "
                       f"the largest ({top['supplier'] if top else 'n/a'}) accounts for only {top_share*100:.0f}% "
                       f"(HHI={d['concentration_hhi']:.0f}). Fragmentation signal only -- not a specific vendor "
                       f"recommendation or savings estimate."),
        })
    candidates.sort(key=lambda c: -c["total_net_obligations"])
    return candidates[:max_results]

consolidation = consolidation_opportunities(categories_detail)

# ============================================================
# DUPLICATE PURCHASE CANDIDATES
# ============================================================
def duplicate_purchase_candidates(rows, max_results=6):
    AMOUNT_TOLERANCE, MIN_AMOUNT, MAX_AMOUNT, MAX_DAYS = 0.30, 5_000, 2_000_000, 120
    groups = {}
    for r in rows:
        if not r["first_date"] or not (MIN_AMOUNT <= abs(r["net_obligations"]) <= MAX_AMOUNT): continue
        groups.setdefault((r["supplier"], r["category"]), []).append(r)
    candidates = []
    seen_awards = set()
    for (supplier, category), awards in groups.items():
        if len(awards) < 2: continue
        awards = sorted(awards, key=lambda r: r["first_date"])
        for i in range(len(awards)):
            for j in range(i+1, len(awards)):
                a, b = awards[i], awards[j]
                if a["award_id"] in seen_awards or b["award_id"] in seen_awards: continue
                days_apart = (dt.date.fromisoformat(b["first_date"]) - dt.date.fromisoformat(a["first_date"])).days
                if days_apart > MAX_DAYS or days_apart < 0: continue
                bigger, smaller = max(a["net_obligations"], b["net_obligations"]), min(a["net_obligations"], b["net_obligations"])
                if bigger <= 0 or (bigger - smaller) / bigger > AMOUNT_TOLERANCE: continue
                candidates.append({
                    "pair_id": "::".join(sorted([a["award_id"], b["award_id"]])),
                    "supplier": supplier, "category": category,
                    "award_id_a": a["award_id"], "award_id_b": b["award_id"],
                    "amount_a": a["net_obligations"], "amount_b": b["net_obligations"],
                    "date_a": a["first_date"], "date_b": b["first_date"], "days_apart": days_apart,
                    "combined_value": a["net_obligations"] + b["net_obligations"],
                    "detail": (f"Two separate awards to {supplier} in {category}, {days_apart} day(s) apart, "
                               f"for similar amounts (${a['net_obligations']:,.0f} and ${b['net_obligations']:,.0f})."),
                })
                seen_awards.add(a["award_id"]); seen_awards.add(b["award_id"])
    candidates.sort(key=lambda c: -c["combined_value"])
    return candidates[:max_results]

duplicates = duplicate_purchase_candidates(award_rows)

# ============================================================
# SAVE
# ============================================================
payload = {
    "meta": {
        "title": "DoD Procurement Intelligence Dashboard",
        "disclosure": "Unofficial educational project analyzing six-plus years of DoD contract award data. Not affiliated with or endorsed by the Department of Defense.",
        "data_period_start": "2019-10-01",
        "data_period_end": "2026-04-30",
        "transaction_count": len(df),
        "source": "USAspending.gov bulk award-download API (definitive contracts, award type D)",
        "current_fiscal_year": CURRENT_FY,
        "note": "This dataset is AWARD-LEVEL -- one row per contract award reflecting its current total value as of extraction, not a full modification-by-modification transaction history. There is no deobligation/negative-transaction data here. 'Transaction count' == award count.",
    },
    "analytics": analytics,
    "suppliers_detail": suppliers_detail,
    "categories_detail": categories_detail,
    "standout_suppliers": standout_sup,
    "standout_awards": standout_awd,
    "awards_summary": awards_summary,
    "consolidation_opportunities": consolidation,
    "duplicate_purchase_candidates": duplicates,
}

with open(f"{OUT_DIR}/payload.json", "w") as f:
    json.dump(payload, f)

print(f"\nDone. Standout suppliers: {len(standout_sup)}, standout awards: {len(standout_awd)}, "
      f"consolidation opportunities: {len(consolidation)}, duplicate candidates: {len(duplicates)}")
print(f"Payload saved to {OUT_DIR}/payload.json")
