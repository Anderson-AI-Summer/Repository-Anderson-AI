"""Builds the single JSON payload embedded in the self-contained dashboard.

All aggregation happens here, in Python, before the HTML is generated -- the
browser only filters/sorts/renders what it's given, it never recomputes the
analytical model.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from src.analytics import to_dataframe
from src.config import EXPLORER_EMBED_ROW_LIMIT
from src.fiscal import is_partial_fiscal_year
from src.schema import EnrichedTransaction

EXPLORER_COLUMNS = [
    "fiscal_year", "action_date", "recipient_name_raw", "normalized_supplier",
    "transaction_obligation_signed", "obligation_direction", "award_id_piid",
    "modification_number", "action_type_description", "transaction_description",
    "psc_code", "naics_code", "ai_spend_category", "ai_spend_subcategory",
    "classification_confidence", "review_status", "opportunity_flags", "data_quality_flags",
]


def _supplier_detail(df: pd.DataFrame, total_net: float) -> dict:
    detail: dict[str, dict] = {}
    for supplier, g in df.groupby("normalized_supplier"):
        annual = []
        for fy, gf in g.groupby("fiscal_year"):
            annual.append({
                "fiscal_year": int(fy),
                "net_obligations": float(gf["transaction_obligation_signed"].sum()),
            })
        annual.sort(key=lambda r: r["fiscal_year"])

        gross = float(g.loc[g["transaction_obligation_signed"] > 0, "transaction_obligation_signed"].sum())
        deob = float(-g.loc[g["transaction_obligation_signed"] < 0, "transaction_obligation_signed"].sum())
        net = float(g["transaction_obligation_signed"].sum())
        cat_mix = g.groupby("ai_spend_category")["transaction_obligation_signed"].sum().sort_values(ascending=False)
        offices = sorted(x for x in g["awarding_office"].dropna().unique().tolist())
        variants = sorted(g["recipient_name_raw"].unique().tolist())
        flags = sorted({f for row in g["data_quality_flags"] for f in row})

        detail[supplier] = {
            "total_net_obligations": net,
            "gross_positive_obligations": gross,
            "deobligations": deob,
            "transaction_count": int(len(g)),
            "unique_awards": int(g["award_id_piid"].nunique()),
            "annual": annual,
            "category_mix": [{"category": c, "net_obligations": float(v)} for c, v in cat_mix.items()],
            "awarding_offices": offices,
            "share_of_agency_obligations": (net / total_net) if total_net else 0.0,
            "raw_name_variants": variants,
            "resolution_confidence": float(g["supplier_resolution_confidence"].mean()),
            "resolution_evidence": sorted(set(g["supplier_resolution_evidence"].tolist()))[:5],
            "flags": flags,
        }
    return detail


def _kpi_drilldowns(df: pd.DataFrame, max_rows: int = 12) -> dict:
    """Backs the Executive Overview KPI tiles' "how does this number build
    up?" drill-down. The dollar-value KPIs (Net/Gross/Deobligations) are
    sums over every transaction, but the Transaction Explorer only embeds
    the most recent EXPLORER_EMBED_ROW_LIMIT rows -- not necessarily the
    largest ones -- so the largest contributors have to be computed here,
    over the full dataset, rather than filtered client-side from a capped
    subset that could miss them entirely.
    """
    if df.empty:
        return {"top_gross_transactions": [], "top_deobligation_transactions": []}

    def _rows(g: pd.DataFrame) -> list[dict]:
        return [{
            "action_date": r["action_date"].date().isoformat(),
            "supplier": r["normalized_supplier"],
            "award_id": r["award_id_piid"],
            "amount": float(r["transaction_obligation_signed"]),
        } for _, r in g.iterrows()]

    pos = df.loc[df["transaction_obligation_signed"] > 0].sort_values("transaction_obligation_signed", ascending=False).head(max_rows)
    neg = df.loc[df["transaction_obligation_signed"] < 0].sort_values("transaction_obligation_signed", ascending=True).head(max_rows)
    return {
        "top_gross_transactions": _rows(pos),
        "top_deobligation_transactions": _rows(neg),
    }


def _category_detail(df: pd.DataFrame) -> dict:
    detail: dict[str, dict] = {}
    for cat, g in df.groupby("ai_spend_category"):
        annual = []
        for fy, gf in g.groupby("fiscal_year"):
            annual.append({"fiscal_year": int(fy), "net_obligations": float(gf["transaction_obligation_signed"].sum())})
        annual.sort(key=lambda r: r["fiscal_year"])

        supplier_agg = g.groupby("normalized_supplier")["transaction_obligation_signed"].sum().sort_values(ascending=False)
        positive = supplier_agg.clip(lower=0)
        total = positive.sum()
        hhi = float(((positive / total * 100) ** 2).sum()) if total else 0.0
        n = len(supplier_agg)
        head_n = max(1, int(n * 0.10))
        tail_share = float(supplier_agg.iloc[head_n:].clip(lower=0).sum() / total) if total else 0.0

        detail[cat] = {
            "annual": annual,
            "unique_suppliers": int(g["normalized_supplier"].nunique()),
            "leading_suppliers": [{"supplier": s, "net_obligations": float(v)} for s, v in supplier_agg.head(10).items()],
            "concentration_hhi": hhi,
            "tail_spend_share": tail_share,
            "low_confidence_count": int((g["classification_confidence"] < 0.6).sum()),
            "needs_review_count": int((g["review_status"] == "NEEDS_REVIEW").sum()),
        }
    return detail


def _standout_suppliers(suppliers_detail: dict, max_results: int = 5) -> list[dict]:
    """Surfaces a short, evidence-based list of suppliers worth a second look --
    not a fraud or performance determination, just three neutral, disclosed
    signals computed from data already in `suppliers_detail`: spend
    concentration, deobligation share, and year-over-year swings. Each
    reason cites the exact supporting metric so a reviewer can check it,
    consistent with this project's rule that agents/heuristics never assert
    wrongdoing -- see src/agents/insights_agent.py.
    """
    candidates = []
    for name, d in suppliers_detail.items():
        gross = d["gross_positive_obligations"]
        deob = d["deobligations"]
        deob_rate = (deob / gross) if gross else 0.0
        annual = sorted(d["annual"], key=lambda r: r["fiscal_year"])
        yoy_pct = None
        yoy_from_fy = yoy_to_fy = None
        if len(annual) >= 2:
            prev, cur = annual[-2], annual[-1]
            if abs(prev["net_obligations"]) >= 50_000:
                yoy_pct = (cur["net_obligations"] - prev["net_obligations"]) / abs(prev["net_obligations"]) * 100
                yoy_from_fy, yoy_to_fy = prev["fiscal_year"], cur["fiscal_year"]

        reasons = []
        if deob >= 10_000 and deob_rate >= 0.05:
            reasons.append({
                "type": "deobligation_flag",
                "label": "Notable deobligations",
                "detail": (
                    f"${deob:,.0f} deobligated ({deob_rate * 100:.1f}% of gross positive obligations) -- "
                    "worth confirming these reflect ordinary contract modifications rather than a data issue."
                ),
            })
        if yoy_pct is not None and abs(yoy_pct) >= 75:
            direction = "growth" if yoy_pct > 0 else "decline"
            reasons.append({
                "type": f"rapid_{direction}",
                "label": f"Rapid year-over-year {direction}",
                "detail": (
                    f"Net obligations changed {yoy_pct:+.1f}% from FY{yoy_from_fy} to FY{yoy_to_fy} -- "
                    "worth confirming against the award record (new award, option exercise, or contract completion)."
                ),
            })

        candidates.append({
            "supplier": name,
            "net_obligations": d["total_net_obligations"],
            "concentration_pct": d["share_of_agency_obligations"] * 100,
            "transaction_count": d["transaction_count"],
            "unique_awards": d["unique_awards"],
            "reasons": reasons,
        })

    candidates.sort(key=lambda c: -c["concentration_pct"])
    standout = []
    seen = set()
    # Always surface the top 3 by spend concentration -- sheer size is itself
    # worth a look, flagged even with no other signal present.
    for c in candidates[:3]:
        c["reasons"] = [{
            "type": "high_concentration",
            "label": "High spend concentration",
            "detail": (
                f"${c['net_obligations']:,.0f} ({c['concentration_pct']:.1f}%) of total NASA net obligations "
                "in this dataset -- among the largest single-supplier shares."
            ),
        }] + c["reasons"]
        standout.append(c)
        seen.add(c["supplier"])
    # Fill remaining slots with any supplier flagged by deobligation/YoY
    # signals alone, ranked by concentration among that subset.
    for c in candidates:
        if len(standout) >= max_results:
            break
        if c["supplier"] in seen:
            continue
        if c["reasons"]:
            standout.append(c)
            seen.add(c["supplier"])
    return standout[:max_results]


def _award_rows(df: pd.DataFrame) -> list[dict]:
    """Per-contract-award (award_id_piid) aggregation shared by the full
    awards summary and the standout-awards signal detector below, so both
    compute the same numbers from a single pass over the data.
    """
    if df.empty:
        return []

    rows = []
    for award_id, g in df.groupby("award_id_piid"):
        if not award_id:
            continue
        g_sorted = g.sort_values("action_date")
        net = float(g["transaction_obligation_signed"].sum())
        gross = float(g.loc[g["transaction_obligation_signed"] > 0, "transaction_obligation_signed"].sum())
        deob = float(-g.loc[g["transaction_obligation_signed"] < 0, "transaction_obligation_signed"].sum())
        initial_amount = float(g_sorted.iloc[0]["transaction_obligation_signed"])
        first_date = g_sorted.iloc[0]["action_date"]
        first_date = first_date.date().isoformat() if pd.notna(first_date) else None
        mod_count = int(g["modification_number"].nunique())

        # Longest description is usually the most informative one on record.
        descriptions = [d for d in g["transaction_description"].tolist() if d]
        description = max(descriptions, key=len) if descriptions else ""

        supplier_counts = g["normalized_supplier"].value_counts()
        category_counts = g["ai_spend_category"].value_counts()

        rows.append({
            "award_id": str(award_id),
            "supplier": supplier_counts.idxmax() if not supplier_counts.empty else "Unknown",
            "category": category_counts.idxmax() if not category_counts.empty else "Uncategorized",
            "net_obligations": net,
            "gross_positive_obligations": gross,
            "deobligations": deob,
            "initial_amount": initial_amount,
            "first_date": first_date,
            "transaction_count": int(len(g)),
            "modification_count": mod_count,
            "description": description[:400],
        })
    return rows


def _award_summary(rows: list[dict], max_results: int = 300) -> list[dict]:
    """The full (well, top-N by value) ranked award list backing the
    Executive Overview's filterable "Top Contracts" table -- distinct from
    _standout_awards below, which is a small, signal-flagged subset, not a
    plain leaderboard. Capped at max_results (deep enough to cover any of
    the offered sort-by-metric views for a top-12 display) rather than
    embedding every award, to keep payload size reasonable on datasets with
    thousands of distinct awards.
    """
    ranked = sorted(rows, key=lambda r: -r["net_obligations"])[:max_results]
    return [
        {
            "award_id": r["award_id"],
            "supplier": r["supplier"],
            "category": r["category"],
            "net_obligations": r["net_obligations"],
            "deobligations": r["deobligations"],
            "transaction_count": r["transaction_count"],
            "modification_count": r["modification_count"],
        }
        for r in ranked
    ]


def _standout_awards(rows: list[dict], max_results: int = 5) -> list[dict]:
    """Same idea as _standout_suppliers, one level down: per-contract-award
    instead of per-supplier. Surfaces high-value awards and two neutral,
    evidence-based signals -- growth via modifications and deobligation
    share -- never a cost-overrun or performance claim, since a repo-CSV-
    ingested award has no ceiling/ordering-office data to compare against
    (only a live API award-detail lookup would have that). Reasons always
    cite the exact supporting metric.
    """
    candidates = []
    for r in rows:
        net, gross, deob = r["net_obligations"], r["gross_positive_obligations"], r["deobligations"]
        deob_rate = (deob / gross) if gross else 0.0
        initial_amount, mod_count = r["initial_amount"], r["modification_count"]

        growth_pct = None
        if r["transaction_count"] > 1 and abs(initial_amount) >= 50_000:
            growth_pct = (net - initial_amount) / abs(initial_amount) * 100

        reasons = []
        if deob >= 10_000 and deob_rate >= 0.05:
            reasons.append({
                "type": "deobligation_flag",
                "label": "Notable deobligations",
                "detail": (
                    f"${deob:,.0f} deobligated ({deob_rate * 100:.1f}% of gross positive obligations) -- "
                    "worth confirming these reflect ordinary contract modifications rather than a data issue."
                ),
            })
        if growth_pct is not None and growth_pct >= 75:
            reasons.append({
                "type": "cost_growth",
                "label": "Grew via modifications",
                "detail": (
                    f"Net obligations grew {growth_pct:+.0f}% from the first recorded transaction "
                    f"(${initial_amount:,.0f}) to ${net:,.0f} across {mod_count} modification(s) -- "
                    "worth confirming against the award's scope-change or ceiling record; this is not "
                    "evidence of a cost overrun on its own."
                ),
            })

        candidates.append({
            "award_id": r["award_id"],
            "supplier": r["supplier"],
            "category": r["category"],
            "net_obligations": net,
            "transaction_count": r["transaction_count"],
            "modification_count": mod_count,
            "description": r["description"],
            "reasons": reasons,
        })

    candidates.sort(key=lambda c: -c["net_obligations"])
    standout = []
    seen = set()
    for c in candidates[:3]:
        c["reasons"] = [{
            "type": "high_value",
            "label": "High contract value",
            "detail": f"${c['net_obligations']:,.0f} in net obligations across {c['transaction_count']} transaction(s) -- one of the largest contracts in this dataset.",
        }] + c["reasons"]
        standout.append(c)
        seen.add(c["award_id"])
    for c in candidates:
        if len(standout) >= max_results:
            break
        if c["award_id"] in seen:
            continue
        if c["reasons"]:
            standout.append(c)
            seen.add(c["award_id"])
    return standout[:max_results]


def _consolidation_opportunities(categories_detail: dict, max_results: int = 5) -> list[dict]:
    """Feature requested by the professor's review: proactively surface
    categories where spend is split across many suppliers with no dominant
    one, rather than only reacting when a *designated* preferred supplier is
    bypassed (supplier_check.py's job, in the general spend_agent engine).
    This is a fragmentation signal only -- it names no specific replacement
    vendor and computes no savings estimate, since we have no per-vendor
    unit-price or contract-tier data to back one. See PROJECT_SUMMARY.md.
    """
    MIN_CATEGORY_SPEND = 100_000
    MIN_SUPPLIERS = 3
    HHI_FRAGMENTED_THRESHOLD = 2500  # below this, no single supplier dominates (DOJ/FTC HHI convention: <1500 unconcentrated, 1500-2500 moderate, >2500 concentrated)

    candidates = []
    for category, d in categories_detail.items():
        total = sum(r["net_obligations"] for r in d["leading_suppliers"])
        if total < MIN_CATEGORY_SPEND or d["unique_suppliers"] < MIN_SUPPLIERS:
            continue
        if d["concentration_hhi"] >= HHI_FRAGMENTED_THRESHOLD:
            continue
        top = d["leading_suppliers"][0] if d["leading_suppliers"] else None
        top_share = (top["net_obligations"] / total) if (top and total) else 0.0
        candidates.append({
            "category": category,
            "total_net_obligations": total,
            "unique_suppliers": d["unique_suppliers"],
            "concentration_hhi": d["concentration_hhi"],
            "top_supplier": top["supplier"] if top else None,
            "top_supplier_share_pct": top_share * 100,
            "leading_suppliers": d["leading_suppliers"][:5],
            "detail": (
                f"${total:,.0f} in this category is split across {d['unique_suppliers']} suppliers; "
                f"the largest ({top['supplier'] if top else 'n/a'}) accounts for only {top_share * 100:.0f}% "
                f"(HHI={d['concentration_hhi']:.0f}, more fragmented than a concentrated category). "
                "Consolidating routine purchases onto fewer suppliers may create leverage for "
                "volume-based pricing -- this is a fragmentation signal, not a recommendation for "
                "a specific vendor, and not a savings estimate (no per-vendor unit-price data available)."
            ),
        })

    candidates.sort(key=lambda c: -c["total_net_obligations"])
    return candidates[:max_results]


def _duplicate_purchase_candidates(rows: list[dict], max_results: int = 5) -> list[dict]:
    """Feature requested by the professor's review, from the "school chair
    pass" example: budget rules sometimes drive a second, separate purchase
    instead of one consolidated one. Flags pairs of *separate* awards
    (contract modifications on the same award are already covered by the
    "grew via modifications" signal in _standout_awards) to the same
    supplier, same category, similar dollar amount, close in time --
    plausible incremental/duplicate procurement, never asserted as waste.
    """
    AMOUNT_TOLERANCE = 0.30  # within 30% of each other
    MIN_AMOUNT = 5_000
    # Above this, two same-supplier awards close together are more likely
    # parallel program funding to a major prime than an administrative
    # duplicate -- this signal is aimed at the "school chair pass" pattern
    # (mundane, repeated small purchases), not billion-dollar contracts.
    MAX_AMOUNT = 2_000_000
    MAX_DAYS_APART = 120

    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        if not r["first_date"] or not (MIN_AMOUNT <= abs(r["net_obligations"]) <= MAX_AMOUNT):
            continue
        groups.setdefault((r["supplier"], r["category"]), []).append(r)

    candidates = []
    seen_awards: set[str] = set()
    for (supplier, category), awards in groups.items():
        if len(awards) < 2:
            continue
        awards = sorted(awards, key=lambda r: r["first_date"])
        for i in range(len(awards)):
            for j in range(i + 1, len(awards)):
                a, b = awards[i], awards[j]
                if a["award_id"] in seen_awards or b["award_id"] in seen_awards:
                    continue
                days_apart = (dt.date.fromisoformat(b["first_date"]) - dt.date.fromisoformat(a["first_date"])).days
                if days_apart > MAX_DAYS_APART:
                    continue
                bigger, smaller = max(a["net_obligations"], b["net_obligations"]), min(a["net_obligations"], b["net_obligations"])
                if bigger <= 0 or (bigger - smaller) / bigger > AMOUNT_TOLERANCE:
                    continue
                candidates.append({
                    "pair_id": "::".join(sorted([a["award_id"], b["award_id"]])),
                    "supplier": supplier,
                    "category": category,
                    "award_id_a": a["award_id"], "award_id_b": b["award_id"],
                    "amount_a": a["net_obligations"], "amount_b": b["net_obligations"],
                    "date_a": a["first_date"], "date_b": b["first_date"],
                    "days_apart": days_apart,
                    "combined_value": a["net_obligations"] + b["net_obligations"],
                    "detail": (
                        f"Two separate awards to {supplier} in {category}, {days_apart} day(s) apart, "
                        f"for similar amounts (${a['net_obligations']:,.0f} on {a['first_date']} and "
                        f"${b['net_obligations']:,.0f} on {b['first_date']}) -- worth checking whether this "
                        "reflects one need that could have been a single consolidated purchase (e.g. a "
                        "budget-cycle-driven incremental buy) rather than genuinely separate needs. Not "
                        "evidence of wasteful spending on its own."
                    ),
                })
                seen_awards.add(a["award_id"])
                seen_awards.add(b["award_id"])

    candidates.sort(key=lambda c: -c["combined_value"])
    return candidates[:max_results]


def build_payload(
    transactions: list[EnrichedTransaction],
    analytics: dict,
    insights_findings: list[dict],
    manifest: dict,
    processing_mode: str,
    today: dt.date | None = None,
) -> dict:
    today = today or dt.date.today()
    df = to_dataframe(transactions)

    total_net = analytics.get("totals", {}).get("net_obligations", 0.0)

    if df.empty:
        explorer_rows = []
        suppliers_detail = {}
        categories_detail = {}
        min_date = max_date = None
    else:
        min_date = df["action_date"].min().date().isoformat()
        max_date = df["action_date"].max().date().isoformat()
        explorer_df = df.sort_values("action_date", ascending=False)
        embedded = explorer_df.head(EXPLORER_EMBED_ROW_LIMIT)
        explorer_rows = embedded[EXPLORER_COLUMNS].assign(
            action_date=embedded["action_date"].dt.date.astype(str)
        ).to_dict("records")
        suppliers_detail = _supplier_detail(df, total_net)
        categories_detail = _category_detail(df)

    award_rows = _award_rows(df)

    review_status_flag = analytics.get("current_fiscal_year")
    partial_year_warning = is_partial_fiscal_year(review_status_flag, today) if review_status_flag else False

    payload = {
        "meta": {
            "title": "NASA Procurement Intelligence Dashboard",
            "disclosure": "Unofficial educational project. Not affiliated with or endorsed by NASA.",
            "data_period_start": min_date,
            "data_period_end": max_date,
            "last_refresh_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "transaction_count": len(transactions),
            "processing_mode": processing_mode,
            "source": manifest.get("source", "unknown"),
            "explorer_row_limit": EXPLORER_EMBED_ROW_LIMIT,
            "explorer_embedded_count": len(explorer_rows),
            "current_fiscal_year": review_status_flag,
            "current_fiscal_year_is_partial": partial_year_warning,
            "note": "Net obligations reflect signed transaction amounts and are NOT the same as payments, expenditures, or outlays.",
        },
        "manifest": manifest,
        "analytics": analytics,
        "insights": insights_findings,
        "explorer_rows": explorer_rows,
        "suppliers_detail": suppliers_detail,
        "categories_detail": categories_detail,
        "standout_suppliers": _standout_suppliers(suppliers_detail),
        "standout_awards": _standout_awards(award_rows),
        "awards_summary": _award_summary(award_rows),
        "consolidation_opportunities": _consolidation_opportunities(categories_detail),
        "duplicate_purchase_candidates": _duplicate_purchase_candidates(award_rows),
        "kpi_drilldowns": _kpi_drilldowns(df),
    }
    return payload
