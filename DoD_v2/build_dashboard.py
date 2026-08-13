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
# HTML BODY (masthead + tab nav + 7 tab panels)
# ============================================================
body_html = f"""
<div class="page">
  <header class="masthead">
    <div class="eyebrow">DoD_v2 &middot; Educational Procurement Intelligence Project</div>
    <h1>DoD Procurement Intelligence Dashboard</h1>
    <p class="dek">{P["meta"]["disclosure"]} Data period {P["meta"]["data_period_start"]} through {P["meta"]["data_period_end"]}, covering {TOTALS["transaction_count"]:,} definitive contract awards from USAspending.gov's bulk award-download API.</p>
    <div class="scope-banner"><b>Read this before the numbers below:</b> {META_NOTE}</div>
  </header>

  <nav class="tabnav" role="tablist">
    <button class="tab-btn" data-tab="overview" aria-selected="true" role="tab">Executive Overview</button>
    <button class="tab-btn" data-tab="standout" role="tab">Standout Suppliers &amp; Contracts</button>
    <button class="tab-btn" data-tab="yoy" role="tab">Year-over-Year Trends</button>
    <button class="tab-btn" data-tab="explorer" role="tab">Transaction Explorer</button>
    <button class="tab-btn" data-tab="supplier" role="tab">Supplier Analysis</button>
    <button class="tab-btn" data-tab="categories" role="tab">Categories &amp; Opportunities</button>
    <button class="tab-btn" data-tab="nobid" role="tab">No-Bid Contracts<span class="new-badge">unique</span></button>
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
  --bg:#eef2f2; --bg-grid:rgba(20,36,51,.05); --surface:#fff; --surface-2:#e3e9ea;
  --ink:#142433; --ink-muted:#4c6070; --ink-faint:#7c8e9a;
  --accent:#0f8aa3; --accent-strong:#0a5c6c; --accent-soft:rgba(15,138,163,.13);
  --flag:#8a3fd1; --flag-strong:#6a24ac; --flag-soft:rgba(138,63,209,.12);
  --warn:#b3261e; --warn-soft:rgba(179,38,30,.10);
  --line:rgba(20,36,51,.13); --line-strong:rgba(20,36,51,.24);
  --shadow:0 1px 2px rgba(20,36,51,.07),0 10px 28px -16px rgba(20,36,51,.28);
  color-scheme:light;
}}
@media (prefers-color-scheme:dark) {{
  :root {{ --bg:#0c1a24; --bg-grid:rgba(234,241,242,.05); --surface:#132633; --surface-2:#1a3140;
    --ink:#eaf1f2; --ink-muted:#92a8b6; --ink-faint:#5f7986;
    --accent:#1f96b3; --accent-strong:#6fd2e8; --accent-soft:rgba(31,150,179,.20);
    --flag:#9c5fe0; --flag-strong:#c8a4ee; --flag-soft:rgba(156,95,224,.22);
    --warn:#e2645c; --warn-soft:rgba(226,100,92,.14);
    --line:rgba(234,241,242,.14); --line-strong:rgba(234,241,242,.26);
    --shadow:0 1px 2px rgba(0,0,0,.35),0 14px 32px -16px rgba(0,0,0,.6); color-scheme:dark; }}
}}
:root[data-theme="dark"] {{ --bg:#0c1a24; --bg-grid:rgba(234,241,242,.05); --surface:#132633; --surface-2:#1a3140;
  --ink:#eaf1f2; --ink-muted:#92a8b6; --ink-faint:#5f7986;
  --accent:#1f96b3; --accent-strong:#6fd2e8; --accent-soft:rgba(31,150,179,.20);
  --flag:#9c5fe0; --flag-strong:#c8a4ee; --flag-soft:rgba(156,95,224,.22);
  --warn:#e2645c; --warn-soft:rgba(226,100,92,.14);
  --line:rgba(234,241,242,.14); --line-strong:rgba(234,241,242,.26);
  --shadow:0 1px 2px rgba(0,0,0,.35),0 14px 32px -16px rgba(0,0,0,.6); color-scheme:dark; }}
:root[data-theme="light"] {{ --bg:#eef2f2; --bg-grid:rgba(20,36,51,.05); --surface:#fff; --surface-2:#e3e9ea;
  --ink:#142433; --ink-muted:#4c6070; --ink-faint:#7c8e9a;
  --accent:#0f8aa3; --accent-strong:#0a5c6c; --accent-soft:rgba(15,138,163,.13);
  --flag:#8a3fd1; --flag-strong:#6a24ac; --flag-soft:rgba(138,63,209,.12);
  --warn:#b3261e; --warn-soft:rgba(179,38,30,.10);
  --line:rgba(20,36,51,.13); --line-strong:rgba(20,36,51,.24);
  --shadow:0 1px 2px rgba(20,36,51,.07),0 10px 28px -16px rgba(20,36,51,.28); color-scheme:light; }}

* {{ box-sizing:border-box; }}
html,body {{ margin:0; padding:0; }}
body {{ background:var(--bg); color:var(--ink); font-family:'IBM Plex Sans',system-ui,sans-serif; font-size:15px; line-height:1.5; -webkit-font-smoothing:antialiased; overflow-x:hidden; }}
.page {{ max-width:1240px; margin:0 auto; padding:36px 26px 64px; display:flex; flex-direction:column; gap:26px; }}

.masthead {{ position:relative; border:1px solid var(--line-strong); border-radius:6px;
  background:linear-gradient(var(--bg-grid) 1px,transparent 1px),linear-gradient(90deg,var(--bg-grid) 1px,transparent 1px),var(--surface);
  background-size:28px 28px,28px 28px,auto; padding:30px 30px 26px; overflow:hidden; }}
.eyebrow {{ font-family:'IBM Plex Mono',monospace; font-size:11.5px; font-weight:500; letter-spacing:.09em; color:var(--accent-strong); text-transform:uppercase; margin-bottom:12px; }}
h1 {{ font-family:'IBM Plex Serif',Georgia,serif; font-weight:600; font-size:30px; letter-spacing:-.01em; margin:0 0 8px; text-wrap:balance; }}
.dek {{ margin:0; max-width:78ch; color:var(--ink-muted); font-size:14px; line-height:1.6; }}
.scope-banner {{ margin-top:14px; padding:12px 16px; border:1px solid var(--warn); background:var(--warn-soft); border-radius:6px; font-size:12.5px; color:var(--ink); line-height:1.6; }}
.scope-banner b {{ color:var(--warn); }}

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
</script>
"""
print("Script HTML built:", len(script_html), "chars")

full_html = head_html + body_html + script_html
OUT_PATH = r"C:\finances\DoD_v2\dod_v2_procurement_dashboard.html"
with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(full_html)
print(f"\nWrote {OUT_PATH} ({len(full_html)/1e6:.1f}MB)")
