"""Builds the single JSON payload embedded in the self-contained dashboard.

All aggregation happens here, in Python, before the HTML is generated -- the
browser only filters/sorts/renders what it's given, it never recomputes the
analytical model.
"""
from __future__ import annotations

import datetime as dt
import json

import pandas as pd

from src.analytics import to_dataframe
from src.config import EXPLORER_EMBED_ROW_LIMIT, MISUSE_EXCLUDED_PSC_PATH
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
    """Per-supplier rollup backing the Supplier Analysis tab.

    `annual` carries the full metric set per fiscal year, not just net
    obligations, so the dashboard's Timeframe range control can scope this
    tab's KPI tiles instead of leaving them stuck at all-time. Net, gross,
    deobligations and transaction count sum exactly across a range; unique
    awards does not (an award active in three of the selected years is
    counted three times), and the UI discloses that rather than presenting
    the sum as a distinct count.

    Vectorized rather than looping per supplier -- _standout_by_range calls
    this once per fiscal-year range.
    """
    detail: dict[str, dict] = {}
    if df.empty:
        return detail

    d = df.copy()
    amt = d["transaction_obligation_signed"]
    d["_pos"] = amt.clip(lower=0)
    d["_neg"] = (-amt).clip(lower=0)

    totals = d.groupby("normalized_supplier", sort=False).agg(
        total_net_obligations=("transaction_obligation_signed", "sum"),
        gross_positive_obligations=("_pos", "sum"),
        deobligations=("_neg", "sum"),
        transaction_count=("transaction_obligation_signed", "size"),
        unique_awards=("award_id_piid", "nunique"),
        resolution_confidence=("supplier_resolution_confidence", "mean"),
    )

    per_year = d.groupby(["normalized_supplier", "fiscal_year"], sort=True).agg(
        net_obligations=("transaction_obligation_signed", "sum"),
        gross_positive_obligations=("_pos", "sum"),
        deobligations=("_neg", "sum"),
        transaction_count=("transaction_obligation_signed", "size"),
        unique_awards=("award_id_piid", "nunique"),
    )
    annual_by_supplier: dict[str, list[dict]] = {}
    for (supplier, fy), r in per_year.iterrows():
        annual_by_supplier.setdefault(supplier, []).append({
            "fiscal_year": int(fy),
            "net_obligations": float(r.net_obligations),
            "gross_positive_obligations": float(r.gross_positive_obligations),
            "deobligations": float(r.deobligations),
            "transaction_count": int(r.transaction_count),
            "unique_awards": int(r.unique_awards),
        })

    cat = d.groupby(["normalized_supplier", "ai_spend_category"], sort=False)["transaction_obligation_signed"].sum()
    cat = cat.sort_values(ascending=False)
    cat_by_supplier: dict[str, list[dict]] = {}
    for (supplier, category), v in cat.items():
        cat_by_supplier.setdefault(supplier, []).append({"category": category, "net_obligations": float(v)})

    offices = d.dropna(subset=["awarding_office"]).groupby("normalized_supplier")["awarding_office"].unique()
    variants = d.groupby("normalized_supplier")["recipient_name_raw"].unique()
    evidence = d.groupby("normalized_supplier")["supplier_resolution_evidence"].unique()
    flags = d.groupby("normalized_supplier")["data_quality_flags"].agg(
        lambda rows: sorted({f for row in rows for f in row})
    )

    for supplier, r in totals.iterrows():
        net = float(r.total_net_obligations)
        detail[supplier] = {
            "total_net_obligations": net,
            "gross_positive_obligations": float(r.gross_positive_obligations),
            "deobligations": float(r.deobligations),
            "transaction_count": int(r.transaction_count),
            "unique_awards": int(r.unique_awards),
            "annual": annual_by_supplier.get(supplier, []),
            "category_mix": cat_by_supplier.get(supplier, []),
            "awarding_offices": sorted(offices[supplier].tolist()) if supplier in offices.index else [],
            "share_of_agency_obligations": (net / total_net) if total_net else 0.0,
            "raw_name_variants": sorted(variants[supplier].tolist()) if supplier in variants.index else [],
            "resolution_confidence": float(r.resolution_confidence),
            "resolution_evidence": sorted(set(evidence[supplier].tolist()))[:5] if supplier in evidence.index else [],
            "flags": flags[supplier] if supplier in flags.index else [],
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
    """Per-category rollup backing the Categories & Opportunities tab.

    Like `_supplier_detail`, `annual` carries the metrics that sum cleanly
    across a fiscal-year range (net obligations, transaction count) plus
    per-year supplier and review counts, so the Timeframe control can scope
    this tab's KPI tiles. Concentration (HHI) and tail-spend share are
    deliberately NOT broken out per year: both are ratios over the whole
    supplier distribution within the scope, and averaging or summing yearly
    values would not reproduce the range's real figure. Those two stay
    all-time and the UI says so.
    """
    detail: dict[str, dict] = {}
    for cat, g in df.groupby("ai_spend_category"):
        annual = []
        for fy, gf in g.groupby("fiscal_year"):
            annual.append({
                "fiscal_year": int(fy),
                "net_obligations": float(gf["transaction_obligation_signed"].sum()),
                "transaction_count": int(len(gf)),
                "unique_suppliers": int(gf["normalized_supplier"].nunique()),
                "low_confidence_count": int((gf["classification_confidence"] < 0.6).sum()),
                "needs_review_count": int((gf["review_status"] == "NEEDS_REVIEW").sum()),
            })
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


def _modal_value(d: pd.DataFrame, key: str, value_col: str, fallback: str) -> pd.Series:
    """Most frequent `value_col` per `key`, ties broken by first occurrence --
    the vectorized equivalent of `g[value_col].value_counts().idxmax()` per
    group, which is far too slow to run once per award on a 142k-row frame.
    """
    counts = d.groupby([key, value_col], sort=False).size().reset_index(name="_n")
    counts = counts.sort_values("_n", ascending=False, kind="mergesort").drop_duplicates(key)
    return counts.set_index(key)[value_col].fillna(fallback)


def _award_rows(df: pd.DataFrame) -> list[dict]:
    """Per-contract-award (award_id_piid) aggregation shared by the full
    awards summary and the standout-awards signal detector below, so both
    compute the same numbers from a single pass over the data.

    Written as vectorized pandas aggregations rather than a Python loop over
    groups: _standout_by_range calls this once per fiscal-year range (28 of
    them on a 7-year dataset), and at 41k awards the per-group loop was the
    single largest cost in the whole build.
    """
    if df.empty:
        return []

    d = df[df["award_id_piid"].notna()].copy()
    d["award_id_piid"] = d["award_id_piid"].astype(str)
    d = d[d["award_id_piid"] != ""]
    if d.empty:
        return []

    amt = d["transaction_obligation_signed"]
    d["_pos"] = amt.clip(lower=0)
    d["_neg"] = (-amt).clip(lower=0)

    # Longest description is usually the most informative one on record.
    # Missing values load as float NaN, so coerce to str before measuring --
    # NaN is truthy in Python and would otherwise survive a plain filter and
    # crash max(..., key=len) with "object of type 'float' has no len()".
    # Resolved BEFORE the sort below so length ties break on original row
    # order, matching what `max(descriptions, key=len)` picked.
    desc = d["transaction_description"].where(d["transaction_description"].apply(lambda x: isinstance(x, str)), "")
    d["_desc"] = desc
    d["_desc_len"] = desc.str.len()
    longest_idx = d.groupby("award_id_piid", sort=False)["_desc_len"].idxmax()
    longest_desc = d.loc[longest_idx].set_index("award_id_piid")["_desc"]

    # Sorting once lets `.first()` stand in for "earliest transaction on this
    # award" without re-sorting inside every group.
    d = d.sort_values(["award_id_piid", "action_date"], kind="mergesort")
    g = d.groupby("award_id_piid", sort=False)

    agg = g.agg(
        net_obligations=("transaction_obligation_signed", "sum"),
        gross_positive_obligations=("_pos", "sum"),
        deobligations=("_neg", "sum"),
        initial_amount=("transaction_obligation_signed", "first"),
        first_date=("action_date", "first"),
        transaction_count=("transaction_obligation_signed", "size"),
        modification_count=("modification_number", "nunique"),
    )

    agg["description"] = longest_desc.reindex(agg.index).fillna("")

    agg["supplier"] = _modal_value(d, "award_id_piid", "normalized_supplier", "Unknown").reindex(agg.index).fillna("Unknown")
    agg["category"] = _modal_value(d, "award_id_piid", "ai_spend_category", "Uncategorized").reindex(agg.index).fillna("Uncategorized")

    first_dates = agg["first_date"]
    return [
        {
            "award_id": str(award_id),
            "supplier": str(r.supplier),
            "category": str(r.category),
            "net_obligations": float(r.net_obligations),
            "gross_positive_obligations": float(r.gross_positive_obligations),
            "deobligations": float(r.deobligations),
            "initial_amount": float(r.initial_amount),
            "first_date": (fd.date().isoformat() if pd.notna(fd) else None),
            "transaction_count": int(r.transaction_count),
            "modification_count": int(r.modification_count),
            "description": str(r.description)[:400],
        }
        for (award_id, r), fd in zip(agg.iterrows(), first_dates)
    ]


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


def _standout_by_range(df: pd.DataFrame, embedded_fiscal_years: list[int], max_results: int = 5) -> dict:
    """Precomputes standout_suppliers/standout_awards for every contiguous
    fiscal-year range among the embedded years (e.g. 7 embedded years ->
    7*8/2 = 28 range combinations, keyed "{from_fy}-{to_fy}"), so the
    dashboard's header Timeframe range control can look one up instantly
    client-side -- no client-side recomputation of the signal-detection
    logic, and no falling back to the all-time view when a narrower range
    is selected. Each range's concentration % (used by the "high spend
    concentration" signal) is computed against that range's own total net
    obligations, not the dataset-wide total, so it reflects share-of-spend
    within the selected window.
    """
    result: dict[str, dict] = {}
    if df.empty or not embedded_fiscal_years:
        return result
    years = sorted(set(embedded_fiscal_years))
    for i, from_fy in enumerate(years):
        for to_fy in years[i:]:
            key = f"{from_fy}-{to_fy}"
            sub = df[(df["fiscal_year"] >= from_fy) & (df["fiscal_year"] <= to_fy)]
            if sub.empty:
                result[key] = {"standout_suppliers": [], "standout_awards": []}
                continue
            range_total_net = float(sub["transaction_obligation_signed"].sum())
            range_suppliers_detail = _supplier_detail(sub, range_total_net)
            range_award_rows = _award_rows(sub)
            result[key] = {
                "standout_suppliers": _standout_suppliers(range_suppliers_detail, max_results),
                "standout_awards": _standout_awards(range_award_rows, max_results),
            }
    return result


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


_NOT_COMPETED_MARKERS = ("NOT COMPETED", "NOT AVAILABLE FOR COMPETITION")


def _load_excluded_psc() -> dict:
    """Loads the Misuse Protection PSC set-aside list. Missing/unreadable
    config means "exclude nothing" -- the screen still works, it just has
    more noise in it, which is the safe direction to fail."""
    try:
        raw = json.loads(MISUSE_EXCLUDED_PSC_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {"label": "", "codes": [], "prefixes": []}
    return {
        "label": raw.get("label", ""),
        "codes": [c["code"].upper() for c in raw.get("codes", []) if c.get("code")],
        "prefixes": [p["prefix"].upper() for p in raw.get("prefixes", []) if p.get("prefix")],
        "reasons": (
            [{"code": c["code"], "why": c.get("why", "")} for c in raw.get("codes", [])]
            + [{"code": p["prefix"] + "*", "why": p.get("why", "")} for p in raw.get("prefixes", [])]
        ),
    }


def _bid_competition_review(
    df: pd.DataFrame,
    threshold: float = 350_000.0,
    max_suppliers: int = 25,
    max_awards_per_supplier: int = 60,
) -> dict:
    """Surfaces suppliers whose awards *below* `threshold` are concentrated
    in single-offer or non-competed procurements -- a "structuring" signal
    reviewers watch for (splitting one larger need into several
    below-threshold awards to avoid the competition requirements that kick
    in above it), not a fraud finding. A single-bid or non-competed award
    under a threshold like this is routine and often fully legitimate
    (Simplified Acquisition Procedures exist for exactly this range, and
    programs like 8(a) sole-source are lawful by design) -- this only flags
    *concentration* of that pattern for a human to look at, and always shows
    the set-aside context (e.g. "8(A) SOLE SOURCE") alongside each award so
    a reviewer isn't looking at the number in isolation.

    Awards whose PSC identifies a proprietary software license (see
    config/misuse_excluded_psc.json) are set aside from the ranking by
    default: a single offer for a named product only that vendor sells is
    the expected outcome, not a signal, and leaving them in buried the
    genuinely irregular patterns under routine license renewals. They are
    counted and reported separately rather than dropped, so the screen never
    silently hides a supplier.

    Needs award-detail fields (number_of_offers_received,
    extent_competed_description, current_award_amount) that only exist when
    that per-award API call was actually made -- large multi-year pulls in
    this project skip it for speed (see README "award-detail enrichment").
    Returns {"available": False, ...} rather than an empty/misleading table
    when none of that data is present in this build.
    """
    excluded = _load_excluded_psc()
    empty = {
        "available": False, "threshold": threshold, "awards_total": 0,
        "awards_with_detail": 0, "suppliers": [], "excluded_psc": excluded,
        "set_aside": {"supplier_count": 0, "award_count": 0, "suppliers": []},
    }
    if df.empty or "award_id_piid" not in df.columns:
        return empty

    # Vectorized award-level rollup. The previous implementation looped in
    # Python over 41k groupby groups, which dominated build time; this does
    # the same work as a handful of pandas aggregations.
    d = df[df["award_id_piid"].notna() & (df["award_id_piid"].astype(str) != "")].copy()
    if d.empty:
        return empty

    def _first_col(col: str):
        return d.groupby("award_id_piid")[col].first() if col in d.columns else None

    grouped = d.groupby("award_id_piid")
    net = grouped["transaction_obligation_signed"].sum()
    awards = pd.DataFrame({"net": net})

    offers = d.dropna(subset=["number_of_offers_received"]).groupby("award_id_piid")["number_of_offers_received"].first() \
        if "number_of_offers_received" in d.columns else pd.Series(dtype=float)
    extent = d.dropna(subset=["extent_competed_description"]).groupby("award_id_piid")["extent_competed_description"].first() \
        if "extent_competed_description" in d.columns else pd.Series(dtype=object)
    set_aside = d.dropna(subset=["set_aside_type_description"]).groupby("award_id_piid")["set_aside_type_description"].first() \
        if "set_aside_type_description" in d.columns else pd.Series(dtype=object)
    cur_amt = d.dropna(subset=["current_award_amount"]).groupby("award_id_piid")["current_award_amount"].first() \
        if "current_award_amount" in d.columns else pd.Series(dtype=float)
    detail_ok = grouped["award_detail_available"].any() if "award_detail_available" in d.columns else pd.Series(False, index=awards.index)
    psc = _first_col("psc_code")
    supplier = grouped["normalized_supplier"].agg(lambda s: s.mode().iat[0] if not s.mode().empty else "Unknown")

    awards["num_offers"] = offers
    awards["extent_competed"] = extent
    awards["set_aside"] = set_aside
    awards["value"] = cur_amt.reindex(awards.index).fillna(awards["net"])
    awards["detail_available"] = detail_ok.reindex(awards.index).fillna(False)
    awards["psc"] = (psc.reindex(awards.index) if psc is not None else pd.Series("", index=awards.index)).fillna("")
    awards["supplier"] = supplier

    awards_total = int(len(awards))
    detailed = awards[awards["detail_available"].astype(bool) & awards["num_offers"].notna()]
    if detailed.empty:
        return {**empty, "awards_total": awards_total}

    ext_upper = detailed["extent_competed"].fillna("").astype(str).str.upper()
    not_competed = ext_upper.str.contains("|".join(_NOT_COMPETED_MARKERS), regex=True)
    detailed = detailed.assign(low_competition=(detailed["num_offers"] <= 1) | not_competed)

    psc_upper = detailed["psc"].astype(str).str.upper()
    is_excluded = psc_upper.isin(excluded["codes"])
    for pref in excluded["prefixes"]:
        is_excluded = is_excluded | psc_upper.str.startswith(pref)
    detailed = detailed.assign(psc_excluded=is_excluded)

    # Total contracts held by each supplier at any value -- context for
    # whether flagged awards are their whole book of business or a sliver.
    total_awards_by_supplier = df.groupby("normalized_supplier")["award_id_piid"].nunique().to_dict()
    detailed_awards_by_supplier = detailed.groupby("supplier").size().to_dict()

    sub = detailed[detailed["value"] < threshold]
    ranked_pool = sub[~sub["psc_excluded"]]
    set_aside_pool = sub[sub["psc_excluded"] & sub["low_competition"]]

    def _award_records(g: pd.DataFrame) -> list[dict]:
        g = g.sort_values("value", ascending=False).head(max_awards_per_supplier)
        return [
            {
                "award_id": str(idx), "value": float(r["value"]),
                "num_offers": None if pd.isna(r["num_offers"]) else int(r["num_offers"]),
                "extent_competed": None if pd.isna(r["extent_competed"]) else str(r["extent_competed"]),
                "set_aside": None if pd.isna(r["set_aside"]) else str(r["set_aside"]),
                "psc": str(r["psc"]) or None,
                "low_competition": bool(r["low_competition"]),
            }
            for idx, r in g.iterrows()
        ]

    suppliers = []
    for name, g in ranked_pool.groupby("supplier"):
        low_n = int(g["low_competition"].sum())
        if not low_n:
            continue
        suppliers.append({
            "supplier": str(name),
            "sub_threshold_award_count": int(len(g)),
            "low_competition_award_count": low_n,
            "low_competition_share": low_n / len(g),
            "total_sub_threshold_value": float(g["value"].sum()),
            "total_award_count": int(total_awards_by_supplier.get(name, len(g))),
            "awards_with_detail": int(detailed_awards_by_supplier.get(name, len(g))),
            "awards_truncated": bool(len(g) > max_awards_per_supplier),
            "awards": _award_records(g),
        })
    suppliers.sort(key=lambda s: (-s["low_competition_share"], -s["sub_threshold_award_count"]))

    set_aside_suppliers = []
    for name, g in set_aside_pool.groupby("supplier"):
        set_aside_suppliers.append({
            "supplier": str(name),
            "award_count": int(len(g)),
            "value": float(g["value"].sum()),
        })
    set_aside_suppliers.sort(key=lambda s: -s["award_count"])

    return {
        "available": True, "threshold": threshold,
        "awards_total": awards_total, "awards_with_detail": int(len(detailed)),
        "suppliers": suppliers[:max_suppliers],
        "excluded_psc": excluded,
        "set_aside": {
            "supplier_count": len(set_aside_suppliers),
            "award_count": int(len(set_aside_pool)),
            "value": float(set_aside_pool["value"].sum()) if len(set_aside_pool) else 0.0,
            "suppliers": set_aside_suppliers[:15],
        },
    }


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
    embedded_fiscal_years = sorted({r["fiscal_year"] for r in analytics.get("annual", [])})
    standout_by_range = _standout_by_range(df, embedded_fiscal_years)

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
        "standout_by_range": standout_by_range,
        "awards_summary": _award_summary(award_rows),
        "consolidation_opportunities": _consolidation_opportunities(categories_detail),
        "duplicate_purchase_candidates": _duplicate_purchase_candidates(award_rows),
        "bid_competition_review": _bid_competition_review(df),
        "kpi_drilldowns": _kpi_drilldowns(df),
    }
    return payload
