# -*- coding: utf-8 -*-
import json

FDIR = r"C:\finances\DoD_v1\sba_loans\fonts"
def b64(name):
    with open(rf"{FDIR}\{name}.b64") as f:
        return f.read().strip()
SANS400, SANS500, SANS600 = b64("sans400"), b64("sans500"), b64("sans600")
MONO400, MONO500 = b64("mono400"), b64("mono500")
SERIF600 = b64("serif600")

with open(r"C:\finances\DoD_v2\data\payload.json") as f:
    P = json.load(f)
with open(r"C:\finances\DoD_v2\data\insights.json") as f:
    INSIGHTS = json.load(f)
with open(r"C:\finances\DoD_v2\data\data_quality_flags.json") as f:
    DQ = json.load(f)

# No-bid data, reused from DoD_v1
with open(r"C:\finances\DoD_v1\sba_loans\_singlebid_final_fullrange.json") as f:
    SB = json.load(f)
with open(r"C:\finances\DoD_v1\sba_loans\_drilldown_final_fullrange.json") as f:
    DD = json.load(f)
with open(r"C:\finances\DoD_v1\sba_loans\_singlebid_detail_export_fullrange.json", encoding="utf-8") as f:
    CD_RECORDS = json.load(f)

# Quality-of-life-by-branch analysis
with open(r"C:\finances\DoD_v2\data\qol_payload.json") as f:
    QOL = json.load(f)

# Sole-source pricing risk + foreign vendor spend analysis
with open(r"C:\finances\DoD_v2\data\risk_payload.json") as f:
    RISK = json.load(f)

A = P["analytics"]
TOTALS = A["totals"]

def fmt_b(n):
    if abs(n) < 1e9:
        return f"${n/1e6:,.1f}M"
    if abs(n) < 1e12:
        return f"${n/1e9:,.1f}B"
    return f"${n/1e12:,.2f}T"

def fmt_full(n):
    return f"${n:,.0f}"

# Trim large embeds to keep page size reasonable
TOP_SUPPLIERS = A["top_suppliers"][:25]
AWARDS_SUMMARY = P["awards_summary"][:150]
CATEGORIES_DETAIL = P["categories_detail"]
SUPPLIERS_DETAIL_TRIMMED = {k: v for k, v in list(P["suppliers_detail"].items())
                             if v["total_net_obligations"] >= 5_000_000}  # cap payload size

# Explorer rows: most recent 2000 awards by action date (mirrors v3's EXPLORER_EMBED_ROW_LIMIT concept)
import pandas as pd
df = pd.read_pickle(r"C:\finances\DoD_v2\data\enriched.pkl")
explorer_df = df.sort_values("action_date", ascending=False).head(2000)
EXPLORER_ROWS = explorer_df[[
    "fiscal_year", "action_date", "recipient_name_raw", "normalized_supplier", "amount",
    "award_id_piid", "transaction_description", "product_or_service_code_description",
    "naics_description", "ai_spend_category", "ai_spend_subcategory", "classification_confidence",
    "extent_competed", "awarding_sub_agency_name",
]].copy()
EXPLORER_ROWS["action_date"] = EXPLORER_ROWS["action_date"].dt.date.astype(str)
EXPLORER_ROWS = EXPLORER_ROWS.rename(columns={"amount": "net_obligations"}).to_dict("records")

TOTAL_EXPLORER_ROWS = len(df)

print("Payload sizes:", "suppliers_detail_trimmed:", len(SUPPLIERS_DETAIL_TRIMMED),
      "explorer_rows:", len(EXPLORER_ROWS), "awards_summary:", len(AWARDS_SUMMARY),
      "categories:", len(CATEGORIES_DETAIL))

payload_json = json.dumps({
    "meta": P["meta"],
    "totals": TOTALS,
    "annual": A["annual"],
    "year_over_year": A["year_over_year"],
    "category_breakdown": A["category_breakdown"],
    "top_suppliers": TOP_SUPPLIERS,
    "concentration": A["concentration"],
    "tail_spend_share": A["tail_spend_share"],
    "notable_category_yoy_changes": A["notable_category_yoy_changes"],
    "concentration_by_year": A["concentration_by_year"],
    "standout_suppliers": P["standout_suppliers"],
    "standout_awards": P["standout_awards"],
    "consolidation_opportunities": P["consolidation_opportunities"],
    "duplicate_purchase_candidates": P["duplicate_purchase_candidates"],
    "categories_detail": CATEGORIES_DETAIL,
    "suppliers_detail": SUPPLIERS_DETAIL_TRIMMED,
    "awards_summary": AWARDS_SUMMARY,
    "insights": INSIGHTS,
    "data_quality": DQ,
})
explorer_json = json.dumps(EXPLORER_ROWS)
nobid_rollup_json = json.dumps(SB["vendor_rollup"])
nobid_drilldown_json = json.dumps(DD["rows"])
nobid_branch_json = json.dumps(DD["branch_counts_near"])
nobid_detail_json = json.dumps(CD_RECORDS)

print(f"Approx payload size: {len(payload_json)/1e6:.1f}MB, explorer: {len(explorer_json)/1e6:.1f}MB, nobid detail: {len(nobid_detail_json)/1e6:.1f}MB")

# ============================================================
# STATIC CONTEXT FOR TEMPLATE
# (field names verified directly against build_analytics.py's actual
# output shapes and the no-bid JSON files -- not assumed from memory)
# ============================================================
CATEGORY_BREAKDOWN = A["category_breakdown"]  # list: category/subcategory/net_obligations/transaction_count/unique_suppliers
CATEGORIES_DETAIL_DICT = P["categories_detail"]  # dict keyed by category: annual/unique_suppliers/leading_suppliers/concentration_hhi/tail_spend_share/low_confidence_count

INSIGHTS_HTML = "".join(
    f'<div class="finding"><strong>{i["title"]}.</strong> {i["finding"]}</div>'
    for i in INSIGHTS
)

def supplier_pct(net_obligations):
    return (net_obligations / TOTALS["net_obligations"] * 100) if TOTALS["net_obligations"] else 0.0

TOP_SUPPLIER_ROWS_HTML = "".join(
    f'<div class="bar-row"><div class="bar-name" title="{s["normalized_supplier"]}">{s["normalized_supplier"]}</div>'
    f'<div class="bar-track"><div class="bar-fill" style="width:{max(s["net_obligations"]/TOP_SUPPLIERS[0]["net_obligations"]*100,1):.1f}%"></div></div>'
    f'<div class="bar-figures"><span>{fmt_b(s["net_obligations"])}</span><span class="bar-pct">{supplier_pct(s["net_obligations"]):.1f}%</span></div></div>'
    for s in TOP_SUPPLIERS[:15]
)

CAT_ROWS_HTML = "".join(
    f'<div class="bar-row"><div class="bar-name" title="{c["category"]} / {c["subcategory"]}">{c["category"]}</div>'
    f'<div class="bar-track"><div class="bar-fill" style="width:{max(c["net_obligations"]/CATEGORY_BREAKDOWN[0]["net_obligations"]*100,1):.1f}%"></div></div>'
    f'<div class="bar-figures"><span>{fmt_b(c["net_obligations"])}</span><span class="bar-pct">{supplier_pct(c["net_obligations"]):.1f}%</span></div></div>'
    for c in CATEGORY_BREAKDOWN[:14]
)

ANNUAL_MAX = max(y["net_obligations"] for y in A["annual"])
ANNUAL_CHART_HTML = "".join(
    f'<div class="month-col{" is-peak" if y["net_obligations"]==ANNUAL_MAX else ""}">'
    f'<div class="month-bar-track"><div class="month-bar" style="height:{max(y["net_obligations"]/ANNUAL_MAX*100,2):.1f}%"></div></div>'
    f'<div class="month-label">FY{y["fiscal_year"]}</div><div class="month-amt">{fmt_b(y["net_obligations"])}</div></div>'
    for y in A["annual"]
)

CONC_MAX = max(y["top5_share"] for y in A["concentration_by_year"])
CONC_CHART_HTML = "".join(
    f'<div class="month-col"><div class="month-bar-track"><div class="month-bar" style="height:{max(y["top5_share"]/CONC_MAX*100,2):.1f}%"></div></div>'
    f'<div class="month-label">FY{y["fiscal_year"]}</div><div class="month-amt">{y["top5_share"]*100:.0f}%</div></div>'
    for y in A["concentration_by_year"]
)

def standout_supplier_card(s):
    reasons = "".join(f'<span class="reason-pill">{r["label"]}</span>' for r in s.get("reasons", []))
    return (f'<div class="card"><div class="card-title">{s["supplier"]}</div>'
            f'<div class="card-amt">{fmt_b(s["net_obligations"])}</div>'
            f'<div style="font-size:12px;color:var(--ink-muted)">{s["concentration_pct"]:.1f}% of total, {s["unique_awards"]:,} awards</div>'
            f'<div>{reasons}</div></div>')

STANDOUT_SUPPLIER_CARDS = "".join(standout_supplier_card(s) for s in P["standout_suppliers"])

def standout_award_card(a):
    reason_text = a["reasons"][0]["detail"] if a.get("reasons") else ""
    return (f'<div class="card"><div class="card-title">{a["award_id"]} &mdash; {a["supplier"]}</div>'
            f'<div class="card-amt">{fmt_b(a["net_obligations"])}</div>'
            f'<div style="font-size:12px;color:var(--ink-muted)">{a.get("category","")}</div>'
            f'<div style="font-size:11.5px;color:var(--ink-faint)">{reason_text}</div></div>')

STANDOUT_AWARD_CARDS = "".join(standout_award_card(a) for a in P["standout_awards"])

def opp_card(c):
    return (f'<div class="card"><div class="card-title">{c["category"]}</div>'
            f'<div class="card-amt">{fmt_b(c["total_net_obligations"])}</div>'
            f'<div style="font-size:12px;color:var(--ink-muted)">HHI {c["concentration_hhi"]:.0f} &middot; {c["unique_suppliers"]} suppliers</div>'
            f'<div style="font-size:11.5px;color:var(--ink-faint)">{c["detail"]}</div></div>')

CONSOLIDATION_CARDS = "".join(opp_card(c) for c in P["consolidation_opportunities"])

def dup_card(d):
    bigger = max(d["amount_a"], d["amount_b"])
    pct_diff = (abs(d["amount_a"] - d["amount_b"]) / bigger * 100) if bigger else 0.0
    return (f'<div class="card"><div class="card-title">{d["supplier"]}</div>'
            f'<div style="font-size:12px;color:var(--ink-muted)">{d["category"]}</div>'
            f'<div style="font-size:11.5px;font-family:&quot;IBM Plex Mono&quot;,monospace">{d["award_id_a"]} {fmt_b(d["amount_a"])} &harr; {d["award_id_b"]} {fmt_b(d["amount_b"])}</div>'
            f'<div style="font-size:11.5px;color:var(--ink-faint)">{d["days_apart"]} days apart, {pct_diff:.0f}% difference</div></div>')

DUPLICATE_CARDS = "".join(dup_card(d) for d in P["duplicate_purchase_candidates"])

CATEGORIES_TABLE_ROWS = "".join(
    f'<tr><td>{cat}</td><td class="num">{fmt_b(sum(x["net_obligations"] for x in d["leading_suppliers"]))}</td>'
    f'<td class="num">{d["unique_suppliers"]:,}</td>'
    f'<td class="num">{d["concentration_hhi"]:.0f}</td>'
    f'<td class="num">{d["tail_spend_share"]*100:.1f}%</td>'
    f'<td class="num">{d["low_confidence_count"]:,}</td></tr>'
    for cat, d in sorted(CATEGORIES_DETAIL_DICT.items(), key=lambda kv: -sum(x["net_obligations"] for x in kv[1]["leading_suppliers"]))
)

TOP_SUPPLIERS_TABLE_ROWS = "".join(
    f'<tr><td>{s["normalized_supplier"]}</td><td class="num">{fmt_b(s["net_obligations"])}</td>'
    f'<td class="num">{supplier_pct(s["net_obligations"]):.1f}%</td><td class="num">{s["unique_awards"]:,}</td></tr>'
    for s in TOP_SUPPLIERS
)

AWARDS_TABLE_ROWS = "".join(
    f'<tr><td>{a["award_id"]}</td><td>{a["supplier"]}</td><td>{a.get("category","")}</td>'
    f'<td class="num">{fmt_b(a["net_obligations"])}</td><td>{a.get("extent_competed","")}</td></tr>'
    for a in AWARDS_SUMMARY
)

DQ_HTML = "".join(
    f'<div class="finding warn"><strong>{a["award_id_piid"]}</strong> ({a["recipient_name_raw"]}) &mdash; '
    f'reported value {fmt_full(a["amount"])}, excluded as an implausible currency/unit outlier (see Methodology).</div>'
    for a in DQ["implausible_awards_excluded"]
)

META_NOTE = P["meta"].get("note", "")
GENERATED_AT = A.get("generated_at", "")

# No-bid tab summary figures (fields verified against the actual SB/DD/CD JSON on disk)
NOBID_TOTAL = SB["single_bid_total_value"]
NOBID_COUNT = SB["single_bid_count"]
NOBID_UNDER_SAT = DD["total_count"]
NOBID_UNDER_SAT_VALUE = DD["total_value"]
NOBID_NEAR_THRESH_COUNT = DD["near_threshold_count"]
NOBID_COMPETED_COUNT = SB["all_competed_count"]
NOBID_COMPETED_VALUE = SB["all_competed_value"]

NOBID_VENDOR_ROWS_HTML = "".join(
    f'<div class="bar-row"><div class="bar-name" title="{v["name"]}">{v["name"]}</div>'
    f'<div class="bar-track"><div class="bar-fill" style="width:{max(v["value"]/SB["vendor_rollup"][0]["value"]*100,1):.1f}%"></div></div>'
    f'<div class="bar-figures"><span>{fmt_b(v["value"])}</span><span class="bar-pct">{v["count"]:,}</span></div></div>'
    for v in SB["vendor_rollup"]
)

NOBID_BRANCH_MAX = max(c for _, c in DD["branch_counts_near"]) if DD["branch_counts_near"] else 1
NOBID_BRANCH_ROWS_HTML = "".join(
    f'<div class="bar-row"><div class="bar-name">{branch}</div>'
    f'<div class="bar-track"><div class="bar-fill" style="width:{max(count/NOBID_BRANCH_MAX*100,1):.1f}%"></div></div>'
    f'<div class="bar-figures"><span>{count:,} contracts</span></div></div>'
    for branch, count in DD["branch_counts_near"]
)

# ============================================================
# QUALITY OF LIFE BY BRANCH (unique to DoD_v2, per user request)
# ============================================================
QOL_META = QOL["meta"]
QOL_ADJ_NOTE = QOL["beneficiary_adjustment"]

def qol_percap_bars(summary, max_val):
    rows = [r for r in summary if r["qol_per_servicemember_per_year"]]
    return "".join(
        f'<div class="bar-row"><div class="bar-name">{r["branch"]}</div>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{max(r["qol_per_servicemember_per_year"]/max_val*100,1):.1f}%"></div></div>'
        f'<div class="bar-figures"><span>${r["qol_per_servicemember_per_year"]:,.0f}/yr</span><span class="bar-pct">{fmt_b(r["qol_total"])}</span></div></div>'
        for r in rows
    )

QOL_PERCAP_MAX = max(r["qol_per_servicemember_per_year"] for r in QOL["branch_summary"] if r["qol_per_servicemember_per_year"])
QOL_BRANCH_BARS_HTML = qol_percap_bars(QOL["branch_summary"], QOL_PERCAP_MAX)
QOL_BRANCH_BARS_ADJUSTED_HTML = qol_percap_bars(QOL["branch_summary_adjusted"], QOL_PERCAP_MAX)

def _ppy(r):
    return f'${r["qol_per_servicemember_per_year"]:,.0f}' if r["qol_per_servicemember_per_year"] else "n/a"

QOL_COMPARE_TABLE_ROWS = "".join(
    f'<tr><td>{a["branch"]}</td>'
    f'<td class="num">{fmt_b(a["qol_total"])}</td>'
    f'<td class="num">{_ppy(a)}</td>'
    f'<td class="num">{fmt_b(b["qol_total"])}</td>'
    f'<td class="num">{_ppy(b)}</td></tr>'
    for a, b in zip(
        sorted(QOL["branch_summary"], key=lambda r: r["branch"]),
        sorted(QOL["branch_summary_adjusted"], key=lambda r: r["branch"]),
    )
)

QOL_CATEGORY_ROWS_HTML = "".join(
    f'<tr><td>{c["category"]}</td>'
    f'<td class="num">{fmt_b(c["Army"])}</td>'
    f'<td class="num">{fmt_b(c["Navy / Marine Corps"])}</td>'
    f'<td class="num">{fmt_b(c["Air Force / Space Force"])}</td>'
    f'<td class="num">{fmt_b(c["Defense-Wide / Multi-Service"])}</td>'
    f'<td class="num">{fmt_b(c["total"])}</td></tr>'
    for c in QOL["category_matrix"]
)

qol_awards_json = json.dumps(QOL["qol_awards"])
QOL_BRANCH_OPTIONS_HTML = "".join(
    f'<option value="{b}">{b}</option>' for b in ["Army", "Navy / Marine Corps", "Air Force / Space Force", "Defense-Wide / Multi-Service"]
)

# ============================================================
# SPEND RISK SIGNALS: sole-source pricing risk + foreign vendor spend
# ============================================================
high_risk_awards_json = json.dumps(RISK["high_risk_awards"])
foreign_awards_json = json.dumps(RISK["foreign_awards"])

RISK_MATRIX_ROWS_HTML = "".join(
    f'<tr><td>{r["competed_bucket"]}</td><td>{r["pricing_bucket"]}</td>'
    f'<td class="num">{fmt_b(r["amount"])}</td><td class="num">{r["count"]:,}</td></tr>'
    for r in RISK["risk_matrix"] if r["amount"] > 0
)

JUSTIFICATION_MAX = max((j["amount"] for j in RISK["justification_breakdown"]), default=1)
JUSTIFICATION_BARS_HTML = "".join(
    f'<div class="bar-row"><div class="bar-name" title="{j["justification"]}">{j["justification"]}</div>'
    f'<div class="bar-track"><div class="bar-fill" style="width:{max(j["amount"]/JUSTIFICATION_MAX*100,1):.1f}%"></div></div>'
    f'<div class="bar-figures"><span>{fmt_b(j["amount"])}</span><span class="bar-pct">{j["count"]:,}</span></div></div>'
    for j in RISK["justification_breakdown"][:10]
)

SUB_MEGA_CAT_MAX = max((c["amount"] for c in RISK["sub_mega_by_category"]), default=1)
SUB_MEGA_CATEGORY_BARS_HTML = "".join(
    f'<div class="bar-row"><div class="bar-name" title="{c["ai_spend_category"]}">{c["ai_spend_category"]}</div>'
    f'<div class="bar-track"><div class="bar-fill" style="width:{max(c["amount"]/SUB_MEGA_CAT_MAX*100,1):.1f}%"></div></div>'
    f'<div class="bar-figures"><span>{fmt_b(c["amount"])}</span><span class="bar-pct">{c["count"]:,}</span></div></div>'
    for c in RISK["sub_mega_by_category"][:12]
)

SUB_MEGA_SUP_MAX = max((s["amount"] for s in RISK["sub_mega_by_supplier"]), default=1)
SUB_MEGA_SUPPLIER_BARS_HTML = "".join(
    f'<div class="bar-row"><div class="bar-name" title="{s["normalized_supplier"]}">{s["normalized_supplier"]}</div>'
    f'<div class="bar-track"><div class="bar-fill" style="width:{max(s["amount"]/SUB_MEGA_SUP_MAX*100,1):.1f}%"></div></div>'
    f'<div class="bar-figures"><span>{fmt_b(s["amount"])}</span><span class="bar-pct">{s["count"]:,}</span></div></div>'
    for s in RISK["sub_mega_by_supplier"][:15]
)

COUNTRY_MAX = max((c["amount"] for c in RISK["country_breakdown"]), default=1)
COUNTRY_ROWS_HTML = "".join(
    f'<tr><td>{c["country"]}</td><td class="num">{fmt_b(c["amount"])}</td>'
    f'<td class="num">{c["count"]:,}</td><td class="num">{c["not_competed_pct"]:.1f}%</td></tr>'
    for c in RISK["country_breakdown"][:20]
)

FOREIGN_CAT_MAX = max((c["amount"] for c in RISK["foreign_category_breakdown"]), default=1)
FOREIGN_CATEGORY_BARS_HTML = "".join(
    f'<div class="bar-row"><div class="bar-name" title="{c["category"]}">{c["category"]}</div>'
    f'<div class="bar-track"><div class="bar-fill" style="width:{max(c["amount"]/FOREIGN_CAT_MAX*100,1):.1f}%"></div></div>'
    f'<div class="bar-figures"><span>{fmt_b(c["amount"])}</span><span class="bar-pct">{c["count"]:,}</span></div></div>'
    for c in RISK["foreign_category_breakdown"][:12]
)

niche_awards_json = json.dumps(RISK["niche_awards"])

def niche_row_html(n):
    note = n["note"] or "Unverified &mdash; no independently confirmed structural explanation on file"
    note_cls = "" if n["note"] else "warn"
    return (
        f'<tr><td>{n["country"]}</td><td>{n["category"]}</td><td>{n["top_vendor"]}</td>'
        f'<td class="num">{fmt_b(n["total"])}</td><td class="num">{n["top_share"]*100:.0f}%</td>'
        f'<td class="num">{n["top_award_count"]}</td><td class="num">{n["not_competed_pct"]*100:.0f}%</td>'
        f'<td style="max-width:280px;font-size:11px;color:var(--ink-muted)">{note}</td></tr>'
    )

NICHE_ROWS_HTML = "".join(niche_row_html(n) for n in RISK["flagged_niches"])
NICHE_UNVERIFIED_COUNT = sum(1 for n in RISK["flagged_niches"] if not n["note"])

# ============================================================
# ORIGINAL STYLIZED BADGE (not a reproduction of any official seal --
# a generic star-in-ring emblem, since this project explicitly
# disclaims official DoD/War Department affiliation or endorsement)
# ============================================================
import math as _math
def _star_points(cx, cy, r_outer, r_inner, n=5, rotate_deg=-90):
    pts = []
    for i in range(n * 2):
        r = r_outer if i % 2 == 0 else r_inner
        angle = _math.radians(rotate_deg + i * (360 / (n * 2)))
        pts.append((cx + r * _math.cos(angle), cy + r * _math.sin(angle)))
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)

def _tick_lines(cx, cy, r_in, r_out, n=24):
    lines = []
    for i in range(n):
        angle = _math.radians(i * (360 / n))
        x1, y1 = cx + r_in * _math.cos(angle), cy + r_in * _math.sin(angle)
        x2, y2 = cx + r_out * _math.cos(angle), cy + r_out * _math.sin(angle)
        lines.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="currentColor" stroke-width="1.5" opacity="0.55"/>')
    return "".join(lines)

BADGE_SVG = f"""<svg viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
<circle cx="60" cy="60" r="56" stroke="currentColor" stroke-width="2"/>
<circle cx="60" cy="60" r="46" stroke="currentColor" stroke-width="1" opacity="0.6"/>
{_tick_lines(60, 60, 50, 56, 24)}
<polygon points="{_star_points(60, 60, 30, 12)}" fill="currentColor"/>
</svg>"""

# ============================================================
# HTML BODY (masthead + tab nav + 7 tab panels)
# ============================================================
body_html = f"""
<div class="page">
  <header class="masthead">
    <div class="masthead-top">
      <div class="masthead-badge">{BADGE_SVG}</div>
      <div>
        <div class="wordmark-primary">Department of War</div>
        <div class="wordmark-secondary">Office of Procurement Analytics &middot; Unofficial Project</div>
      </div>
    </div>
    <div class="eyebrow">DoD_v2 &middot; Educational Procurement Intelligence Project</div>
    <h1>DoD Procurement Intelligence Dashboard</h1>
    <p class="dek">{P["meta"]["disclosure"]} Data period {P["meta"]["data_period_start"]} through {P["meta"]["data_period_end"]}, covering {TOTALS["transaction_count"]:,} definitive contract awards from USAspending.gov's bulk award-download API.</p>
  </header>

  <nav class="tabnav" role="tablist">
    <button class="tab-btn" data-tab="overview" aria-selected="true" role="tab">Executive Overview</button>
    <button class="tab-btn" data-tab="standout" role="tab">Standout Suppliers &amp; Contracts</button>
    <button class="tab-btn" data-tab="yoy" role="tab">Year-over-Year Trends</button>
    <button class="tab-btn" data-tab="explorer" role="tab">Transaction Explorer</button>
    <button class="tab-btn" data-tab="supplier" role="tab">Supplier Analysis</button>
    <button class="tab-btn" data-tab="categories" role="tab">Categories &amp; Opportunities</button>
    <button class="tab-btn" data-tab="nobid" role="tab">No-Bid Contracts<span class="new-badge">unique</span></button>
    <button class="tab-btn" data-tab="qol" role="tab">Quality of Life by Branch<span class="new-badge">unique</span></button>
    <button class="tab-btn" data-tab="risk" role="tab">Spend Risk Signals<span class="new-badge">unique</span></button>
  </nav>

  <section class="tabpanel is-active" id="tab-overview">
    <div class="kpi-row">
      <div class="kpi"><div class="kpi-label">Total Award Value</div><div class="kpi-value">{fmt_b(TOTALS["net_obligations"])}</div><div class="kpi-sub">current total contract value, not period obligations</div></div>
      <div class="kpi"><div class="kpi-label">Unique Suppliers</div><div class="kpi-value">{TOTALS["unique_suppliers"]:,}</div><div class="kpi-sub">parent-UEI resolved</div></div>
      <div class="kpi"><div class="kpi-label">Unique Awards</div><div class="kpi-value">{TOTALS["unique_awards"]:,}</div><div class="kpi-sub">definitive contracts, FY2020-FY2026 YTD</div></div>
      <div class="kpi"><div class="kpi-label">Supplier HHI</div><div class="kpi-value">{A["concentration"]["hhi"]:.0f}</div><div class="kpi-sub">DOJ/FTC: &lt;1500 unconcentrated</div></div>
    </div>

    <div class="panel">
      <div class="panel-head"><h2>Annual Award Value by Fiscal Year</h2></div>
      <div class="month-chart">{ANNUAL_CHART_HTML}</div>
    </div>

    <div class="panel-grid">
      <div class="panel">
        <div class="panel-head"><h2>Spend by Category</h2></div>
        <div class="bars">{CAT_ROWS_HTML}</div>
      </div>
      <div class="panel">
        <div class="panel-head"><h2>Top 15 Suppliers</h2></div>
        <div class="bars">{TOP_SUPPLIER_ROWS_HTML}</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head"><h2>Key Findings</h2></div>
      {INSIGHTS_HTML}
    </div>

    {"<div class='panel'><div class='panel-head'><h2>Data Quality Exclusions</h2></div>" + DQ_HTML + "</div>" if DQ["implausible_awards_excluded"] else ""}
  </section>

  <section class="tabpanel" id="tab-standout">
    <div class="panel">
      <div class="panel-head"><h2>Standout Suppliers</h2></div>
      <div class="card-list">{STANDOUT_SUPPLIER_CARDS}</div>
    </div>
    <div class="panel">
      <div class="panel-head"><h2>Standout Contracts</h2></div>
      <div class="card-list">{STANDOUT_AWARD_CARDS}</div>
    </div>
    <div class="panel">
      <div class="panel-head"><h2>Consolidation Opportunities</h2></div>
      <p style="font-size:12px;color:var(--ink-muted);margin:-6px 0 14px">Categories where spend is fragmented across many suppliers with no single dominant vendor (HHI below 2500) -- a fragmentation signal only, not a savings estimate or vendor recommendation.</p>
      <div class="card-list">{CONSOLIDATION_CARDS}</div>
    </div>
    <div class="panel">
      <div class="panel-head"><h2>Duplicate Purchase Candidates</h2></div>
      <p style="font-size:12px;color:var(--ink-muted);margin:-6px 0 14px">Same supplier, same category, similar dollar amount, within 120 days -- flagged for review, not asserted as wasteful.</p>
      <div class="card-list">{DUPLICATE_CARDS}</div>
    </div>
  </section>

  <section class="tabpanel" id="tab-yoy">
    <div class="panel-grid">
      <div class="panel">
        <div class="panel-head"><h2>Net Award Value by Fiscal Year</h2></div>
        <div class="month-chart">{ANNUAL_CHART_HTML}</div>
      </div>
      <div class="panel">
        <div class="panel-head"><h2>Top-5 Supplier Concentration by Fiscal Year</h2></div>
        <div class="month-chart">{CONC_CHART_HTML}</div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-head"><h2>Notable Category Year-over-Year Changes (&ge;25%)</h2></div>
      <div class="table-scroll"><table>
        <thead><tr><th>Category</th><th>From FY</th><th>To FY</th><th class="num">Change</th></tr></thead>
        <tbody>{"".join(f'<tr><td>{c["category"]}</td><td>{c["from_fy"]}</td><td>{c["to_fy"]}</td><td class="num">{c["pct_change"]:+.1f}%</td></tr>' for c in A["notable_category_yoy_changes"])}</tbody>
      </table></div>
    </div>
  </section>

  <section class="tabpanel" id="tab-explorer">
    <div class="panel">
      <div class="panel-head"><h2>Transaction Explorer</h2></div>
      <div class="cd-toolbar">
        <div class="cd-search" style="flex:1"><input type="text" id="explorer-search" placeholder="Search supplier, award ID, description, category..."></div>
        <div class="cd-count" id="explorer-count"></div>
        <button class="cd-download" id="explorer-download">Download CSV</button>
      </div>
      <p style="font-size:11.5px;color:var(--ink-faint);margin:-6px 0 12px">Showing the {len(EXPLORER_ROWS):,} most recent awards by action date, out of {TOTAL_EXPLORER_ROWS:,} total in the dataset.</p>
      <div class="table-scroll" style="max-height:640px">
        <table id="explorer-table">
          <thead><tr>
            <th>FY</th><th>Action Date</th><th>Supplier</th><th>Award ID</th><th class="num">Value</th>
            <th>Category</th><th>PSC / NAICS Desc.</th><th>Description</th><th>Extent Competed</th><th>Sub-Agency</th>
          </tr></thead>
          <tbody id="explorer-tbody"></tbody>
        </table>
      </div>
    </div>
  </section>

  <section class="tabpanel" id="tab-supplier">
    <div class="panel">
      <div class="panel-head"><h2>Supplier Lookup</h2></div>
      <div class="cd-search"><input type="text" id="supplier-search" placeholder="Search a supplier by name..."></div>
      <div id="supplier-search-results" style="margin-top:8px"></div>
    </div>
    <div class="panel" id="supplier-detail-panel" style="display:none">
      <div class="panel-head"><h2 id="supplier-detail-name"></h2></div>
      <div id="supplier-detail-body"></div>
    </div>
    <div class="panel">
      <div class="panel-head"><h2>Top 25 Suppliers</h2></div>
      <div class="table-scroll"><table>
        <thead><tr><th>Supplier</th><th class="num">Net Value</th><th class="num">Share</th><th class="num">Awards</th></tr></thead>
        <tbody>{TOP_SUPPLIERS_TABLE_ROWS}</tbody>
      </table></div>
    </div>
  </section>

  <section class="tabpanel" id="tab-categories">
    <div class="panel">
      <div class="panel-head"><h2>Category Breakdown, Concentration &amp; Review Queue</h2></div>
      <div class="table-scroll"><table>
        <thead><tr><th>Category</th><th class="num">Net Value</th><th class="num">Suppliers</th><th class="num">HHI</th><th class="num">Tail Share</th><th class="num">Low-Confidence</th></tr></thead>
        <tbody>{CATEGORIES_TABLE_ROWS}</tbody>
      </table></div>
    </div>
    <div class="panel">
      <div class="panel-head"><h2>Largest Contracts</h2></div>
      <div class="table-scroll"><table>
        <thead><tr><th>Award ID</th><th>Supplier</th><th>Category</th><th class="num">Value</th><th>Extent Competed</th></tr></thead>
        <tbody>{AWARDS_TABLE_ROWS}</tbody>
      </table></div>
    </div>
  </section>

  <section class="tabpanel" id="tab-nobid">
    <div class="callout">
      <div class="callout-mark">i</div>
      <div class="callout-body">
        <p>Unique to this DoD_v2 build (not part of v3's structure): every award in this dataset carries FPDS's <code>number_of_offers_received</code> field, which lets us isolate contracts awarded with exactly one offer received -- i.e. genuinely uncompeted in practice, regardless of how the contract was coded (many are legally "competed" under a streamlined procedure like SAP but still drew a single bid).</p>
        <p>This is a screening signal, not a finding of wrongdoing: a single bid can reflect a legitimate sole-source situation, a niche specialty vendor, or simply a thin market -- not necessarily a process failure.</p>
      </div>
    </div>
    <div class="kpi-row">
      <div class="kpi"><div class="kpi-label">Single-Bid Contracts</div><div class="kpi-value">{NOBID_COUNT:,}</div><div class="kpi-sub">{fmt_b(NOBID_TOTAL)} total value</div></div>
      <div class="kpi"><div class="kpi-label">Under SAT ($350K)</div><div class="kpi-value">{NOBID_UNDER_SAT:,}</div><div class="kpi-sub">{fmt_b(NOBID_UNDER_SAT_VALUE)} total value</div></div>
      <div class="kpi"><div class="kpi-label">Near-Threshold (&gt;90% of SAT)</div><div class="kpi-value">{NOBID_NEAR_THRESH_COUNT:,}</div><div class="kpi-sub">clustering just under the simplified-acquisition ceiling</div></div>
      <div class="kpi"><div class="kpi-label">Genuinely Competed</div><div class="kpi-value">{NOBID_COMPETED_COUNT:,}</div><div class="kpi-sub">{fmt_b(NOBID_COMPETED_VALUE)} total value</div></div>
    </div>
    <div class="panel-grid">
      <div class="panel">
        <div class="panel-head"><h2>Top 20 Vendors by Single-Bid Value</h2></div>
        <div class="bars">{NOBID_VENDOR_ROWS_HTML}</div>
      </div>
      <div class="panel">
        <div class="panel-head"><h2>Under-SAT Single-Bid Awards by Branch</h2></div>
        <div class="bars">{NOBID_BRANCH_ROWS_HTML}</div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-head"><h2>Single-Bid Contract Detail (Under $350K SAT)</h2></div>
      <div class="cd-toolbar">
        <div class="cd-search" style="flex:1"><input type="text" id="nobid-search" placeholder="Search vendor, award ID, description..."></div>
        <div class="cd-count" id="nobid-count"></div>
        <button class="cd-download" id="nobid-download">Download CSV</button>
      </div>
      <div class="table-scroll" style="max-height:640px">
        <table id="nobid-table">
          <thead><tr>
            <th>Award ID</th><th>Vendor</th><th class="num">Value</th><th>Branch</th><th>Extent Competed</th>
            <th>Contract Type</th><th>Award Date</th><th>PSC Description</th><th>Description</th>
          </tr></thead>
          <tbody id="nobid-tbody"></tbody>
        </table>
      </div>
    </div>
    <div class="methodology">
      <h3>No-Bid Methodology</h3>
      <ul>
        <li>Single-bid = <code>number_of_offers_received == 1</code>, sourced directly from FPDS via USAspending.gov's bulk award-download API.</li>
        <li>SAT = Simplified Acquisition Threshold, $350,000 -- the level below which streamlined procedures are legally permitted.</li>
        <li>Near-threshold = single-bid awards priced at 90% or more of the $350K SAT, a pattern worth watching for threshold-bunching, not proof of it.</li>
        <li>"Genuinely competed" excludes single-bid awards regardless of procedure code; a contract can be legally "competed" and still draw one bid.</li>
      </ul>
    </div>
  </section>

  <section class="tabpanel" id="tab-qol">
    <div class="callout">
      <div class="callout-mark">i</div>
      <div class="callout-body">
        <p>Unique to this DoD_v2 build: awards are keyword-matched against nine quality-of-life categories (dining facilities, chapels, family housing, dormitories/barracks, fitness &amp; recreation, child &amp; youth services, medical clinics, commissary/exchange, and MWR), then grouped by service branch and divided by each branch's active-duty headcount.</p>
        <p><strong>FPDS doesn't distinguish Space Force from Air Force, or Marine Corps from Navy</strong> at the awarding-agency level -- both pairs share contracting infrastructure, so branches are reported as combined pairs: "Air Force / Space Force" and "Navy / Marine Corps". Army is reported alone.</p>
        <p><strong>The result runs opposite to a common assumption that Air Force/Space Force spend more per person on quality of life.</strong> In this data, Army and Navy/Marine Corps show roughly 2-3x the per-servicemember rate that Air Force/Space Force does -- see Methodology below for why that comparison itself needs a caveat before treating it as a definitive finding.</p>
      </div>
    </div>

    <div class="kpi-row">
      <div class="kpi"><div class="kpi-label">Total QoL-Coded Spend</div><div class="kpi-value">{fmt_b(QOL["qol_total_all_branches"])}</div><div class="kpi-sub">{QOL["qol_award_count_all_branches"]:,} awards, {QOL_META["categories_tracked"].__len__()} categories</div></div>
      <div class="kpi"><div class="kpi-label">Share of Total DoD Spend</div><div class="kpi-value">{QOL["qol_total_all_branches"]/TOTALS["net_obligations"]*100:.2f}%</div><div class="kpi-sub">of {fmt_b(TOTALS['net_obligations'])} total</div></div>
      <div class="kpi"><div class="kpi-label">Data Period</div><div class="kpi-value">{QOL_META["years_covered"]:.1f} yrs</div><div class="kpi-sub">FY2020 &ndash; FY2026 YTD</div></div>
      <div class="kpi"><div class="kpi-label">Beneficiary Reassignments</div><div class="kpi-value">{QOL_ADJ_NOTE["awards_reassigned"]}</div><div class="kpi-sub">{fmt_b(QOL_ADJ_NOTE["value_reassigned"])} moved off awarding branch</div></div>
    </div>

    <div class="panel-grid">
      <div class="panel">
        <div class="panel-head"><h2>QoL Spend per Servicemember per Year</h2><span class="pill">as-awarded (by contracting agency)</span></div>
        <div class="bars">{QOL_BRANCH_BARS_HTML}</div>
      </div>
      <div class="panel">
        <div class="panel-head"><h2>QoL Spend per Servicemember per Year</h2><span class="pill">beneficiary-adjusted (floor correction)</span></div>
        <div class="bars">{QOL_BRANCH_BARS_ADJUSTED_HTML}</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head"><h2>As-Awarded vs. Beneficiary-Adjusted, Side by Side</h2></div>
      <div class="table-scroll"><table>
        <thead><tr><th>Branch</th><th class="num">As-Awarded Total</th><th class="num">As-Awarded $/Person/Yr</th><th class="num">Adjusted Total</th><th class="num">Adjusted $/Person/Yr</th></tr></thead>
        <tbody>{QOL_COMPARE_TABLE_ROWS}</tbody>
      </table></div>
    </div>

    <div class="panel">
      <div class="panel-head"><h2>QoL Category Breakdown by Branch (as-awarded)</h2></div>
      <div class="table-scroll"><table>
        <thead><tr><th>Category</th><th class="num">Army</th><th class="num">Navy/USMC</th><th class="num">AF/USSF</th><th class="num">Defense-Wide</th><th class="num">Total</th></tr></thead>
        <tbody>{QOL_CATEGORY_ROWS_HTML}</tbody>
      </table></div>
    </div>

    <div class="panel">
      <div class="panel-head"><h2>Quality-of-Life Award Detail</h2></div>
      <p style="font-size:11.5px;color:var(--ink-faint);margin:-6px 0 12px">All {len(QOL["qol_awards"]):,} QoL-classified awards, filterable by branch and searchable by supplier, award ID, category, or description.</p>
      <div class="cd-toolbar">
        <select id="qol-branch-filter" style="font-family:'IBM Plex Mono',monospace;font-size:12px;padding:8px 10px;border:1px solid var(--line-strong);border-radius:6px;background:var(--surface);color:var(--ink)">
          <option value="">All Branches</option>
          {QOL_BRANCH_OPTIONS_HTML}
        </select>
        <div class="cd-search" style="flex:1"><input type="text" id="qol-search" placeholder="Search supplier, award ID, category, description..."></div>
        <div class="cd-count" id="qol-count"></div>
        <button class="cd-download" id="qol-download">Download CSV</button>
      </div>
      <div class="table-scroll" style="max-height:640px">
        <table id="qol-table">
          <thead><tr>
            <th>Award ID</th><th>Branch (as-awarded)</th><th>Branch (adjusted)</th><th>Category</th><th>Supplier</th>
            <th class="num">Value</th><th>Date</th><th>Extent Competed</th><th>Description</th>
          </tr></thead>
          <tbody id="qol-tbody"></tbody>
        </table>
      </div>
    </div>

    <div class="methodology">
      <h3>Quality-of-Life Methodology &amp; Caveats</h3>
      <ul>
        <li>Categories are identified by keyword matching against each award's description, PSC description, and NAICS description -- the same deterministic approach used elsewhere in this project. An award that funds quality of life without using one of these keywords (e.g. a generic "facility repair" that happens to be a gym) is not counted, so totals are a floor, not a comprehensive figure.</li>
        <li><strong>Awarding agency &ne; beneficiary.</strong> The Army Corps of Engineers executes a large share of DoD-wide military construction, including barracks and child care centers built for Air Force or Marine Corps personnel. The "beneficiary-adjusted" view reassigns the {QOL_ADJ_NOTE["awards_reassigned"]} awards ({fmt_b(QOL_ADJ_NOTE["value_reassigned"])}) whose own description explicitly names a different service -- but most such awards don't name the beneficiary in free text, so this is a floor correction, not a full one. The true Air Force/Space Force figure is likely higher than either view shows here.</li>
        <li>Per-servicemember figures divide a {QOL_META["years_covered"]:.1f}-year cumulative spend total by a single point-in-time headcount snapshot, not a matched annual budget. Treat as a rough comparative rate, not a precise per-person budget line.</li>
        <li>Headcount source: {QOL_META["headcount_source"]}</li>
        <li>"Air Force / Space Force" and "Navy / Marine Corps" are reported as combined pairs because FPDS's awarding-agency field doesn't separate them -- Space Force shares Air Force contracting infrastructure, and the Marine Corps is organizationally part of the Department of the Navy.</li>
      </ul>
    </div>
  </section>

  <section class="tabpanel" id="tab-risk">
    <div class="callout">
      <div class="callout-mark">i</div>
      <div class="callout-body">
        <p><strong>Sole-source pricing risk:</strong> {RISK["meta"]["sole_source_methodology"]}</p>
      </div>
    </div>

    <div class="kpi-row">
      <div class="kpi"><div class="kpi-label">Not Competed + Cost-Type</div><div class="kpi-value">{fmt_b(RISK["high_risk_total"])}</div><div class="kpi-sub">{RISK["high_risk_count"]:,} awards, {RISK["high_risk_share_of_total_pct"]:.1f}% of all DoD spend</div></div>
      <div class="kpi"><div class="kpi-label">Mega-Prime Awards (&ge;$500M)</div><div class="kpi-value">{fmt_b(RISK["high_risk_mega_total"])}</div><div class="kpi-sub">{RISK["high_risk_mega_count"]:,} awards &mdash; structurally sole-source</div></div>
      <div class="kpi"><div class="kpi-label">Smaller / Actionable (&lt;$500M)</div><div class="kpi-value">{fmt_b(RISK["high_risk_sub_mega_total"])}</div><div class="kpi-sub">{RISK["high_risk_sub_mega_count"]:,} awards &mdash; the more useful oversight slice</div></div>
      <div class="kpi"><div class="kpi-label">Share Below Threshold</div><div class="kpi-value">{RISK["high_risk_sub_mega_total"]/RISK["high_risk_total"]*100:.0f}%</div><div class="kpi-sub">of the not-competed + cost-type total</div></div>
    </div>

    <div class="panel">
      <div class="panel-head"><h2>Competition &times; Pricing Type Risk Matrix</h2></div>
      <div class="table-scroll"><table>
        <thead><tr><th>Competed Status</th><th>Pricing Type</th><th class="num">Value</th><th class="num">Awards</th></tr></thead>
        <tbody>{RISK_MATRIX_ROWS_HTML}</tbody>
      </table></div>
    </div>

    <div class="panel-grid">
      <div class="panel">
        <div class="panel-head"><h2>Why Sole-Sourced? (FAR Justification Codes)</h2><span class="pill">not-competed + cost-type awards</span></div>
        <div class="bars">{JUSTIFICATION_BARS_HTML}</div>
      </div>
      <div class="panel">
        <div class="panel-head"><h2>Top Suppliers</h2><span class="pill">smaller / actionable slice only</span></div>
        <div class="bars">{SUB_MEGA_SUPPLIER_BARS_HTML}</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head"><h2>Category Breakdown</h2><span class="pill">smaller / actionable slice only (&lt;$500M each)</span></div>
      <div class="bars">{SUB_MEGA_CATEGORY_BARS_HTML}</div>
    </div>

    <div class="panel">
      <div class="panel-head"><h2>Sole-Source Pricing Risk &mdash; Award Detail</h2></div>
      <p style="font-size:11.5px;color:var(--ink-faint);margin:-6px 0 12px">All {len(RISK["high_risk_awards"]):,} awards that are both not competed and cost-reimbursement/T&amp;M priced. Filter out the {RISK["high_risk_mega_count"]} mega-prime awards (&ge;$500M) to focus on the more actionable slice.</p>
      <div class="cd-toolbar">
        <select id="risk-mega-filter" style="font-family:'IBM Plex Mono',monospace;font-size:12px;padding:8px 10px;border:1px solid var(--line-strong);border-radius:6px;background:var(--surface);color:var(--ink)">
          <option value="">All Awards</option>
          <option value="sub">Smaller / Actionable (&lt;$500M)</option>
          <option value="mega">Mega-Prime Only (&ge;$500M)</option>
        </select>
        <div class="cd-search" style="flex:1"><input type="text" id="risk-search" placeholder="Search supplier, award ID, category, justification, description..."></div>
        <div class="cd-count" id="risk-count"></div>
        <button class="cd-download" id="risk-download">Download CSV</button>
      </div>
      <div class="table-scroll" style="max-height:640px">
        <table id="risk-table">
          <thead><tr>
            <th>Award ID</th><th>Supplier</th><th>Category</th><th>Pricing Type</th><th>Justification</th>
            <th class="num">Value</th><th>Date</th><th>Sub-Agency</th><th>Description</th>
          </tr></thead>
          <tbody id="risk-tbody"></tbody>
        </table>
      </div>
    </div>

    <div class="callout" style="margin-top:6px">
      <div class="callout-mark">i</div>
      <div class="callout-body">
        <p><strong>Foreign vendor &amp; overseas spend:</strong> {RISK["meta"]["foreign_vendor_methodology"]}</p>
      </div>
    </div>

    <div class="kpi-row">
      <div class="kpi"><div class="kpi-label">Domestic Vendor Spend</div><div class="kpi-value">{fmt_b(RISK["domestic_summary"]["total"])}</div><div class="kpi-sub">{RISK["domestic_summary"]["not_competed_pct"]:.1f}% not competed</div></div>
      <div class="kpi"><div class="kpi-label">Foreign Vendor Spend</div><div class="kpi-value">{fmt_b(RISK["foreign_summary"]["total"])}</div><div class="kpi-sub">{RISK["foreign_summary"]["not_competed_pct"]:.1f}% not competed</div></div>
      <div class="kpi"><div class="kpi-label">Foreign Share of Total</div><div class="kpi-value">{RISK["foreign_summary"]["total"]/(RISK["domestic_summary"]["total"]+RISK["foreign_summary"]["total"])*100:.2f}%</div><div class="kpi-sub">{RISK["foreign_summary"]["count"]:,} awards to {len(RISK["country_breakdown"])} countries</div></div>
      <div class="kpi"><div class="kpi-label">Foreign + Not Competed</div><div class="kpi-value">{fmt_b(RISK["foreign_not_competed_total"])}</div><div class="kpi-sub">{RISK["foreign_not_competed_count"]:,} awards</div></div>
    </div>

    <div class="panel-grid">
      <div class="panel">
        <div class="panel-head"><h2>Top Countries by Foreign Vendor Spend</h2></div>
        <div class="table-scroll"><table>
          <thead><tr><th>Country</th><th class="num">Value</th><th class="num">Awards</th><th class="num">Not Competed</th></tr></thead>
          <tbody>{COUNTRY_ROWS_HTML}</tbody>
        </table></div>
      </div>
      <div class="panel">
        <div class="panel-head"><h2>Foreign Spend by Category</h2></div>
        <div class="bars">{FOREIGN_CATEGORY_BARS_HTML}</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head"><h2>Foreign Vendor Award Detail</h2></div>
      <p style="font-size:11.5px;color:var(--ink-faint);margin:-6px 0 12px">All {len(RISK["foreign_awards"]):,} awards to non-U.S.-registered vendors.</p>
      <div class="cd-toolbar">
        <select id="foreign-competed-filter" style="font-family:'IBM Plex Mono',monospace;font-size:12px;padding:8px 10px;border:1px solid var(--line-strong);border-radius:6px;background:var(--surface);color:var(--ink)">
          <option value="">All</option>
          <option value="Competed">Competed</option>
          <option value="Not Competed">Not Competed</option>
        </select>
        <div class="cd-search" style="flex:1"><input type="text" id="foreign-search" placeholder="Search supplier, award ID, country, category, description..."></div>
        <div class="cd-count" id="foreign-count"></div>
        <button class="cd-download" id="foreign-download">Download CSV</button>
      </div>
      <div class="table-scroll" style="max-height:640px">
        <table id="foreign-table">
          <thead><tr>
            <th>Award ID</th><th>Supplier</th><th>Country</th><th>Category</th><th>Competed Status</th>
            <th class="num">Value</th><th>Date</th><th>PoP Country</th><th>Description</th>
          </tr></thead>
          <tbody id="foreign-tbody"></tbody>
        </table>
      </div>
    </div>

    <div class="callout" style="margin-top:6px">
      <div class="callout-mark">i</div>
      <div class="callout-body">
        <p><strong>Concentrated vendor niches (generalized "Fat Leonard" screen):</strong> {RISK["meta"]["niche_methodology"]}</p>
      </div>
    </div>

    <div class="kpi-row">
      <div class="kpi"><div class="kpi-label">Flagged Niches</div><div class="kpi-value">{len(RISK["flagged_niches"])}</div><div class="kpi-sub">country &times; category combinations</div></div>
      <div class="kpi"><div class="kpi-label">Total Value</div><div class="kpi-value">{fmt_b(sum(n["total"] for n in RISK["flagged_niches"]))}</div><div class="kpi-sub">{len(RISK["niche_awards"]):,} awards</div></div>
      <div class="kpi"><div class="kpi-label">Structurally Explained</div><div class="kpi-value">{len(RISK["flagged_niches"]) - NICHE_UNVERIFIED_COUNT}</div><div class="kpi-sub">independently identifiable, disclosed reason</div></div>
      <div class="kpi"><div class="kpi-label">Unverified</div><div class="kpi-value">{NICHE_UNVERIFIED_COUNT}</div><div class="kpi-sub">no confirmed reason on file &mdash; worth review</div></div>
    </div>

    <div class="panel">
      <div class="panel-head"><h2>Flagged Niches</h2><span class="pill">min $2M &middot; &ge;60% share &middot; &ge;3 awards &middot; &ge;50% uncompeted</span></div>
      <div class="table-scroll"><table>
        <thead><tr><th>Country</th><th>Category</th><th>Top Vendor</th><th class="num">Total</th>
          <th class="num">Vendor Share</th><th class="num">Awards</th><th class="num">Uncompeted</th><th>Note</th></tr></thead>
        <tbody>{NICHE_ROWS_HTML}</tbody>
      </table></div>
    </div>

    <div class="panel">
      <div class="panel-head"><h2>Award Detail Within Flagged Niches</h2></div>
      <p style="font-size:11.5px;color:var(--ink-faint);margin:-6px 0 12px">All {len(RISK["niche_awards"]):,} awards belonging to the 13 flagged niches above.</p>
      <div class="cd-toolbar">
        <div class="cd-search" style="flex:1"><input type="text" id="niche-search" placeholder="Search supplier, award ID, country, category, description..."></div>
        <div class="cd-count" id="niche-count"></div>
        <button class="cd-download" id="niche-download">Download CSV</button>
      </div>
      <div class="table-scroll" style="max-height:640px">
        <table id="niche-table">
          <thead><tr>
            <th>Award ID</th><th>Supplier</th><th>Country</th><th>Category</th><th>Competed Status</th>
            <th class="num">Value</th><th>Date</th><th>Sub-Agency</th><th>Description</th>
          </tr></thead>
          <tbody id="niche-tbody"></tbody>
        </table>
      </div>
    </div>
  </section>

  <footer style="text-align:center;font-size:11px;color:var(--ink-faint);padding:20px 0">
    Generated {GENERATED_AT} &middot; Source: USAspending.gov bulk award-download API &middot; Unofficial educational project, not affiliated with or endorsed by the Department of Defense.
  </footer>
</div>
"""

print("Body HTML built:", len(body_html), "chars")

# ============================================================
# HEAD / CSS
# ============================================================
head_html = f"""<title>DoD Procurement Intelligence Dashboard (v2)</title>
<style>
@font-face {{ font-family:'IBM Plex Sans'; font-weight:400; font-style:normal; font-display:swap; src:url(data:font/woff2;base64,{SANS400}) format('woff2'); }}
@font-face {{ font-family:'IBM Plex Sans'; font-weight:500; font-style:normal; font-display:swap; src:url(data:font/woff2;base64,{SANS500}) format('woff2'); }}
@font-face {{ font-family:'IBM Plex Sans'; font-weight:600; font-style:normal; font-display:swap; src:url(data:font/woff2;base64,{SANS600}) format('woff2'); }}
@font-face {{ font-family:'IBM Plex Mono'; font-weight:400; font-style:normal; font-display:swap; src:url(data:font/woff2;base64,{MONO400}) format('woff2'); }}
@font-face {{ font-family:'IBM Plex Mono'; font-weight:500; font-style:normal; font-display:swap; src:url(data:font/woff2;base64,{MONO500}) format('woff2'); }}
@font-face {{ font-family:'IBM Plex Serif'; font-weight:600; font-style:normal; font-display:swap; src:url(data:font/woff2;base64,{SERIF600}) format('woff2'); }}

:root {{
  --bg:#e4eaed; --bg-grid:rgba(13,26,36,.05); --surface:#fff; --surface-2:#d6dfe4;
  --ink:#0f1e28; --ink-muted:#425c6b; --ink-faint:#6d8794;
  --accent:#35677d; --accent-strong:#1c4150; --accent-soft:rgba(53,103,125,.14);
  --flag:#6b7548; --flag-strong:#4a5232; --flag-soft:rgba(107,117,72,.15);
  --warn:#a83a2e; --warn-soft:rgba(168,58,46,.10);
  --line:rgba(13,26,36,.13); --line-strong:rgba(13,26,36,.24);
  --shadow:0 1px 2px rgba(13,26,36,.07),0 10px 28px -16px rgba(13,26,36,.28);
  color-scheme:light;
}}
@media (prefers-color-scheme:dark) {{
  :root {{ --bg:#0a141c; --bg-grid:rgba(220,232,238,.05); --surface:#101f29; --surface-2:#16303e;
    --ink:#e3edf1; --ink-muted:#8aa2b0; --ink-faint:#5a7482;
    --accent:#4a8aa3; --accent-strong:#8fd0e6; --accent-soft:rgba(74,138,163,.20);
    --flag:#a8b478; --flag-strong:#cddb9e; --flag-soft:rgba(168,180,120,.18);
    --warn:#d97a6a; --warn-soft:rgba(217,122,106,.14);
    --line:rgba(220,232,238,.14); --line-strong:rgba(220,232,238,.26);
    --shadow:0 1px 2px rgba(0,0,0,.35),0 14px 32px -16px rgba(0,0,0,.6); color-scheme:dark; }}
}}
:root[data-theme="dark"] {{ --bg:#0a141c; --bg-grid:rgba(220,232,238,.05); --surface:#101f29; --surface-2:#16303e;
  --ink:#e3edf1; --ink-muted:#8aa2b0; --ink-faint:#5a7482;
  --accent:#4a8aa3; --accent-strong:#8fd0e6; --accent-soft:rgba(74,138,163,.20);
  --flag:#a8b478; --flag-strong:#cddb9e; --flag-soft:rgba(168,180,120,.18);
  --warn:#d97a6a; --warn-soft:rgba(217,122,106,.14);
  --line:rgba(220,232,238,.14); --line-strong:rgba(220,232,238,.26);
  --shadow:0 1px 2px rgba(0,0,0,.35),0 14px 32px -16px rgba(0,0,0,.6); color-scheme:dark; }}
:root[data-theme="light"] {{ --bg:#e4eaed; --bg-grid:rgba(13,26,36,.05); --surface:#fff; --surface-2:#d6dfe4;
  --ink:#0f1e28; --ink-muted:#425c6b; --ink-faint:#6d8794;
  --accent:#35677d; --accent-strong:#1c4150; --accent-soft:rgba(53,103,125,.14);
  --flag:#6b7548; --flag-strong:#4a5232; --flag-soft:rgba(107,117,72,.15);
  --warn:#a83a2e; --warn-soft:rgba(168,58,46,.10);
  --line:rgba(13,26,36,.13); --line-strong:rgba(13,26,36,.24);
  --shadow:0 1px 2px rgba(13,26,36,.07),0 10px 28px -16px rgba(13,26,36,.28); color-scheme:light; }}

* {{ box-sizing:border-box; }}
html,body {{ margin:0; padding:0; }}
body {{ background:var(--bg); color:var(--ink); font-family:'IBM Plex Sans',system-ui,sans-serif; font-size:15px; line-height:1.5; -webkit-font-smoothing:antialiased; overflow-x:hidden; }}
.page {{ max-width:1240px; margin:0 auto; padding:36px 26px 64px; display:flex; flex-direction:column; gap:26px; }}

.masthead {{ position:relative; border:1px solid var(--line-strong); border-radius:6px;
  background:linear-gradient(var(--bg-grid) 1px,transparent 1px),linear-gradient(90deg,var(--bg-grid) 1px,transparent 1px),var(--surface);
  background-size:28px 28px,28px 28px,auto; padding:26px 30px 26px; overflow:hidden; }}
.masthead-top {{ display:flex; align-items:center; gap:16px; padding-bottom:16px; margin-bottom:16px; border-bottom:1px solid var(--line-strong); }}
.masthead-badge {{ flex-shrink:0; width:52px; height:52px; color:var(--accent-strong); }}
.masthead-badge svg {{ width:100%; height:100%; display:block; }}
.wordmark-primary {{ font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:16px; letter-spacing:.14em; text-transform:uppercase; color:var(--ink); }}
.wordmark-secondary {{ font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:.05em; color:var(--ink-faint); margin-top:3px; text-transform:uppercase; }}
.eyebrow {{ font-family:'IBM Plex Mono',monospace; font-size:11.5px; font-weight:500; letter-spacing:.09em; color:var(--accent-strong); text-transform:uppercase; margin-bottom:12px; }}
h1 {{ font-family:'IBM Plex Serif',Georgia,serif; font-weight:600; font-size:30px; letter-spacing:-.01em; margin:0 0 8px; text-wrap:balance; }}
.dek {{ margin:0; max-width:78ch; color:var(--ink-muted); font-size:14px; line-height:1.6; }}

.tabnav {{ display:flex; gap:2px; border-bottom:1px solid var(--line-strong); padding:0 2px; overflow-x:auto; }}
.tab-btn {{ appearance:none; border:none; background:transparent; font-family:'IBM Plex Sans',sans-serif; font-weight:500; font-size:12.5px; color:var(--ink-muted); padding:11px 12px 10px; cursor:pointer; border-bottom:2px solid transparent; margin-bottom:-1px; white-space:nowrap; }}
.tab-btn:hover {{ color:var(--ink); }}
.tab-btn[aria-selected="true"] {{ color:var(--ink); border-bottom-color:var(--accent-strong); }}
.tabpanel {{ display:none; flex-direction:column; gap:22px; }}
.tabpanel.is-active {{ display:flex; }}

.kpi-row {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }}
.kpi {{ background:var(--surface); border:1px solid var(--line); border-radius:6px; padding:14px 16px; display:flex; flex-direction:column; gap:4px; box-shadow:var(--shadow); }}
.kpi-label {{ font-family:'IBM Plex Mono',monospace; font-size:10px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-faint); }}
.kpi-value {{ font-weight:600; font-size:23px; color:var(--ink); font-variant-numeric:tabular-nums; }}
.kpi-sub {{ font-size:11.5px; color:var(--ink-muted); }}

.panel {{ background:var(--surface); border:1px solid var(--line); border-radius:6px; box-shadow:var(--shadow); padding:20px 22px 22px; }}
.panel-head {{ display:flex; align-items:baseline; justify-content:space-between; gap:14px; margin-bottom:14px; flex-wrap:wrap; }}
.panel-head h2 {{ font-weight:600; font-size:15px; margin:0; }}
.panel-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
@media (max-width:860px) {{ .panel-grid {{ grid-template-columns:1fr; }} .kpi-row {{ grid-template-columns:repeat(2,1fr); }} }}

.callout {{ display:flex; gap:12px; border:1px solid var(--accent); background:var(--accent-soft); border-radius:6px; padding:14px 18px; }}
.callout-mark {{ font-family:'IBM Plex Serif',serif; font-weight:600; font-size:14px; color:var(--accent-strong); flex-shrink:0; width:20px; height:20px; border:1.5px solid var(--accent-strong); border-radius:50%; display:flex; align-items:center; justify-content:center; }}
.callout-body p {{ margin:0 0 5px; font-size:12.5px; line-height:1.6; }}
.callout-body p:last-child {{ margin-bottom:0; }}

.bars {{ display:flex; flex-direction:column; gap:3px; }}
.bar-row {{ display:grid; grid-template-columns:220px 1fr 130px; align-items:center; gap:12px; padding:6px 7px; border-radius:4px; }}
.bar-row:hover {{ background:var(--accent-soft); }}
.bar-name {{ font-size:12.5px; font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.bar-track {{ height:14px; background:var(--surface-2); border-radius:3px; padding:2px; }}
.bar-fill {{ height:100%; border-radius:2px; background:var(--accent); min-width:2px; }}
.bar-figures {{ display:flex; justify-content:flex-end; gap:8px; font-family:'IBM Plex Mono',monospace; font-size:11.5px; white-space:nowrap; }}
.bar-pct {{ color:var(--ink-faint); width:56px; text-align:right; }}

table {{ width:100%; border-collapse:collapse; font-size:12px; }}
thead th {{ text-align:left; font-family:'IBM Plex Mono',monospace; font-size:9.5px; letter-spacing:.05em; text-transform:uppercase; color:var(--ink-faint); font-weight:500; padding:0 8px 8px; border-bottom:1px solid var(--line-strong); white-space:nowrap; position:sticky; top:0; background:var(--surface); }}
thead th.num {{ text-align:right; }}
tbody td {{ padding:8px; border-bottom:1px solid var(--line); vertical-align:top; }}
tbody tr:hover {{ background:var(--accent-soft); }}
td.num {{ text-align:right; font-family:'IBM Plex Mono',monospace; font-variant-numeric:tabular-nums; white-space:nowrap; }}
.table-scroll {{ overflow:auto; max-height:520px; border:1px solid var(--line); border-radius:6px; }}

.finding {{ border:1px solid var(--line-strong); border-radius:6px; padding:14px 18px; background:var(--surface-2); font-size:12.5px; line-height:1.6; color:var(--ink-muted); margin-bottom:8px; }}
.finding:last-child {{ margin-bottom:0; }}
.finding strong {{ color:var(--ink); }}
.finding.warn {{ border-color:var(--warn); background:var(--warn-soft); }}

.card {{ border:1px solid var(--line); border-radius:6px; padding:14px 16px; background:var(--surface-2); display:flex; flex-direction:column; gap:8px; }}
.card-title {{ font-weight:600; font-size:13px; }}
.card-amt {{ font-family:'IBM Plex Mono',monospace; font-size:16px; font-weight:600; color:var(--accent-strong); }}
.reason-pill {{ display:inline-block; font-size:10.5px; font-family:'IBM Plex Mono',monospace; padding:3px 8px; border-radius:8px; background:var(--flag-soft); color:var(--flag-strong); margin:2px 4px 0 0; }}
.card-list {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
@media (max-width:860px) {{ .card-list {{ grid-template-columns:1fr; }} }}

.cd-toolbar {{ display:flex; align-items:center; gap:10px; margin-bottom:12px; flex-wrap:wrap; }}
.cd-search input {{ width:100%; min-width:220px; font-family:'IBM Plex Sans',sans-serif; font-size:12.5px; padding:8px 12px; border:1px solid var(--line-strong); border-radius:6px; background:var(--surface); color:var(--ink); }}
.cd-search input:focus {{ outline:none; border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft); }}
.cd-count {{ font-family:'IBM Plex Mono',monospace; font-size:11px; color:var(--ink-faint); white-space:nowrap; }}
.cd-download {{ font-family:'IBM Plex Mono',monospace; font-size:11px; padding:7px 12px; border-radius:6px; border:1px solid var(--line-strong); background:var(--surface); cursor:pointer; }}
.cd-download:hover {{ background:var(--accent-soft); }}
.month-chart {{ display:flex; align-items:stretch; gap:6px; height:200px; padding-top:8px; position:relative; }}
.month-col {{ flex:1; display:flex; flex-direction:column; align-items:center; min-width:0; }}
.month-bar-track {{ flex:1; width:100%; display:flex; align-items:flex-end; justify-content:center; }}
.month-bar {{ width:60%; border-radius:3px 3px 0 0; background:var(--accent); min-height:2px; }}
.month-col.is-peak .month-bar {{ background:var(--accent-strong); }}
.month-label {{ margin-top:6px; font-family:'IBM Plex Mono',monospace; font-size:10px; color:var(--ink); }}
.month-amt {{ font-family:'IBM Plex Mono',monospace; font-size:9px; color:var(--ink-faint); }}
.methodology {{ border:1px dashed var(--line-strong); border-radius:6px; padding:18px 22px; }}
.methodology h3 {{ font-family:'IBM Plex Mono',monospace; font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-faint); margin:0 0 10px; }}
.methodology ul {{ margin:0; padding-left:16px; color:var(--ink-muted); font-size:12px; line-height:1.7; }}
.supplier-search-result {{ padding:8px 10px; border-radius:4px; cursor:pointer; font-size:12.5px; }}
.supplier-search-result:hover {{ background:var(--accent-soft); }}
.new-badge {{ font-family:'IBM Plex Mono',monospace; font-size:9px; background:var(--accent); color:var(--surface); padding:2px 6px; border-radius:6px; margin-left:6px; }}
</style>
"""
print("Head HTML built:", len(head_html), "chars")

# ============================================================
# JS
# ============================================================
script_html = f"""
<script>
const PAYLOAD = {payload_json};
const EXPLORER_ROWS = {explorer_json};
const NOBID_DETAIL = {nobid_detail_json};
const QOL_AWARDS = {qol_awards_json};
const HIGH_RISK_AWARDS = {high_risk_awards_json};
const FOREIGN_AWARDS = {foreign_awards_json};
const NICHE_AWARDS = {niche_awards_json};

// ---------- Tabs ----------
document.querySelectorAll(".tab-btn").forEach(btn => {{
  btn.addEventListener("click", () => {{
    document.querySelectorAll(".tab-btn").forEach(b => b.setAttribute("aria-selected", "false"));
    document.querySelectorAll(".tabpanel").forEach(p => p.classList.remove("is-active"));
    btn.setAttribute("aria-selected", "true");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("is-active");
  }});
}});

function fmtB(n) {{
  const abs = Math.abs(n);
  if (abs < 1e9) return "$" + (n/1e6).toLocaleString(undefined,{{maximumFractionDigits:1}}) + "M";
  if (abs < 1e12) return "$" + (n/1e9).toLocaleString(undefined,{{maximumFractionDigits:1}}) + "B";
  return "$" + (n/1e12).toLocaleString(undefined,{{maximumFractionDigits:2}}) + "T";
}}
function esc(s) {{
  if (s === null || s === undefined) return "";
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}}
function csvCell(s) {{
  const v = String(s === null || s === undefined ? "" : s);
  return '"' + v.replace(/"/g, '""') + '"';
}}
function downloadCsv(filename, headers, rows) {{
  const lines = [headers.map(csvCell).join(",")];
  rows.forEach(r => lines.push(r.map(csvCell).join(",")));
  const blob = new Blob([lines.join("\\r\\n")], {{type: "text/csv;charset=utf-8;"}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}}

// ---------- Transaction Explorer ----------
const explorerBody = document.getElementById("explorer-tbody");
const explorerSearch = document.getElementById("explorer-search");
const explorerCount = document.getElementById("explorer-count");

function renderExplorer() {{
  const q = explorerSearch.value.trim().toLowerCase();
  const filtered = q ? EXPLORER_ROWS.filter(r =>
    (r.normalized_supplier||"").toLowerCase().includes(q) ||
    (r.award_id_piid||"").toLowerCase().includes(q) ||
    (r.transaction_description||"").toLowerCase().includes(q) ||
    (r.ai_spend_category||"").toLowerCase().includes(q) ||
    (r.ai_spend_subcategory||"").toLowerCase().includes(q) ||
    (r.naics_description||"").toLowerCase().includes(q)
  ) : EXPLORER_ROWS;
  explorerCount.textContent = filtered.length.toLocaleString() + " of " + EXPLORER_ROWS.length.toLocaleString();
  const rowsHtml = filtered.slice(0, 500).map(r => (
    "<tr><td>" + esc(r.fiscal_year) + "</td><td>" + esc(r.action_date) + "</td><td>" + esc(r.normalized_supplier) +
    "</td><td>" + esc(r.award_id_piid) + "</td><td class='num'>" + fmtB(r.net_obligations) + "</td><td>" + esc(r.ai_spend_category) +
    "</td><td>" + esc(r.naics_description) + "</td><td>" + esc((r.transaction_description||"").slice(0,120)) +
    "</td><td>" + esc(r.extent_competed) + "</td><td>" + esc(r.awarding_sub_agency_name) + "</td></tr>"
  )).join("");
  explorerBody.innerHTML = rowsHtml;
}}
explorerSearch.addEventListener("input", renderExplorer);
document.getElementById("explorer-download").addEventListener("click", () => {{
  const q = explorerSearch.value.trim().toLowerCase();
  const filtered = q ? EXPLORER_ROWS.filter(r =>
    (r.normalized_supplier||"").toLowerCase().includes(q) ||
    (r.award_id_piid||"").toLowerCase().includes(q) ||
    (r.transaction_description||"").toLowerCase().includes(q) ||
    (r.ai_spend_category||"").toLowerCase().includes(q)
  ) : EXPLORER_ROWS;
  downloadCsv("dod_transaction_explorer.csv",
    ["fiscal_year","action_date","supplier","award_id","net_obligations","category","subcategory","naics_description","description","extent_competed","sub_agency"],
    filtered.map(r => [r.fiscal_year, r.action_date, r.normalized_supplier, r.award_id_piid, r.net_obligations, r.ai_spend_category, r.ai_spend_subcategory, r.naics_description, r.transaction_description, r.extent_competed, r.awarding_sub_agency_name]));
}});
renderExplorer();

// ---------- Supplier Analysis ----------
const supplierSearch = document.getElementById("supplier-search");
const supplierResults = document.getElementById("supplier-search-results");
const supplierDetailPanel = document.getElementById("supplier-detail-panel");
const supplierDetailName = document.getElementById("supplier-detail-name");
const supplierDetailBody = document.getElementById("supplier-detail-body");
const supplierNames = Object.keys(PAYLOAD.suppliers_detail);

function renderSupplierResults() {{
  const q = supplierSearch.value.trim().toLowerCase();
  if (!q) {{ supplierResults.innerHTML = ""; return; }}
  const matches = supplierNames.filter(n => n.toLowerCase().includes(q)).slice(0, 20);
  supplierResults.innerHTML = matches.map(n =>
    "<div class='supplier-search-result' data-name='" + esc(n) + "'>" + esc(n) + "</div>"
  ).join("") || "<div style='font-size:12px;color:var(--ink-faint)'>No suppliers with total value at or above $5M matched (smaller suppliers aren't included in this lookup).</div>";
  supplierResults.querySelectorAll(".supplier-search-result").forEach(el => {{
    el.addEventListener("click", () => showSupplier(el.dataset.name));
  }});
}}
function showSupplier(name) {{
  const d = PAYLOAD.suppliers_detail[name];
  if (!d) return;
  supplierDetailPanel.style.display = "";
  supplierDetailName.textContent = name;
  const annualMax = Math.max(...d.annual.map(a => a.net_obligations), 1);
  const annualHtml = d.annual.map(a =>
    "<div class='month-col'><div class='month-bar-track'><div class='month-bar' style='height:" +
    Math.max(a.net_obligations/annualMax*100,2).toFixed(1) + "%'></div></div><div class='month-label'>FY" + a.fiscal_year +
    "</div><div class='month-amt'>" + fmtB(a.net_obligations) + "</div></div>"
  ).join("");
  const catHtml = d.category_mix.slice(0,8).map(c =>
    "<div class='bar-row'><div class='bar-name'>" + esc(c.category) + "</div><div class='bar-track'><div class='bar-fill' style='width:" +
    Math.max(c.net_obligations/d.category_mix[0].net_obligations*100,1).toFixed(1) + "%'></div></div><div class='bar-figures'><span>" +
    fmtB(c.net_obligations) + "</span></div></div>"
  ).join("");
  supplierDetailBody.innerHTML =
    "<div class='kpi-row'>" +
    "<div class='kpi'><div class='kpi-label'>Total Value</div><div class='kpi-value'>" + fmtB(d.total_net_obligations) + "</div></div>" +
    "<div class='kpi'><div class='kpi-label'>Share of Total</div><div class='kpi-value'>" + (d.share_of_agency_obligations*100).toFixed(1) + "%</div></div>" +
    "<div class='kpi'><div class='kpi-label'>Unique Awards</div><div class='kpi-value'>" + d.unique_awards.toLocaleString() + "</div></div>" +
    "<div class='kpi'><div class='kpi-label'>Awarding Offices</div><div class='kpi-value'>" + d.awarding_offices.length.toLocaleString() + "</div></div>" +
    "</div><div class='panel-grid' style='margin-top:16px'>" +
    "<div><h3 style='font-size:12px;color:var(--ink-faint);text-transform:uppercase;letter-spacing:.05em'>Annual Trend</h3><div class='month-chart' style='height:140px'>" + annualHtml + "</div></div>" +
    "<div><h3 style='font-size:12px;color:var(--ink-faint);text-transform:uppercase;letter-spacing:.05em'>Category Mix</h3><div class='bars'>" + catHtml + "</div></div>" +
    "</div>" +
    (d.raw_name_variants.length > 1 ? "<p style='font-size:11px;color:var(--ink-faint);margin-top:14px'>Resolved from " + d.raw_name_variants.length + " raw recipient name variant(s): " + esc(d.raw_name_variants.slice(0,6).join(", ")) + (d.raw_name_variants.length > 6 ? ", ..." : "") + "</p>" : "");
}}
supplierSearch.addEventListener("input", renderSupplierResults);

// ---------- No-Bid Contract Detail ----------
const nobidBody = document.getElementById("nobid-tbody");
const nobidSearch = document.getElementById("nobid-search");
const nobidCount = document.getElementById("nobid-count");

function renderNobid() {{
  const q = nobidSearch.value.trim().toLowerCase();
  const filtered = q ? NOBID_DETAIL.filter(r =>
    (r.vendor||"").toLowerCase().includes(q) ||
    (r.award_id||"").toLowerCase().includes(q) ||
    (r.description||"").toLowerCase().includes(q) ||
    (r.psc_description||"").toLowerCase().includes(q) ||
    (r.branch_short||"").toLowerCase().includes(q)
  ) : NOBID_DETAIL;
  nobidCount.textContent = filtered.length.toLocaleString() + " of " + NOBID_DETAIL.length.toLocaleString();
  nobidBody.innerHTML = filtered.slice(0, 500).map(r => (
    "<tr><td>" + esc(r.award_id) + "</td><td>" + esc(r.vendor) + "</td><td class='num'>" + fmtB(r.amount) +
    "</td><td>" + esc(r.branch_short) + "</td><td>" + esc(r.extent_competed) + "</td><td>" + esc(r.type_of_contract_pricing) +
    "</td><td>" + esc(r.award_date) + "</td><td>" + esc(r.psc_description) + "</td><td>" + esc((r.description||"").slice(0,140)) + "</td></tr>"
  )).join("");
}}
nobidSearch.addEventListener("input", renderNobid);
document.getElementById("nobid-download").addEventListener("click", () => {{
  const q = nobidSearch.value.trim().toLowerCase();
  const filtered = q ? NOBID_DETAIL.filter(r =>
    (r.vendor||"").toLowerCase().includes(q) ||
    (r.award_id||"").toLowerCase().includes(q) ||
    (r.description||"").toLowerCase().includes(q)
  ) : NOBID_DETAIL;
  downloadCsv("dod_nobid_contracts.csv",
    ["award_id","vendor","vendor_uei","amount","branch","extent_competed","contract_type","award_date","psc_description","naics_description","description"],
    filtered.map(r => [r.award_id, r.vendor, r.vendor_uei, r.amount, r.branch_short, r.extent_competed, r.type_of_contract_pricing, r.award_date, r.psc_description, r.naics_description, r.description]));
}});
renderNobid();

// ---------- Quality of Life Award Detail ----------
const qolBody = document.getElementById("qol-tbody");
const qolSearch = document.getElementById("qol-search");
const qolBranchFilter = document.getElementById("qol-branch-filter");
const qolCount = document.getElementById("qol-count");

function filterQol() {{
  const q = qolSearch.value.trim().toLowerCase();
  const branch = qolBranchFilter.value;
  return QOL_AWARDS.filter(r => {{
    if (branch && r.branch !== branch) return false;
    if (!q) return true;
    return (r.supplier||"").toLowerCase().includes(q) ||
      (r.award_id||"").toLowerCase().includes(q) ||
      (r.category||"").toLowerCase().includes(q) ||
      (r.description||"").toLowerCase().includes(q);
  }});
}}
function renderQol() {{
  const filtered = filterQol();
  qolCount.textContent = filtered.length.toLocaleString() + " of " + QOL_AWARDS.length.toLocaleString();
  qolBody.innerHTML = filtered.slice(0, 500).map(r => (
    "<tr><td>" + esc(r.award_id) + "</td><td>" + esc(r.branch) + "</td><td>" + esc(r.branch_adjusted) +
    "</td><td>" + esc(r.category) + "</td><td>" + esc(r.supplier) + "</td><td class='num'>" + fmtB(r.amount) +
    "</td><td>" + esc(r.date) + "</td><td>" + esc(r.extent_competed) + "</td><td>" + esc((r.description||"").slice(0,140)) + "</td></tr>"
  )).join("");
}}
qolSearch.addEventListener("input", renderQol);
qolBranchFilter.addEventListener("change", renderQol);
document.getElementById("qol-download").addEventListener("click", () => {{
  const filtered = filterQol();
  downloadCsv("dod_quality_of_life_awards.csv",
    ["award_id","branch_as_awarded","branch_adjusted","category","supplier","amount","date","extent_competed","awarding_sub_agency","description"],
    filtered.map(r => [r.award_id, r.branch, r.branch_adjusted, r.category, r.supplier, r.amount, r.date, r.extent_competed, r.awarding_sub_agency, r.description]));
}});
renderQol();

// ---------- Sole-Source Pricing Risk Detail ----------
const riskBody = document.getElementById("risk-tbody");
const riskSearch = document.getElementById("risk-search");
const riskMegaFilter = document.getElementById("risk-mega-filter");
const riskCount = document.getElementById("risk-count");

function filterRisk() {{
  const q = riskSearch.value.trim().toLowerCase();
  const mega = riskMegaFilter.value;
  return HIGH_RISK_AWARDS.filter(r => {{
    if (mega === "sub" && r.is_mega) return false;
    if (mega === "mega" && !r.is_mega) return false;
    if (!q) return true;
    return (r.supplier||"").toLowerCase().includes(q) ||
      (r.award_id||"").toLowerCase().includes(q) ||
      (r.category||"").toLowerCase().includes(q) ||
      (r.justification||"").toLowerCase().includes(q) ||
      (r.description||"").toLowerCase().includes(q);
  }});
}}
function renderRisk() {{
  const filtered = filterRisk();
  riskCount.textContent = filtered.length.toLocaleString() + " of " + HIGH_RISK_AWARDS.length.toLocaleString();
  riskBody.innerHTML = filtered.slice(0, 500).map(r => (
    "<tr><td>" + esc(r.award_id) + "</td><td>" + esc(r.supplier) + "</td><td>" + esc(r.category) +
    "</td><td>" + esc(r.pricing_type) + "</td><td>" + esc(r.justification) + "</td><td class='num'>" + fmtB(r.amount) +
    "</td><td>" + esc(r.date) + "</td><td>" + esc(r.awarding_sub_agency) + "</td><td>" + esc((r.description||"").slice(0,140)) + "</td></tr>"
  )).join("");
}}
riskSearch.addEventListener("input", renderRisk);
riskMegaFilter.addEventListener("change", renderRisk);
document.getElementById("risk-download").addEventListener("click", () => {{
  const filtered = filterRisk();
  downloadCsv("dod_sole_source_pricing_risk.csv",
    ["award_id","supplier","category","pricing_type","justification","amount","is_mega","date","awarding_sub_agency","description"],
    filtered.map(r => [r.award_id, r.supplier, r.category, r.pricing_type, r.justification, r.amount, r.is_mega, r.date, r.awarding_sub_agency, r.description]));
}});
renderRisk();

// ---------- Foreign Vendor Award Detail ----------
const foreignBody = document.getElementById("foreign-tbody");
const foreignSearch = document.getElementById("foreign-search");
const foreignCompetedFilter = document.getElementById("foreign-competed-filter");
const foreignCount = document.getElementById("foreign-count");

function filterForeign() {{
  const q = foreignSearch.value.trim().toLowerCase();
  const competed = foreignCompetedFilter.value;
  return FOREIGN_AWARDS.filter(r => {{
    if (competed && r.competed_bucket !== competed) return false;
    if (!q) return true;
    return (r.supplier||"").toLowerCase().includes(q) ||
      (r.award_id||"").toLowerCase().includes(q) ||
      (r.country||"").toLowerCase().includes(q) ||
      (r.category||"").toLowerCase().includes(q) ||
      (r.description||"").toLowerCase().includes(q);
  }});
}}
function renderForeign() {{
  const filtered = filterForeign();
  foreignCount.textContent = filtered.length.toLocaleString() + " of " + FOREIGN_AWARDS.length.toLocaleString();
  foreignBody.innerHTML = filtered.slice(0, 500).map(r => (
    "<tr><td>" + esc(r.award_id) + "</td><td>" + esc(r.supplier) + "</td><td>" + esc(r.country) +
    "</td><td>" + esc(r.category) + "</td><td>" + esc(r.competed_bucket) + "</td><td class='num'>" + fmtB(r.amount) +
    "</td><td>" + esc(r.date) + "</td><td>" + esc(r.pop_country) + "</td><td>" + esc((r.description||"").slice(0,140)) + "</td></tr>"
  )).join("");
}}
foreignSearch.addEventListener("input", renderForeign);
foreignCompetedFilter.addEventListener("change", renderForeign);
document.getElementById("foreign-download").addEventListener("click", () => {{
  const filtered = filterForeign();
  downloadCsv("dod_foreign_vendor_awards.csv",
    ["award_id","supplier","country","category","competed_status","extent_competed","amount","date","pop_country","awarding_sub_agency","description"],
    filtered.map(r => [r.award_id, r.supplier, r.country, r.category, r.competed_bucket, r.extent_competed, r.amount, r.date, r.pop_country, r.awarding_sub_agency, r.description]));
}});
renderForeign();

// ---------- Concentrated Vendor Niche Award Detail ----------
const nicheBody = document.getElementById("niche-tbody");
const nicheSearch = document.getElementById("niche-search");
const nicheCount = document.getElementById("niche-count");

function filterNiche() {{
  const q = nicheSearch.value.trim().toLowerCase();
  if (!q) return NICHE_AWARDS;
  return NICHE_AWARDS.filter(r =>
    (r.supplier||"").toLowerCase().includes(q) ||
    (r.award_id||"").toLowerCase().includes(q) ||
    (r.country||"").toLowerCase().includes(q) ||
    (r.category||"").toLowerCase().includes(q) ||
    (r.description||"").toLowerCase().includes(q)
  );
}}
function renderNiche() {{
  const filtered = filterNiche();
  nicheCount.textContent = filtered.length.toLocaleString() + " of " + NICHE_AWARDS.length.toLocaleString();
  nicheBody.innerHTML = filtered.slice(0, 500).map(r => (
    "<tr><td>" + esc(r.award_id) + "</td><td>" + esc(r.supplier) + "</td><td>" + esc(r.country) +
    "</td><td>" + esc(r.category) + "</td><td>" + esc(r.competed_bucket) + "</td><td class='num'>" + fmtB(r.amount) +
    "</td><td>" + esc(r.date) + "</td><td>" + esc(r.awarding_sub_agency) + "</td><td>" + esc((r.description||"").slice(0,140)) + "</td></tr>"
  )).join("");
}}
nicheSearch.addEventListener("input", renderNiche);
document.getElementById("niche-download").addEventListener("click", () => {{
  const filtered = filterNiche();
  downloadCsv("dod_concentrated_vendor_niches.csv",
    ["award_id","supplier","country","category","competed_status","extent_competed","amount","date","awarding_sub_agency","description"],
    filtered.map(r => [r.award_id, r.supplier, r.country, r.category, r.competed_bucket, r.extent_competed, r.amount, r.date, r.awarding_sub_agency, r.description]));
}});
renderNiche();
</script>
"""
print("Script HTML built:", len(script_html), "chars")

full_html = head_html + body_html + script_html
OUT_PATH = r"C:\finances\DoD_v2\dod_v2_procurement_dashboard.html"
with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(full_html)
print(f"\nWrote {OUT_PATH} ({len(full_html)/1e6:.1f}MB)")
