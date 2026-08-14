"""Deterministic analytics over enriched transactions. No LLM involved --
this is the numeric ground truth that the Insights Agent narrates but never
recomputes.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from src.fiscal import current_fiscal_year, is_partial_fiscal_year
from src.schema import EnrichedTransaction


def to_dataframe(transactions: list[EnrichedTransaction]) -> pd.DataFrame:
    rows = [t.model_dump(mode="json") for t in transactions]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["action_date"] = pd.to_datetime(df["action_date"])
    return df


def _hhi(shares: pd.Series) -> float:
    """Herfindahl-Hirschman Index on 0-10000 scale (percent shares, squared, summed)."""
    pct = shares / shares.sum() * 100 if shares.sum() else shares
    return float((pct ** 2).sum())


def _confidence_distribution(series: pd.Series) -> dict:
    bins = [0, 0.5, 0.7, 0.85, 1.01]
    labels = ["low (<0.50)", "medium (0.50-0.70)", "high (0.70-0.85)", "very_high (0.85-1.00)"]
    binned = pd.cut(series, bins=bins, labels=labels, right=False, include_lowest=True)
    counts = binned.value_counts().reindex(labels, fill_value=0)
    return {str(k): int(v) for k, v in counts.items()}


def compute_analytics(transactions: list[EnrichedTransaction], today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    df = to_dataframe(transactions)
    cur_fy = current_fiscal_year(today)

    if df.empty:
        return {
            "generated_at": today.isoformat(),
            "current_fiscal_year": cur_fy,
            "totals": {},
            "annual": [],
            "monthly": [],
            "category_breakdown": [],
            "top_suppliers": [],
            "concentration": {"hhi": 0.0, "top5_share": 0.0, "top10_share": 0.0},
            "supplier_category_overlap": [],
            "confidence": {"classification": {}, "supplier_resolution": {}},
            "review_queue_count": 0,
            "tail_spend_share": 0.0,
            "notable_category_yoy_changes": [],
            "top_suppliers_names": [],
            "deobligation_rate": 0.0,
            "concentration_by_year": [],
            "year_over_year": [],
            "supplier_count_by_category": {},
        }

    net = float(df["transaction_obligation_signed"].sum())
    gross_pos = float(df.loc[df["transaction_obligation_signed"] > 0, "transaction_obligation_signed"].sum())
    deob = float(-df.loc[df["transaction_obligation_signed"] < 0, "transaction_obligation_signed"].sum())
    deob_rate = (deob / gross_pos) if gross_pos > 0 else 0.0

    totals = {
        "net_obligations": net,
        "gross_positive_obligations": gross_pos,
        "deobligations": deob,
        "deobligation_rate": deob_rate,
        "transaction_count": int(len(df)),
        "unique_awards": int(df["award_id_piid"].nunique()),
        "unique_suppliers": int(df["normalized_supplier"].nunique()),
        "avg_transaction_size": float(df["transaction_obligation_signed"].mean()),
        "median_transaction_size": float(df["transaction_obligation_signed"].median()),
        "zero_dollar_action_count": int((df["obligation_direction"] == "ZERO_DOLLAR_ACTION").sum()),
        "negative_transaction_count": int((df["transaction_obligation_signed"] < 0).sum()),
    }

    # --- annual series ---
    annual_rows = []
    for fy, g in df.groupby("fiscal_year"):
        fy = int(fy)
        g_net = float(g["transaction_obligation_signed"].sum())
        g_gross = float(g.loc[g["transaction_obligation_signed"] > 0, "transaction_obligation_signed"].sum())
        g_deob = float(-g.loc[g["transaction_obligation_signed"] < 0, "transaction_obligation_signed"].sum())
        annual_rows.append({
            "fiscal_year": fy,
            "is_partial_year": is_partial_fiscal_year(fy, today),
            "net_obligations": g_net,
            "gross_positive_obligations": g_gross,
            "deobligations": g_deob,
            "deobligation_rate": (g_deob / g_gross) if g_gross > 0 else 0.0,
            "transaction_count": int(len(g)),
            "unique_awards": int(g["award_id_piid"].nunique()),
            "unique_suppliers": int(g["normalized_supplier"].nunique()),
        })
    annual_rows.sort(key=lambda r: r["fiscal_year"])

    # --- monthly series -- finer granularity than fiscal year. Some datasets
    # (a single sample/refresh pull) only span one or two fiscal years, at
    # which point an annual trend chart has too few points to show a trend
    # at all; the dashboard falls back to this when that happens. ---
    monthly_rows = []
    month_key = df["action_date"].dt.to_period("M")
    for period, g in df.groupby(month_key):
        g_net = float(g["transaction_obligation_signed"].sum())
        g_gross = float(g.loc[g["transaction_obligation_signed"] > 0, "transaction_obligation_signed"].sum())
        g_deob = float(-g.loc[g["transaction_obligation_signed"] < 0, "transaction_obligation_signed"].sum())
        monthly_rows.append({
            "period": str(period),
            "net_obligations": g_net,
            "gross_positive_obligations": g_gross,
            "deobligations": g_deob,
            "transaction_count": int(len(g)),
        })
    monthly_rows.sort(key=lambda r: r["period"])

    # --- year-over-year % changes (net obligations) ---
    yoy = []
    for i in range(1, len(annual_rows)):
        prev, cur = annual_rows[i - 1], annual_rows[i]
        if prev["net_obligations"]:
            pct = (cur["net_obligations"] - prev["net_obligations"]) / abs(prev["net_obligations"]) * 100
        else:
            pct = None
        yoy.append({
            "from_fy": prev["fiscal_year"], "to_fy": cur["fiscal_year"],
            "pct_change_net_obligations": pct,
            "to_fy_is_partial": cur["is_partial_year"],
        })

    # --- category breakdown ---
    cat_rows = []
    for (cat, sub), g in df.groupby(["ai_spend_category", "ai_spend_subcategory"]):
        cat_rows.append({
            "category": cat, "subcategory": sub,
            "net_obligations": float(g["transaction_obligation_signed"].sum()),
            "transaction_count": int(len(g)),
            "unique_suppliers": int(g["normalized_supplier"].nunique()),
        })
    cat_rows.sort(key=lambda r: -r["net_obligations"])

    # category-level YoY notable changes (top categories by |change|, magnitude > 25%)
    cat_yoy = []
    for cat, g in df.groupby("ai_spend_category"):
        by_fy = g.groupby("fiscal_year")["transaction_obligation_signed"].sum().sort_index()
        fys = list(by_fy.index)
        for i in range(1, len(fys)):
            prev_v, cur_v = by_fy.iloc[i - 1], by_fy.iloc[i]
            if abs(prev_v) < 1000:
                continue
            pct = (cur_v - prev_v) / abs(prev_v) * 100
            if abs(pct) >= 25:
                cat_yoy.append({
                    "category": cat, "from_fy": int(fys[i - 1]), "to_fy": int(fys[i]),
                    "pct_change": float(pct),
                })
    cat_yoy.sort(key=lambda r: -abs(r["pct_change"]))

    # --- concentration by year ---
    concentration_by_year = []
    for fy, g in df.groupby("fiscal_year"):
        s = g.groupby("normalized_supplier")["transaction_obligation_signed"].sum().clip(lower=0)
        total_pos = s.sum()
        concentration_by_year.append({
            "fiscal_year": int(fy),
            "hhi": _hhi(s),
            "top5_share": float(s.sort_values(ascending=False).head(5).sum() / total_pos) if total_pos else 0.0,
            "unique_suppliers": int(g["normalized_supplier"].nunique()),
        })
    concentration_by_year.sort(key=lambda r: r["fiscal_year"])

    # --- top suppliers ---
    supplier_agg = df.groupby("normalized_supplier").agg(
        net_obligations=("transaction_obligation_signed", "sum"),
        transaction_count=("transaction_id", "count"),
        unique_awards=("award_id_piid", "nunique"),
    ).reset_index().sort_values("net_obligations", ascending=False)
    top_suppliers = supplier_agg.head(25).to_dict("records")

    positive_total = supplier_agg["net_obligations"].clip(lower=0).sum()
    top5_share = float(supplier_agg.head(5)["net_obligations"].clip(lower=0).sum() / positive_total) if positive_total else 0.0
    top10_share = float(supplier_agg.head(10)["net_obligations"].clip(lower=0).sum() / positive_total) if positive_total else 0.0
    hhi = _hhi(supplier_agg["net_obligations"].clip(lower=0))

    # --- tail spend: share of net obligations outside the top 10% of suppliers by spend ---
    n_suppliers = len(supplier_agg)
    head_n = max(1, int(n_suppliers * 0.10))
    tail_total = supplier_agg.iloc[head_n:]["net_obligations"].clip(lower=0).sum()
    tail_share = float(tail_total / positive_total) if positive_total else 0.0

    # --- supplier count per category & supplier-category overlap ---
    supplier_count_by_cat = df.groupby("ai_spend_category")["normalized_supplier"].nunique().to_dict()
    overlap_rows = []
    supplier_categories = df.groupby("normalized_supplier")["ai_spend_category"].apply(lambda s: sorted(set(s)))
    multi_cat_suppliers = supplier_categories[supplier_categories.apply(len) > 1]
    for supplier, cats in multi_cat_suppliers.items():
        overlap_rows.append({"supplier": supplier, "categories": cats, "category_count": len(cats)})
    overlap_rows.sort(key=lambda r: -r["category_count"])

    # --- confidence distributions & review queue ---
    classification_conf_dist = _confidence_distribution(df["classification_confidence"])
    supplier_conf_dist = _confidence_distribution(df["supplier_resolution_confidence"])
    review_queue_count = int((df["review_status"] == "NEEDS_REVIEW").sum())

    return {
        "generated_at": today.isoformat(),
        "current_fiscal_year": cur_fy,
        "totals": totals,
        "annual": annual_rows,
        "monthly": monthly_rows,
        "year_over_year": yoy,
        "category_breakdown": cat_rows,
        "top_suppliers": top_suppliers,
        "top_suppliers_names": [r["normalized_supplier"] for r in top_suppliers[:10]],
        "concentration": {"hhi": hhi, "top5_share": top5_share, "top10_share": top10_share},
        "supplier_count_by_category": supplier_count_by_cat,
        "supplier_category_overlap": overlap_rows,
        "confidence": {
            "classification": classification_conf_dist,
            "supplier_resolution": supplier_conf_dist,
        },
        "review_queue_count": review_queue_count,
        "tail_spend_share": tail_share,
        "notable_category_yoy_changes": cat_yoy[:6],
        "deobligation_rate": deob_rate,
        "concentration_by_year": concentration_by_year,
    }
