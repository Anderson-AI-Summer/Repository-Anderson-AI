# -*- coding: utf-8 -*-
import json

FDIR = r"C:\finances\data\sba_loans\fonts"

def b64(name):
    with open(rf"{FDIR}\{name}.b64", "r") as f:
        return f.read().strip()

SANS400 = b64("sans400")
SANS500 = b64("sans500")
SANS600 = b64("sans600")
MONO400 = b64("mono400")
MONO500 = b64("mono500")
SERIF600 = b64("serif600")

with open(r"C:\finances\data\sba_loans\_data_fullrange.json") as f:
    DATA = json.load(f)

TOTAL = DATA["total"]
ROWS = DATA["rows"]
NAICS_COVERAGE_PCT = 91.5

with open(r"C:\finances\data\sba_loans\_vendor_tab_data_fullrange.json") as f:
    VENDOR_ROWS = json.load(f)

TOP30_SUM = sum(r["total"] for r in VENDOR_ROWS)
FLAGGED_COUNT = sum(1 for r in VENDOR_ROWS if r["tier"] == "flag")
WATCH_COUNT = sum(1 for r in VENDOR_ROWS if r["tier"] == "watch")
TOP_VENDOR = VENDOR_ROWS[0]

with open(r"C:\finances\data\sba_loans\_procurement_patterns_fullrange.json") as f:
    PP = json.load(f)
MONTHLY_ROWS = [{"month": row["month"], "total": row["avg"], "vs_avg_pct": row["vs_avg_pct"],
                  "noncompete": row["noncompete_avg"], "noncompete_pct": row["noncompete_pct"]}
                 for row in PP["seasonal_avg_rows"]]
MONTHLY_AVG = PP["seasonal_avg_overall"]
PEAK_MONTH = max(MONTHLY_ROWS, key=lambda r: r["total"])
SEP_ROW = next(r for r in MONTHLY_ROWS if r["month"] == "Sep")
PEAK_NC_MONTH = max(MONTHLY_ROWS, key=lambda r: r["noncompete_pct"])
COMPLETE_YEARS = PP["complete_years"]
YEARLY_TOTALS = PP["yearly_totals"]
YEAR_ROWS = [{"year": f"FY{y}" + (" YTD" if y == "2026" else ""), "total": v} for y, v in sorted(YEARLY_TOTALS.items())]
YEAR_MAX_ROW = max(YEAR_ROWS, key=lambda r: r["total"])

with open(r"C:\finances\data\sba_loans\_costtype_by_vendor_fullrange.json") as f:
    COSTTYPE_ROWS_RAW = json.load(f)
# "L3Harris Technologies, Inc." is excluded: recipient_search_text over-matches its
# substring "L3Harris Technologies Integrated Systems L.P." too, inflating its cost-type
# share past 100% (a text-matching artifact, not a real >100% share).
COSTTYPE_ROWS = sorted(
    [{"name": r["name"], "total": r["total"], "cost_type_amt": r["cost_type_amt"],
      "cost_type_share": r["cost_type_share"]} for r in COSTTYPE_ROWS_RAW
     if r["cost_type_share"] <= 100.0],
    key=lambda r: -r["cost_type_share"]
)
COST_TYPE_TOTAL = 847383907375.24
FIXED_PRICE_TOTAL = 2020876169808.61
CONTRACT_TOTAL_ALL = 2891607797040.08
FULL_COST_TYPE_VENDORS = sum(1 for r in COSTTYPE_ROWS if r["cost_type_share"] >= 99.5)

with open(r"C:\finances\data\sba_loans\_bunching_analysis_fullrange.json") as f:
    BUNCH = json.load(f)
BUNCH_VENDORS = BUNCH["vendor_summary"]
BUNCH_TOTAL_STANDALONE_DOLLARS = sum(v["dollars_in_standalone_clusters"] for v in BUNCH_VENDORS)
BUNCH_TOTAL_CLUSTERS = sum(v["clusters_standalone_or_mixed_parents"] for v in BUNCH_VENDORS)
BUNCH_TOP2 = sorted(BUNCH_VENDORS, key=lambda v: -v["clusters_standalone_or_mixed_parents"])[:2]

with open(r"C:\finances\data\sba_loans\_singlebid_final_fullrange.json") as f:
    SINGLEBID = json.load(f)

with open(r"C:\finances\data\sba_loans\_singlebid_detail_export_fullrange.json", encoding="utf-8") as f:
    CD_RECORDS = json.load(f)
CD_TOTAL_VALUE = sum(r["amount"] for r in CD_RECORDS)
CD_NEAR_COUNT = sum(1 for r in CD_RECORDS if r["near_threshold"])
CD_NEAR_VALUE = sum(r["amount"] for r in CD_RECORDS if r["near_threshold"])

with open(r"C:\finances\data\sba_loans\_drilldown_final_fullrange.json") as f:
    DRILLDOWN = json.load(f)
DD_ROWS = DRILLDOWN["rows"]
DD_TOTAL_COUNT = DRILLDOWN["total_count"]
DD_TOTAL_VALUE = DRILLDOWN["total_value"]
DD_NEAR_COUNT = DRILLDOWN["near_threshold_count"]
DD_NEAR_VALUE = DRILLDOWN["near_threshold_value"]
DD_BRANCH_NEAR = DRILLDOWN["branch_counts_near"]
DD_LELAND = DRILLDOWN["leland_records"]
SB_ROLLUP = SINGLEBID["vendor_rollup"]
SB_COUNT = SINGLEBID["single_bid_count"]
SB_VALUE = SINGLEBID["single_bid_total_value"]
SB_COMPETED_COUNT = SINGLEBID["all_competed_count"]
SB_COMPETED_VALUE = SINGLEBID["all_competed_value"]
SB_TOTAL_DEFINITIVE = SINGLEBID["total_definitive_contracts"]
SB_TOP_VENDOR = SB_ROLLUP[0]

def fmt_b(n):
    if abs(n) < 1e9:
        return f"${n/1e6:,.1f}M"
    return f"${n/1e9:,.1f}B"

def fmt_full(n):
    return f"${n:,.0f}"

rows_json = json.dumps(ROWS)
vendor_json = json.dumps(VENDOR_ROWS)
monthly_json = json.dumps(MONTHLY_ROWS)
year_json = json.dumps(YEAR_ROWS)
costtype_json = json.dumps(COSTTYPE_ROWS)
bunch_json = json.dumps(BUNCH_VENDORS)
singlebid_json = json.dumps(SB_ROLLUP)
drilldown_json = json.dumps(DD_ROWS)
branch_near_json = json.dumps(DD_BRANCH_NEAR)
cd_records_json = json.dumps(CD_RECORDS)

html = f"""<title>DoD FY2020-FY2026 YTD Spend Taxonomy</title>
<style>
@font-face {{
  font-family: 'IBM Plex Sans';
  font-weight: 400;
  font-style: normal;
  font-display: swap;
  src: url(data:font/woff2;base64,{SANS400}) format('woff2');
}}
@font-face {{
  font-family: 'IBM Plex Sans';
  font-weight: 500;
  font-style: normal;
  font-display: swap;
  src: url(data:font/woff2;base64,{SANS500}) format('woff2');
}}
@font-face {{
  font-family: 'IBM Plex Sans';
  font-weight: 600;
  font-style: normal;
  font-display: swap;
  src: url(data:font/woff2;base64,{SANS600}) format('woff2');
}}
@font-face {{
  font-family: 'IBM Plex Mono';
  font-weight: 400;
  font-style: normal;
  font-display: swap;
  src: url(data:font/woff2;base64,{MONO400}) format('woff2');
}}
@font-face {{
  font-family: 'IBM Plex Mono';
  font-weight: 500;
  font-style: normal;
  font-display: swap;
  src: url(data:font/woff2;base64,{MONO500}) format('woff2');
}}
@font-face {{
  font-family: 'IBM Plex Serif';
  font-weight: 600;
  font-style: normal;
  font-display: swap;
  src: url(data:font/woff2;base64,{SERIF600}) format('woff2');
}}

:root {{
  --bg: #eef2f2;
  --bg-grid: rgba(20,36,51,0.05);
  --surface: #ffffff;
  --surface-2: #e3e9ea;
  --ink: #142433;
  --ink-muted: #4c6070;
  --ink-faint: #7c8e9a;
  --accent: #0f8aa3;
  --accent-strong: #0a5c6c;
  --accent-soft: rgba(15,138,163,0.13);
  --residual: #c1793a;
  --residual-strong: #8f5726;
  --residual-soft: rgba(193,121,58,0.16);
  --flag: #8a3fd1;
  --flag-strong: #6a24ac;
  --flag-soft: rgba(138,63,209,0.12);
  --line: rgba(20,36,51,0.13);
  --line-strong: rgba(20,36,51,0.24);
  --shadow: 0 1px 2px rgba(20,36,51,0.07), 0 10px 28px -16px rgba(20,36,51,0.28);
  color-scheme: light;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #0c1a24;
    --bg-grid: rgba(234,241,242,0.05);
    --surface: #132633;
    --surface-2: #1a3140;
    --ink: #eaf1f2;
    --ink-muted: #92a8b6;
    --ink-faint: #5f7986;
    --accent: #1f96b3;
    --accent-strong: #6fd2e8;
    --accent-soft: rgba(31,150,179,0.20);
    --residual: #bd7f3f;
    --residual-strong: #e0a666;
    --residual-soft: rgba(189,127,63,0.22);
    --flag: #9c5fe0;
    --flag-strong: #c8a4ee;
    --flag-soft: rgba(156,95,224,0.22);
    --line: rgba(234,241,242,0.14);
    --line-strong: rgba(234,241,242,0.26);
    --shadow: 0 1px 2px rgba(0,0,0,0.35), 0 14px 32px -16px rgba(0,0,0,0.6);
    color-scheme: dark;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #0c1a24;
  --bg-grid: rgba(234,241,242,0.05);
  --surface: #132633;
  --surface-2: #1a3140;
  --ink: #eaf1f2;
  --ink-muted: #92a8b6;
  --ink-faint: #5f7986;
  --accent: #1f96b3;
  --accent-strong: #6fd2e8;
  --accent-soft: rgba(31,150,179,0.20);
  --residual: #bd7f3f;
  --residual-strong: #e0a666;
  --residual-soft: rgba(189,127,63,0.22);
  --flag: #9c5fe0;
  --flag-strong: #c8a4ee;
  --flag-soft: rgba(156,95,224,0.22);
  --line: rgba(234,241,242,0.14);
  --line-strong: rgba(234,241,242,0.26);
  --shadow: 0 1px 2px rgba(0,0,0,0.35), 0 14px 32px -16px rgba(0,0,0,0.6);
  color-scheme: dark;
}}
:root[data-theme="light"] {{
  --bg: #eef2f2;
  --bg-grid: rgba(20,36,51,0.05);
  --surface: #ffffff;
  --surface-2: #e3e9ea;
  --ink: #142433;
  --ink-muted: #4c6070;
  --ink-faint: #7c8e9a;
  --accent: #0f8aa3;
  --accent-strong: #0a5c6c;
  --accent-soft: rgba(15,138,163,0.13);
  --residual: #c1793a;
  --residual-strong: #8f5726;
  --residual-soft: rgba(193,121,58,0.16);
  --flag: #8a3fd1;
  --flag-strong: #6a24ac;
  --flag-soft: rgba(138,63,209,0.12);
  --line: rgba(20,36,51,0.13);
  --line-strong: rgba(20,36,51,0.24);
  --shadow: 0 1px 2px rgba(20,36,51,0.07), 0 10px 28px -16px rgba(20,36,51,0.28);
  color-scheme: light;
}}

* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
  background: var(--bg);
  color: var(--ink);
  font-family: 'IBM Plex Sans', system-ui, sans-serif;
  font-size: 15px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  overflow-x: hidden;
}}

.page {{
  max-width: 1180px;
  margin: 0 auto;
  padding: 40px 28px 64px;
  display: flex;
  flex-direction: column;
  gap: 28px;
}}

/* ---------- Masthead ---------- */
.masthead {{
  position: relative;
  border: 1px solid var(--line-strong);
  border-radius: 6px;
  background:
    linear-gradient(var(--bg-grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--bg-grid) 1px, transparent 1px),
    var(--surface);
  background-size: 28px 28px, 28px 28px, auto;
  padding: 32px 32px 28px;
  overflow: hidden;
}}
.masthead::before, .masthead::after,
.masthead .tick-br, .masthead .tick-bl {{
  content: "";
  position: absolute;
  width: 14px;
  height: 14px;
  border-color: var(--line-strong);
  border-style: solid;
}}
.masthead::before {{ top: 10px; left: 10px; border-width: 1.5px 0 0 1.5px; }}
.masthead::after {{ top: 10px; right: 10px; border-width: 1.5px 1.5px 0 0; }}
.tick-bl {{ bottom: 10px; left: 10px; border-width: 0 0 1.5px 1.5px; }}
.tick-br {{ bottom: 10px; right: 10px; border-width: 0 1.5px 1.5px 0; }}

.eyebrow {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11.5px;
  font-weight: 500;
  letter-spacing: 0.09em;
  color: var(--accent-strong);
  text-transform: uppercase;
  margin-bottom: 14px;
}}
.masthead-row {{
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 32px;
  flex-wrap: wrap;
}}
h1 {{
  font-family: 'IBM Plex Serif', Georgia, serif;
  font-weight: 600;
  font-size: 34px;
  letter-spacing: -0.01em;
  margin: 0 0 10px;
  text-wrap: balance;
}}
.dek {{
  margin: 0;
  max-width: 62ch;
  color: var(--ink-muted);
  font-size: 14.5px;
  line-height: 1.6;
}}
.hero-total {{
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
}}
.hero-total-label {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-faint);
}}
.hero-total-figure {{
  font-family: 'IBM Plex Serif', Georgia, serif;
  font-weight: 600;
  font-size: 44px;
  color: var(--accent-strong);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}}
.hero-total-sub {{
  font-size: 12px;
  color: var(--ink-faint);
  font-family: 'IBM Plex Mono', monospace;
}}

/* ---------- Tabs ---------- */
.tabnav {{
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--line-strong);
  padding: 0 2px;
}}
.tab-btn {{
  appearance: none;
  border: none;
  background: transparent;
  font-family: 'IBM Plex Sans', sans-serif;
  font-weight: 500;
  font-size: 13.5px;
  color: var(--ink-muted);
  padding: 12px 6px 11px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.tab-btn:hover {{ color: var(--ink); }}
.tab-btn[aria-selected="true"] {{
  color: var(--ink);
  border-bottom-color: var(--accent-strong);
}}
.tab-btn .tab-count {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10.5px;
  color: var(--flag-strong);
  background: var(--flag-soft);
  border-radius: 8px;
  padding: 1px 6px;
}}
.tab-btn:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.tabpanel {{ display: none; flex-direction: column; gap: 28px; }}
.tabpanel.is-active {{ display: flex; }}

/* ---------- KPI row ---------- */
.kpi-row {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}}
.kpi {{
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-shadow: var(--shadow);
}}
.kpi-label {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10.5px;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--ink-faint);
}}
.kpi-value {{
  font-family: 'IBM Plex Sans', sans-serif;
  font-weight: 600;
  font-size: 26px;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}}
.kpi-sub {{
  font-size: 12.5px;
  color: var(--ink-muted);
}}

/* ---------- Callout ---------- */
.callout {{
  display: flex;
  gap: 14px;
  border: 1px solid var(--flag);
  background: var(--flag-soft);
  border-radius: 6px;
  padding: 16px 20px;
}}
.callout-mark {{
  font-family: 'IBM Plex Serif', serif;
  font-weight: 600;
  font-size: 16px;
  color: var(--flag-strong);
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border: 1.5px solid var(--flag-strong);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}}
.callout-body p {{
  margin: 0 0 6px;
  font-size: 13px;
  line-height: 1.65;
  color: var(--ink);
}}
.callout-body p:last-child {{ margin-bottom: 0; }}
.callout-body strong {{ font-weight: 600; }}

/* ---------- Panels ---------- */
.panel {{
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 6px;
  box-shadow: var(--shadow);
  padding: 24px 26px 26px;
}}
.panel-head {{
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}}
.panel-head h2 {{
  font-family: 'IBM Plex Sans', sans-serif;
  font-weight: 600;
  font-size: 16px;
  margin: 0;
  letter-spacing: -0.005em;
}}
.legend {{
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--ink-muted);
  font-family: 'IBM Plex Mono', monospace;
  align-items: center;
}}
.swatch {{
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  margin-right: 6px;
  vertical-align: -1px;
}}
.swatch.accent {{ background: var(--accent); }}
.swatch.residual {{
  background: repeating-linear-gradient(135deg, var(--residual), var(--residual) 2px, var(--residual-soft) 2px, var(--residual-soft) 4px);
}}
.swatch.flag {{ background: var(--flag); border-radius: 50%; }}
.swatch.watch {{ border: 1.5px dashed var(--ink-faint); background: transparent; }}

/* ---------- Bars ---------- */
.bars {{ display: flex; flex-direction: column; gap: 3px; }}
.bar-row {{
  display: grid;
  grid-template-columns: 230px 1fr 128px;
  align-items: center;
  gap: 14px;
  padding: 7px 8px;
  border-radius: 4px;
  position: relative;
  cursor: default;
  border-left: 3px solid transparent;
}}
.bar-row:hover, .bar-row:focus-visible {{
  background: var(--accent-soft);
  outline: none;
}}
.bar-row.is-residual:hover, .bar-row.is-residual:focus-visible {{
  background: var(--residual-soft);
}}
.bar-row.tier-flag {{ border-left-color: var(--flag); }}
.bar-row.tier-flag:hover, .bar-row.tier-flag:focus-visible {{ background: var(--flag-soft); }}
.bar-row.tier-watch {{ border-left: 3px dashed var(--line-strong); }}
.bar-row-label {{
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}}
.bar-rank {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  color: var(--ink-faint);
  width: 16px;
  flex-shrink: 0;
}}
.bar-name {{
  font-size: 13px;
  font-weight: 500;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}
.bar-track {{
  height: 16px;
  background: var(--surface-2);
  border-radius: 3px;
  padding: 2px;
  overflow: hidden;
}}
.bar-fill {{
  height: 100%;
  border-radius: 2px;
  background: var(--accent);
  min-width: 3px;
}}
.bar-row.is-residual .bar-fill {{
  background: repeating-linear-gradient(135deg, var(--residual), var(--residual) 3px, var(--residual-soft) 3px, var(--residual-soft) 6px);
}}
.bar-figures {{
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  font-family: 'IBM Plex Mono', monospace;
  font-variant-numeric: tabular-nums;
  font-size: 12.5px;
  white-space: nowrap;
}}
.bar-amt {{ color: var(--ink); font-weight: 500; }}
.bar-pct {{ color: var(--ink-faint); width: 42px; text-align: right; }}

.tier-badge {{
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10.5px;
  padding: 2px 7px;
  border-radius: 9px;
  white-space: nowrap;
  flex-shrink: 0;
}}
.tier-badge.flag {{ background: var(--flag-soft); color: var(--flag-strong); border: 1px solid var(--flag); }}
.tier-badge.watch {{ background: transparent; color: var(--ink-faint); border: 1px dashed var(--line-strong); }}

.bar-tooltip {{
  position: absolute;
  left: 8px;
  right: 8px;
  top: 100%;
  margin-top: 2px;
  background: var(--ink);
  color: var(--bg);
  border-radius: 5px;
  padding: 9px 12px;
  font-size: 12px;
  line-height: 1.5;
  z-index: 5;
  opacity: 0;
  transform: translateY(-4px);
  pointer-events: none;
  transition: opacity 0.12s ease, transform 0.12s ease;
  box-shadow: 0 8px 20px -6px rgba(0,0,0,0.4);
}}
.bar-row:hover .bar-tooltip, .bar-row:focus-visible .bar-tooltip {{
  opacity: 1;
  transform: translateY(0);
}}
.bar-tooltip b {{ font-weight: 600; }}
.bar-tooltip .tt-examples {{ color: var(--bg); opacity: 0.78; }}

/* ---------- Table ---------- */
.table-scroll {{ overflow-x: auto; }}
table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}}
thead th {{
  text-align: left;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10.5px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--ink-faint);
  font-weight: 500;
  padding: 0 10px 10px;
  border-bottom: 1px solid var(--line-strong);
  white-space: nowrap;
}}
thead th.num {{ text-align: right; }}
tbody td {{
  padding: 10px 10px;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}}
tbody tr:last-child td {{ border-bottom: none; }}
tbody tr:hover {{ background: var(--accent-soft); }}
tbody tr.is-residual:hover {{ background: var(--residual-soft); }}
tbody tr.tier-flag:hover {{ background: var(--flag-soft); }}
td.rank {{ font-family: 'IBM Plex Mono', monospace; color: var(--ink-faint); width: 28px; }}
td.cat {{ font-weight: 500; white-space: nowrap; }}
td.num {{ text-align: right; font-family: 'IBM Plex Mono', monospace; font-variant-numeric: tabular-nums; white-space: nowrap; }}
td.ex {{ color: var(--ink-muted); font-size: 12.5px; }}
td.note {{ color: var(--ink-faint); font-size: 12px; max-width: 220px; }}
.dot {{
  display: inline-block;
  width: 7px; height: 7px;
  border-radius: 50%;
  margin-right: 7px;
  background: var(--accent);
  vertical-align: 1px;
}}
tr.is-residual .dot {{
  background: repeating-linear-gradient(135deg, var(--residual), var(--residual) 1.5px, var(--residual-soft) 1.5px, var(--residual-soft) 3px);
}}
tr.tier-flag .dot {{ background: var(--flag); }}

/* ---------- Methodology ---------- */
.methodology {{
  border: 1px dashed var(--line-strong);
  border-radius: 6px;
  padding: 20px 24px;
  background: transparent;
}}
.methodology h3 {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11.5px;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--ink-faint);
  margin: 0 0 12px;
  font-weight: 500;
}}
.methodology ul {{
  margin: 0;
  padding-left: 18px;
  color: var(--ink-muted);
  font-size: 12.8px;
  line-height: 1.7;
}}
.methodology li {{ margin-bottom: 4px; }}
.methodology li:last-child {{ margin-bottom: 0; }}
.methodology strong {{ color: var(--ink); font-weight: 500; }}

/* ---------- Monthly column chart ---------- */
.month-chart {{
  display: flex;
  align-items: stretch;
  gap: 8px;
  height: 240px;
  padding-top: 8px;
}}
.month-col {{
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 0;
  position: relative;
}}
.month-ncpct {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: var(--ink-faint);
  margin-bottom: 4px;
  white-space: nowrap;
}}
.month-col.is-ncpeak .month-ncpct {{ color: var(--flag-strong); font-weight: 500; }}
.month-bar-track {{
  flex: 1;
  width: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}}
.month-bar {{
  width: 62%;
  border-radius: 3px 3px 0 0;
  background: var(--accent);
  min-height: 3px;
  position: relative;
}}
.month-col.is-peak .month-bar {{ background: var(--accent-strong); }}
.month-peak-tag {{
  position: absolute;
  top: -18px;
  left: 50%;
  transform: translateX(-50%);
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--accent-strong);
  white-space: nowrap;
}}
.month-label {{
  margin-top: 8px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11px;
  color: var(--ink);
  font-weight: 500;
}}
.month-amt {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10px;
  color: var(--ink-faint);
  margin-top: 1px;
  font-variant-numeric: tabular-nums;
}}
.month-avg-line {{
  position: absolute;
  left: 0; right: 0;
  border-top: 1.5px dashed var(--line-strong);
  z-index: 1;
}}
.month-avg-label {{
  position: absolute;
  right: 0;
  top: -16px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  color: var(--ink-faint);
  background: var(--surface);
  padding: 0 4px;
}}

/* ---------- Cost-type mix ---------- */
.costtype-legend-row {{
  display: flex;
  gap: 22px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}}
.costtype-stat {{
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12.5px;
  color: var(--ink-muted);
}}
.costtype-stat b {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 15px;
  color: var(--ink);
  font-weight: 600;
}}
.pill {{
  display: inline-flex;
  align-items: center;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 10.5px;
  padding: 2px 7px;
  border-radius: 9px;
  background: var(--surface-2);
  color: var(--ink-muted);
  white-space: nowrap;
}}
.pill.flag {{
  background: var(--flag-soft);
  color: var(--flag-strong);
  border: 1px solid var(--flag);
}}

/* ---------- Drill-down ---------- */
.branch-row {{
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 4px 0 18px;
}}
.branch-pill {{
  display: inline-flex;
  align-items: baseline;
  gap: 5px;
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11.5px;
  padding: 4px 10px;
  border-radius: 9px;
  background: var(--surface-2);
  color: var(--ink-muted);
  border: 1px solid var(--line);
}}
.branch-pill b {{ color: var(--ink); font-weight: 600; }}
td.branch {{ font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: var(--ink-muted); white-space: nowrap; }}
tbody tr.near-threshold {{ background: var(--flag-soft); }}
tbody tr.near-threshold:hover {{ background: var(--flag-soft); filter: brightness(0.97); }}
.dd-scroll {{ max-height: 480px; overflow-y: auto; overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; }}
.dd-scroll table {{ font-size: 12.5px; }}
.dd-scroll thead th {{ position: sticky; top: 0; background: var(--surface); z-index: 2; }}

/* ---------- Contract Detail tab ---------- */
.cd-toolbar {{
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}}
.cd-search {{
  flex: 1;
  min-width: 220px;
  position: relative;
}}
.cd-search input {{
  width: 100%;
  font-family: 'IBM Plex Sans', sans-serif;
  font-size: 13px;
  padding: 9px 14px 9px 34px;
  border: 1px solid var(--line-strong);
  border-radius: 6px;
  background: var(--surface);
  color: var(--ink);
  box-sizing: border-box;
}}
.cd-search input:focus {{
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}}
.cd-search::before {{
  content: "";
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 13px;
  height: 13px;
  border: 1.5px solid var(--ink-faint);
  border-radius: 50%;
}}
.cd-search::after {{
  content: "";
  position: absolute;
  left: 22.5px;
  top: 58%;
  width: 6px;
  height: 1.5px;
  background: var(--ink-faint);
  transform: rotate(45deg);
  transform-origin: left;
}}
.cd-count {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11.5px;
  color: var(--ink-faint);
  white-space: nowrap;
}}
.cd-download {{
  font-family: 'IBM Plex Mono', monospace;
  font-size: 11.5px;
  padding: 8px 14px;
  border-radius: 6px;
  border: 1px solid var(--line-strong);
  background: var(--surface);
  color: var(--ink);
  cursor: pointer;
  white-space: nowrap;
}}
.cd-download:hover {{ background: var(--accent-soft); border-color: var(--accent); }}
.cd-scroll {{ max-height: 620px; overflow-y: auto; overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; }}
.cd-scroll table {{ font-size: 12px; }}
.cd-scroll thead th {{ position: sticky; top: 0; background: var(--surface); z-index: 2; }}
td.memo {{ color: var(--ink); font-size: 12px; max-width: 260px; }}
td.geo {{ color: var(--ink-muted); font-size: 11.5px; white-space: nowrap; }}
.cd-empty {{ padding: 40px 20px; text-align: center; color: var(--ink-faint); font-size: 13px; display: none; }}

/* ---------- Finding callouts (neutral / null-result) ---------- */
.finding {{
  border: 1px solid var(--line-strong);
  border-radius: 6px;
  padding: 16px 20px;
  background: var(--surface-2);
  font-size: 13px;
  line-height: 1.65;
  color: var(--ink-muted);
}}
.finding strong {{ color: var(--ink); font-weight: 600; }}
.finding.null-result {{ border-style: dashed; }}

@media (max-width: 720px) {{
  .kpi-row {{ grid-template-columns: repeat(2, 1fr); }}
  .bar-row {{ grid-template-columns: 1fr; row-gap: 6px; }}
  .bar-figures {{ justify-content: flex-start; }}
  .masthead-row {{ align-items: flex-start; }}
  .hero-total {{ align-items: flex-start; }}
  h1 {{ font-size: 27px; }}
  .hero-total-figure {{ font-size: 34px; }}
  .tabnav {{ overflow-x: auto; }}
  .month-chart {{ height: 200px; }}
  .month-label {{ font-size: 9px; }}
  .month-amt {{ display: none; }}
}}
</style>

<div class="page">
  <header class="masthead">
    <span class="tick-bl"></span><span class="tick-br"></span>
    <div class="eyebrow">USAspending.gov &middot; Public Award Data &middot; Independent Analysis</div>
    <div class="masthead-row">
      <div>
        <h1>Department of Defense &mdash; FY2020&ndash;FY2026 YTD Spend Analysis</h1>
        <p class="dek">Six and a half years of obligations (Oct 2019&ndash;Apr 2026): what DoD buys, grouped into 18 spend categories, who it buys from, and procurement-pattern tests spanning the pandemic era through today, with a screen for contracts classified under vague catch-all industry codes.</p>
      </div>
      <div class="hero-total">
        <span class="hero-total-label">Total Obligated</span>
        <span class="hero-total-figure">{fmt_b(TOTAL)}</span>
        <span class="hero-total-sub">{fmt_full(TOTAL)}</span>
      </div>
    </div>
  </header>

  <nav class="tabnav" role="tablist" aria-label="Dashboard views">
    <button class="tab-btn" role="tab" id="tab-btn-taxonomy" aria-controls="panel-taxonomy" aria-selected="true">Spend Taxonomy</button>
    <button class="tab-btn" role="tab" id="tab-btn-vendors" aria-controls="panel-vendors" aria-selected="false">Vendor Concentration <span class="tab-count">{FLAGGED_COUNT} flagged</span></button>
    <button class="tab-btn" role="tab" id="tab-btn-patterns" aria-controls="panel-patterns" aria-selected="false">Procurement Patterns</button>
    <button class="tab-btn" role="tab" id="tab-btn-detail" aria-controls="panel-detail" aria-selected="false">Contract Detail</button>
  </nav>

  <section class="tabpanel is-active" id="panel-taxonomy" role="tabpanel" aria-labelledby="tab-btn-taxonomy">
    <section class="kpi-row">
      <div class="kpi">
        <span class="kpi-label">Categories Mapped</span>
        <span class="kpi-value">18</span>
        <span class="kpi-sub">+ 1 residual bucket</span>
      </div>
      <div class="kpi">
        <span class="kpi-label">Top Category</span>
        <span class="kpi-value">{max((r for r in ROWS if r['kind']=='core'), key=lambda r: r['amt'])['pct']:.1f}%</span>
        <span class="kpi-sub">{max((r for r in ROWS if r['kind']=='core'), key=lambda r: r['amt'])['name']}</span>
      </div>
      <div class="kpi">
        <span class="kpi-label">NAICS Coverage</span>
        <span class="kpi-value">{NAICS_COVERAGE_PCT:.1f}%</span>
        <span class="kpi-sub">of total, from top-100 codes</span>
      </div>
      <div class="kpi">
        <span class="kpi-label">Contract Share</span>
        <span class="kpi-value">{CONTRACT_TOTAL_ALL/TOTAL*100:.1f}%</span>
        <span class="kpi-sub">of obligations via contracts</span>
      </div>
    </section>

    <section class="panel chart-panel">
      <div class="panel-head">
        <h2>Obligations by Category, Ranked</h2>
        <div class="legend"><span><span class="swatch accent"></span>NAICS-mapped</span><span><span class="swatch residual"></span>Residual / unclassified</span></div>
      </div>
      <div class="bars" id="bars"></div>
    </section>

    <section class="panel table-panel">
      <div class="panel-head">
        <h2>Full Breakdown</h2>
      </div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Category</th>
              <th class="num">Amount</th>
              <th class="num">Share</th>
              <th>Representative Industries</th>
            </tr>
          </thead>
          <tbody id="tbody"></tbody>
        </table>
      </div>
    </section>

    <footer class="methodology">
      <h3>Methodology &amp; Caveats</h3>
      <ul>
        <li>Source: USAspending.gov public award API, queried live &mdash; no bulk dataset was downloaded to produce this view.</li>
        <li>Scope: Department of Defense as awarding agency, all award types, action dates 2019-10-01 through 2026-04-30 (FY2020 through FY2026 year-to-date).</li>
        <li>The top 100 NAICS industry codes by dollar amount were retrieved ({NAICS_COVERAGE_PCT:.1f}% of total obligations) and grouped by hand into 18 mission-relevant categories; the remainder &mdash; the long tail of smaller NAICS codes plus grants, direct payments, and other non-contract assistance &mdash; is shown as <strong>Other</strong>.</li>
        <li>This is an independently constructed taxonomy for analysis purposes, not an official DoD budget or appropriations classification (which uses Procurement / RDT&amp;E / O&amp;M / Military Personnel lines instead).</li>
        <li>DoD contract awards carry a 90-day publication delay under federal disclosure rules, so FY2026 activity from mid-May 2026 onward is excluded rather than shown as an undercount &mdash; the FY2026 YTD figures here run through April 2026 only.</li>
      </ul>
    </footer>
  </section>

  <section class="tabpanel" id="panel-vendors" role="tabpanel" aria-labelledby="tab-btn-vendors">
    <div class="callout">
      <span class="callout-mark">i</span>
      <div class="callout-body">
        <p><strong>What this is:</strong> the top 30 DoD vendors by dollar value across FY2020&ndash;FY2026 YTD (Oct 2019&ndash;Apr 2026), cross-referenced against how much of each vendor's spend falls under Census Bureau <strong>catch-all NAICS codes</strong> &mdash; industry classifications literally titled "All Other&hellip;" that get used when a business's work doesn't fit a more specific category.</p>
        <p><strong>What this is not:</strong> proof of waste, fraud, or mismanagement. A high catch-all share means the public classification data says less about what was purchased &mdash; nothing more. It is a starting point for deeper contract-level review, not a finding.</p>
      </div>
    </div>

    <section class="kpi-row">
      <div class="kpi">
        <span class="kpi-label">Top 30 Vendors</span>
        <span class="kpi-value">{fmt_b(TOP30_SUM)}</span>
        <span class="kpi-sub">{TOP30_SUM/TOTAL*100:.1f}% of total obligations</span>
      </div>
      <div class="kpi">
        <span class="kpi-label">Largest Vendor</span>
        <span class="kpi-value">{TOP_VENDOR['pct_of_total']:.1f}%</span>
        <span class="kpi-sub">{TOP_VENDOR['name']}</span>
      </div>
      <div class="kpi">
        <span class="kpi-label">Elevated Share (&ge;15%)</span>
        <span class="kpi-value">{FLAGGED_COUNT}</span>
        <span class="kpi-sub">vendors worth a closer look</span>
      </div>
      <div class="kpi">
        <span class="kpi-label">Watch Tier (5&ndash;14%)</span>
        <span class="kpi-value">{WATCH_COUNT}</span>
        <span class="kpi-sub">vendors</span>
      </div>
    </section>

    <section class="panel chart-panel">
      <div class="panel-head">
        <h2>Top 30 Vendors by Obligated Value</h2>
        <div class="legend"><span><span class="swatch flag"></span>Elevated non-specific share</span><span><span class="swatch watch"></span>Watch tier</span></div>
      </div>
      <div class="bars" id="vbars"></div>
    </section>

    <section class="panel table-panel">
      <div class="panel-head">
        <h2>Full Vendor Breakdown</h2>
      </div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Vendor</th>
              <th class="num">Amount</th>
              <th class="num">Share</th>
              <th class="num">Non-Specific Share</th>
              <th>Primary Business</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody id="vtbody"></tbody>
        </table>
      </div>
    </section>

    <footer class="methodology">
      <h3>Methodology &amp; Caveats</h3>
      <ul>
        <li>Source: USAspending.gov public award API, queried live. Vendors are ranked by total DoD-awarded dollar value for FY2020&ndash;FY2026 YTD (2019-10-01 through 2026-04-30), consolidated across registered entity-name variants (e.g. "Lockheed Martin Corp" and "Lockheed Martin Corporation" are combined).</li>
        <li><strong>Non-Specific Share</strong> = the portion of a vendor's DoD dollars classified under NAICS codes whose title begins with "All Other" (e.g. "All Other Professional, Scientific, and Technical Services"). These are Census Bureau catch-all classifications, used when a business's activity doesn't fit a more specific code &mdash; by definition, they disclose less about the nature of the work than a specific code would.</li>
        <li>Computed from each vendor's top 50 NAICS codes by dollar amount; vendors flagged "additional codes not shown" have a longer tail beyond that cut &mdash; their true share may differ from what's shown here.</li>
        <li>Vendors with only 1&ndash;3 total NAICS codes (e.g. many health-plan administrators, sole-source pharma distributors) are highly specialized, single-purpose contractors &mdash; a 0% non-specific share for them reflects a narrow business line, not a clean bill of health, and isn't comparable to a diversified prime's share.</li>
        <li><strong>This ranking does not indicate wrongdoing.</strong> Legitimate reasons a vendor's spend concentrates in catch-all codes include broad professional-services contracts, evolving scopes of work, or contracting-officer classification habits. Treat elevated shares as a prompt to pull the underlying contract records, not as a conclusion.</li>
        <li>DoD contract awards carry a 90-day publication delay, so FY2026 activity is cut off at April 2026 rather than shown as an artificially low recent-month figure.</li>
      </ul>
    </footer>
  </section>

  <section class="tabpanel" id="panel-patterns" role="tabpanel" aria-labelledby="tab-btn-patterns">
    <div class="callout">
      <span class="callout-mark">i</span>
      <div class="callout-body">
        <p><strong>Four procurement-pattern tests below.</strong> Three produced clean, usable findings. The fourth (threshold clustering) is shown anyway, with its result: it did not hold up as a reliable signal once checked properly, and we explain why rather than dressing it up.</p>
      </div>
    </div>

    <section class="panel">
      <div class="panel-head">
        <h2>Single-Bid "Competed" Contracts</h2>
        <div class="legend"><span>Nominally competitive, functionally uncontested</span></div>
      </div>
      <p class="dek" style="margin-bottom:16px;">A contract coded "full and open competition" can still draw only one bidder — often a sign of high barriers to entry, incumbent lock-in, or requirements written narrowly enough that only one company can realistically meet them. Scoped to definitive contracts specifically (where competition decisions are actually made, as opposed to orders placed under an already-competed vehicle). This required USAspending's bulk award-download data &mdash; the field isn't exposed through the standard search API.</p>
      <div class="kpi-row">
        <div class="kpi">
          <span class="kpi-label">Single-Bid Competed Contracts</span>
          <span class="kpi-value">{SB_COUNT:,}</span>
          <span class="kpi-sub">of {SB_COMPETED_COUNT:,} genuinely-competed contracts</span>
        </div>
        <div class="kpi">
          <span class="kpi-label">Share of Competed Contracts</span>
          <span class="kpi-value">{SB_COUNT/SB_COMPETED_COUNT*100:.1f}%</span>
          <span class="kpi-sub">by count</span>
        </div>
        <div class="kpi">
          <span class="kpi-label">Total Value</span>
          <span class="kpi-value">{fmt_b(SB_VALUE)}</span>
          <span class="kpi-sub">{SB_VALUE/SB_COMPETED_VALUE*100:.1f}% of competed-contract dollars</span>
        </div>
        <div class="kpi">
          <span class="kpi-label">Top Vendor</span>
          <span class="kpi-value">{fmt_b(SB_TOP_VENDOR['value'])}</span>
          <span class="kpi-sub">{SB_TOP_VENDOR['name']}, {SB_TOP_VENDOR['count']} contracts</span>
        </div>
      </div>
      <div class="bars" id="sbbars" style="margin-top:16px;"></div>
      <div class="finding" style="margin-top:16px;">
        <strong>About a quarter of nominally-competed definitive contracts drew exactly one bidder, consistently across seven fiscal years.</strong> This spans the largest primes &mdash; {SB_TOP_VENDOR['name']} alone accounts for {fmt_b(SB_TOP_VENDOR['value'])} across {SB_TOP_VENDOR['count']} single-bid competed contracts, and Lockheed Martin, Sikorsky, and National Steel and Shipbuilding each show up with single awards north of $1.8B &mdash; which fits a well-documented pattern in defense procurement: highly specialized, capital-intensive work (shipyards, classified systems, sustainment of legacy platforms) often has exactly one company capable of bidding, even when the solicitation is technically open to all. That's frequently a structural reality of the defense industrial base, not a procurement failure. It's still worth surfacing, because it's the same underlying condition GAO reports point to when they recommend agencies work to expand the industrial base or reconsider whether a requirement needs to be split into more competable pieces.
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>Drill-Down: Single-Bid Contracts Under the $350K Threshold</h2>
        <div class="legend"><span><span class="swatch flag"></span>Near-threshold ($300K&ndash;$349,999)</span></div>
      </div>
      <p class="dek" style="margin-bottom:12px;">Narrowing the single-bid pattern to contracts under the Simplified Acquisition Threshold &mdash; where competition requirements are lighter to begin with, so a single bidder is less inherently surprising, but still worth a look, especially where the award size sits conspicuously close to the $350K line.</p>
      <div class="costtype-legend-row">
        <div class="costtype-stat"><b>{DD_TOTAL_COUNT:,}</b>&nbsp;single-bid competed contracts under $350K ({fmt_b(DD_TOTAL_VALUE)})</div>
        <div class="costtype-stat"><b>{DD_NEAR_COUNT}</b>&nbsp;of those in the $300K&ndash;$349,999 near-threshold band ({fmt_b(DD_NEAR_VALUE)})</div>
      </div>
      <div class="branch-row" id="branchRow"></div>

      <div class="finding" style="margin-bottom:18px;">
        <strong>Leland Limited Inc &mdash; Defense Logistics Agency (Navy/Marine supply) &mdash; 17 single-bid awards spanning FY2021 through FY2025, same product every time.</strong> Every one of Leland's contracts with DLA across five fiscal years was for <em>Marine Lifesaving and Diving Equipment</em>, nominally competed under Simplified Acquisition Procedures, and drew exactly one bidder &mdash; Leland. Five-plus years of a perfect one-bidder streak on the identical product category is consistent with a genuinely thin supplier market for specialized diving/marine-safety gear (in which case one bidder every time is simply reality, not a process failure) &mdash; but it's also exactly the pattern worth a contracting officer double-checking: are other qualified suppliers being notified of these solicitations, or has the sourcing list been effectively down to one company for half a decade?
        <div class="table-scroll" style="margin-top:12px;">
          <table>
            <thead><tr><th>Date</th><th>Award ID</th><th class="num">Amount</th><th>Extent Competed</th></tr></thead>
            <tbody id="lelandBody"></tbody>
          </table>
        </div>
      </div>

      <div class="panel-head" style="margin-bottom:10px;">
        <h2 style="font-size:14px;">Full List &mdash; {DD_TOTAL_COUNT:,} Single-Bid Contracts Under $350K</h2>
      </div>
      <div class="dd-scroll">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Vendor</th>
              <th class="num">Amount</th>
              <th>Branch</th>
              <th>Extent Competed</th>
              <th>Date</th>
              <th>Award ID</th>
            </tr>
          </thead>
          <tbody id="ddBody"></tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>Obligations by Fiscal Year</h2>
      </div>
      <p class="dek" style="margin-bottom:16px;">Total DoD contract obligations, FY2020 through FY2026 year-to-date (partial year, through April 2026).</p>
      <div class="month-chart" id="yearChart"></div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>Obligation Timing — Seasonal Pattern (FY2020&ndash;FY2025 Average)</h2>
      </div>
      <p class="dek" style="margin-bottom:16px;">Common government-spending folklore says agencies rush to obligate before the fiscal year ends in September ("use it or lose it"). Averaged across six complete fiscal years, that's not what DoD's data shows.</p>
      <div class="kpi-row">
        <div class="kpi">
          <span class="kpi-label">Peak Month (Avg)</span>
          <span class="kpi-value">{PEAK_MONTH['month']}</span>
          <span class="kpi-sub">{fmt_b(PEAK_MONTH['total'])}, {PEAK_MONTH['vs_avg_pct']:+.0f}% vs. average</span>
        </div>
        <div class="kpi">
          <span class="kpi-label">September (FY-End)</span>
          <span class="kpi-value">{SEP_ROW['vs_avg_pct']:+.0f}%</span>
          <span class="kpi-sub">vs. average — essentially flat</span>
        </div>
        <div class="kpi">
          <span class="kpi-label">Monthly Average</span>
          <span class="kpi-value">{fmt_b(MONTHLY_AVG)}</span>
          <span class="kpi-sub">across 6 complete fiscal years (FY20&ndash;FY25)</span>
        </div>
        <div class="kpi">
          <span class="kpi-label">Highest Non-Competitive Month</span>
          <span class="kpi-value">{PEAK_NC_MONTH['noncompete_pct']:.0f}%</span>
          <span class="kpi-sub">{PEAK_NC_MONTH['month']} (avg, FY20&ndash;FY25)</span>
        </div>
      </div>
      <div style="margin-top:20px;">
        <div class="month-chart" id="monthChart"></div>
      </div>
      <div class="finding" style="margin-top:16px;">
        <strong>December obligates {PEAK_MONTH['total']/MONTHLY_AVG:.1f}&times; the monthly average &mdash; every single year, not a one-year fluke.</strong> Averaged across all six complete fiscal years (FY2020&ndash;FY2025), December is the largest month by a wide margin, while September &mdash; the actual fiscal year-end &mdash; comes in at {SEP_ROW['vs_avg_pct']:+.0f}%, essentially a normal month. The most common driver of a pattern like this is appropriations timing: DoD frequently operates under a Continuing Resolution at the start of the fiscal year, which restricts new-start spending until a full-year appropriations bill (often passed in December) unlocks it &mdash; producing a backlog release rather than a deliberate year-end rush. March carries the highest average non-competitive share ({PEAK_NC_MONTH['noncompete_pct']:.1f}% of dollars, vs. roughly 40&ndash;48% in most other months), consistent with obligations moving faster — with less time for competitive procedures — in the run-up to the government's own fiscal year-end deadlines for the following cycle. This is a plausible explanation, not a proven cause; we have not traced individual awards back to specific appropriations actions.</div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>Cost-Reimbursement Exposure by Vendor</h2>
        <div class="legend"><span>Cost-type shifts overrun risk to the government</span></div>
      </div>
      <p class="dek" style="margin-bottom:12px;">Fixed-price contracts put cost-overrun risk on the vendor; cost-reimbursement contracts put it on the government. Neither is wrong — cost-type is standard (and often required) for FFRDCs, novel R&amp;D, and unique sustainment work — but a vendor's mix is a useful risk profile, not a verdict.</p>
      <div class="costtype-legend-row">
        <div class="costtype-stat"><b>{fmt_b(COST_TYPE_TOTAL)}</b>&nbsp;cost-reimbursement ({COST_TYPE_TOTAL/CONTRACT_TOTAL_ALL*100:.1f}% of contract $)</div>
        <div class="costtype-stat"><b>{fmt_b(FIXED_PRICE_TOTAL)}</b>&nbsp;fixed-price ({FIXED_PRICE_TOTAL/CONTRACT_TOTAL_ALL*100:.1f}%)</div>
        <div class="costtype-stat"><b>{FULL_COST_TYPE_VENDORS}</b>&nbsp;of the top 30 vendors are effectively 100% cost-type</div>
      </div>
      <div class="bars" id="ctbars"></div>
      <div class="finding" style="margin-top:16px;">
        The vendors at ~100% cost-type are not a red flag — they're exactly who you'd expect: <strong>Health Net Federal Services</strong> and <strong>Humana Government Business</strong> administer TRICARE health plans (cost-reimbursement by design), and <strong>Bechtel Plant Machinery</strong> and <strong>Fluor Marine Propulsion</strong> sustain naval nuclear reactors (unique, sole-source expertise). Large primes cluster in the 30&ndash;90% range across this longer window, reflecting their mix of production (fixed-price) and R&amp;D/sustainment (cost-type) work over multiple contract cycles. Nothing here indicates impropriety on its own &mdash; it's a map of where cost-growth risk sits, useful alongside other signals, not instead of them.
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h2>Threshold Clustering — Tested, No Reliable Signal Found</h2>
      </div>
      <p class="dek" style="margin-bottom:12px;">We looked for the classic "structuring" pattern: the same vendor receiving multiple awards from the same office on the same day, each individually under the $350K SAT, that together exceed it — a way to dodge the competition requirement on what should've been one larger, competed buy.</p>
      <div class="finding null-result">
        <strong>Same conclusion as the single-year test, reinforced by six times the data.</strong> We found {BUNCH_TOTAL_CLUSTERS} same-vendor/same-day/same-agency clusters across 8 candidate vendors, totaling {fmt_b(BUNCH_TOTAL_STANDALONE_DOLLARS)}, even after excluding clusters that shared one existing parent supply vehicle (i.e. routine multiple calls under an already-competed contract, which is normal). But the vendors driving nearly all of it &mdash; <strong>{BUNCH_TOP2[0]['vendor']}</strong> ({BUNCH_TOP2[0]['clusters_standalone_or_mixed_parents']} clusters, {fmt_b(BUNCH_TOP2[0]['dollars_in_standalone_clusters'])}) and <strong>{BUNCH_TOP2[1]['vendor']}</strong> ({BUNCH_TOP2[1]['clusters_standalone_or_mixed_parents']} clusters, {fmt_b(BUNCH_TOP2[1]['dollars_in_standalone_clusters'])}) &mdash; are large, established DLA distributors (pharmaceuticals and medical/tactical supply) who hold <em>multiple concurrent</em> supply IDVs as their normal operating model, and whose day-level record counts hit our 500-record-per-vendor pull cap, so the true totals for these two are understated, not overstated. Getting several separate calls from DLA on the same day, each against a different existing vehicle, is exactly what a high-volume distributor's business looks like &mdash; not evidence of splitting one requirement into two to dodge competition.<br><br>
        A genuinely reliable test would need to compare the <em>item-level descriptions</em> of same-day awards to check whether they're really the same requirement split in two &mdash; that data isn't available through USAspending's bulk API. We're reporting this as a tested-and-inconclusive result rather than either hiding it or overstating it.
      </div>
    </section>

    <footer class="methodology">
      <h3>Methodology &amp; Caveats</h3>
      <ul>
        <li>Source: USAspending.gov public award API and bulk award-download endpoint, queried live. Scope: Department of Defense, FY2020 through FY2026 year-to-date (2019-10-01 through 2026-04-30), contract award types only.</li>
        <li><strong>Obligation timing</strong> uses actual (calendar) obligation month via each award's action date; the seasonal-average chart uses only the six complete fiscal years (FY2020&ndash;FY2025) &mdash; FY2026 YTD is partial and shown separately in the yearly-totals chart, not blended into the monthly average. "Non-competitive" uses the same B/C/G extent-competed definition as the Vendor Concentration tab.</li>
        <li><strong>Cost-type mix</strong> uses FPDS contract pricing type codes: cost-reimbursement = Cost Plus Award Fee, Cost No Fee, Cost Sharing, Cost Plus Fixed Fee, Cost Plus Incentive Fee; fixed-price = Firm Fixed Price and its variants. Time-and-materials contracts (under 1% of dollars) are excluded from both buckets. "L3Harris Technologies, Inc." is excluded from this view specifically because text-based vendor matching over-counts it (it also catches "L3Harris Technologies Integrated Systems L.P.", a separate entity), producing a share above 100% &mdash; a data artifact, not a real number.</li>
        <li><strong>Threshold clustering</strong> was tested on the 8 vendors with the highest dollar concentration in the $300,000&ndash;$349,999 band across the full date range; "same parent vehicle" is inferred from each award's underlying IDV/BPA reference number. Records were capped at 500 per vendor (sorted earliest-first), so the highest-volume vendors' true totals are understated.</li>
        <li><strong>Single-bid competed contracts</strong> covers all {SB_TOTAL_DEFINITIVE:,} DoD definitive contracts (award type "D") for FY2020&ndash;FY2026 YTD, pulled via USAspending's bulk award-download endpoint (the only place "Number of Offers Received" is exposed &mdash; it's absent from the standard search API). "Genuinely competed" = Full and Open Competition, Full and Open Competition after Exclusion of Sources, or Competed under Simplified Acquisition Procedures; sole-source categories are excluded since a single offer is expected by design for those. <strong>Branch</strong> in the drill-down table is the awarding sub-agency reported on the award (Army, Navy, Air Force, Defense Logistics Agency, and other DoD components) &mdash; not necessarily where the equipment or service is ultimately used.</li>
        <li>A fifth analysis &mdash; small-business subcontracting pass-through &mdash; was investigated but not included on this tab: USAspending's subaward data can be reliably scoped to a specific prime contract (via its Award ID), but most prime awards have zero reported subawards at all (a known FSRS reporting-compliance gap), and there's no business-size field on subaward records, so classifying a subcontractor as "large" or "small" requires a separate lookup per subcontractor. Early spot-checks did not support a "small businesses fronting for large corporations" pattern &mdash; one high-pass-through case we found (97.5% of a $76M contract subcontracted) went to another small business, not a large one &mdash; but the coverage gaps mean this isn't reliable enough to present as a finding yet.</li>
      </ul>
    </footer>
  </section>

  <section class="tabpanel" id="panel-detail" role="tabpanel" aria-labelledby="tab-btn-detail">
    <div class="callout">
      <span class="callout-mark">i</span>
      <div class="callout-body">
        <p>Full record-level detail behind the single-bid drill-down on the Procurement Patterns tab &mdash; every DoD definitive contract from FY2020 through FY2026 YTD that was nominally competed, drew exactly one bidder, and came in under the $350K Simplified Acquisition Threshold. Search across vendor, description, place, or branch; export the full dataset (29 fields, including vendor UEI, solicitation IDs, and funding agency) as CSV.</p>
      </div>
    </div>

    <section class="kpi-row">
      <div class="kpi">
        <span class="kpi-label">Contracts</span>
        <span class="kpi-value">{len(CD_RECORDS):,}</span>
        <span class="kpi-sub">{fmt_b(CD_TOTAL_VALUE)} total</span>
      </div>
      <div class="kpi">
        <span class="kpi-label">Near-Threshold</span>
        <span class="kpi-value">{CD_NEAR_COUNT}</span>
        <span class="kpi-sub">{fmt_b(CD_NEAR_VALUE)}, $300K&ndash;$349,999</span>
      </div>
      <div class="kpi">
        <span class="kpi-label">Fields Per Record</span>
        <span class="kpi-value">29</span>
        <span class="kpi-sub">vendor, geography, dates, pricing, memo</span>
      </div>
      <div class="kpi">
        <span class="kpi-label">Source</span>
        <span class="kpi-value">Bulk API</span>
        <span class="kpi-sub">USAspending.gov award-download export</span>
      </div>
    </section>

    <section class="panel">
      <div class="cd-toolbar">
        <div class="cd-search">
          <input type="text" id="cdSearchInput" placeholder="Search vendor, description, place of performance, branch, award ID&hellip;" aria-label="Search contracts">
        </div>
        <span class="cd-count" id="cdCount"></span>
        <button class="cd-download" id="cdDownloadBtn">&#8595; Download CSV (all 29 fields)</button>
      </div>
      <div class="cd-scroll">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Vendor</th>
              <th class="num">Amount</th>
              <th>Branch</th>
              <th>Award Date</th>
              <th>Period of Performance</th>
              <th>Description / Memo</th>
              <th>Product/Service Code</th>
              <th>Place of Performance</th>
              <th>Vendor Location</th>
              <th>Pricing Type</th>
              <th>Award ID</th>
            </tr>
          </thead>
          <tbody id="cdBody"></tbody>
        </table>
        <div class="cd-empty" id="cdEmpty">No contracts match that search.</div>
      </div>
    </section>

    <footer class="methodology">
      <h3>Methodology &amp; Caveats</h3>
      <ul>
        <li>Same underlying dataset and definitions as the drill-down on the Procurement Patterns tab. "Description / Memo" is USAspending's own transaction description field, as submitted by the contracting office &mdash; wording and completeness vary by office.</li>
        <li>"Place of Performance" is where the work/delivery occurs; "Vendor Location" is the contractor's registered address. These often differ and both are shown to make geographic patterns visible.</li>
        <li>The CSV export includes all 29 fields captured for this analysis, including parent award ID, vendor UEI, funding agency/sub-agency, solicitation ID, and solicitation procedures &mdash; more than is practical to show in the on-page table.</li>
      </ul>
    </footer>
  </section>
</div>

<script>
const DATA = {rows_json};
const TOTAL = {TOTAL};
const MAX = Math.max(...DATA.map(d => d.amt));

const VDATA = {vendor_json};
const VMAX = Math.max(...VDATA.map(d => d.total));

function fmtB(n) {{
  if (Math.abs(n) < 1e9) {{
    return '$' + (n/1e6).toLocaleString('en-US', {{minimumFractionDigits:1, maximumFractionDigits:1}}) + 'M';
  }}
  return '$' + (n/1e9).toLocaleString('en-US', {{minimumFractionDigits:1, maximumFractionDigits:1}}) + 'B';
}}
function fmtFull(n) {{
  return '$' + Math.round(n).toLocaleString('en-US');
}}

const barsEl = document.getElementById('bars');
const tbodyEl = document.getElementById('tbody');

DATA.forEach((d, i) => {{
  const isResidual = d.kind === 'residual';
  const row = document.createElement('div');
  row.className = 'bar-row' + (isResidual ? ' is-residual' : '');
  row.tabIndex = 0;
  const widthPct = (d.amt / MAX * 100).toFixed(2);
  row.innerHTML = `
    <div class="bar-row-label">
      <span class="bar-rank">${{String(i+1).padStart(2,'0')}}</span>
      <span class="bar-name">${{d.name}}</span>
    </div>
    <div class="bar-track"><div class="bar-fill" style="width:${{widthPct}}%"></div></div>
    <div class="bar-figures"><span class="bar-amt">${{fmtB(d.amt)}}</span><span class="bar-pct">${{d.pct.toFixed(1)}}%</span></div>
    <div class="bar-tooltip"><b>${{fmtFull(d.amt)}}</b> &middot; ${{d.pct.toFixed(1)}}% of total<br><span class="tt-examples">${{d.examples.join(' &middot; ')}}</span></div>
  `;
  barsEl.appendChild(row);

  const tr = document.createElement('tr');
  if (isResidual) tr.className = 'is-residual';
  tr.innerHTML = `
    <td class="rank">${{i+1}}</td>
    <td class="cat"><span class="dot"></span>${{d.name}}</td>
    <td class="num">${{fmtFull(d.amt)}}</td>
    <td class="num">${{d.pct.toFixed(1)}}%</td>
    <td class="ex">${{d.examples.join(', ')}}</td>
  `;
  tbodyEl.appendChild(tr);
}});

const vbarsEl = document.getElementById('vbars');
const vtbodyEl = document.getElementById('vtbody');

function tierBadge(d) {{
  if (d.tier === 'flag') return `<span class="tier-badge flag">&#9679; ${{d.catchall_share.toFixed(0)}}% non-specific</span>`;
  if (d.tier === 'watch') return `<span class="tier-badge watch">${{d.catchall_share.toFixed(0)}}% non-specific</span>`;
  return '';
}}

VDATA.forEach((d, i) => {{
  const row = document.createElement('div');
  row.className = 'bar-row tier-' + d.tier;
  row.tabIndex = 0;
  const widthPct = (d.total / VMAX * 100).toFixed(2);
  const note = d.naics_code_count <= 3
    ? 'Narrow, single-purpose business (' + d.naics_code_count + ' NAICS code' + (d.naics_code_count===1?'':'s') + ')'
    : (d.naics_incomplete ? 'Additional smaller codes not shown' : '');
  row.innerHTML = `
    <div class="bar-row-label">
      <span class="bar-rank">${{String(i+1).padStart(2,'0')}}</span>
      <span class="bar-name">${{d.name}}</span>
    </div>
    <div class="bar-track"><div class="bar-fill" style="width:${{widthPct}}%"></div></div>
    <div class="bar-figures">${{tierBadge(d)}}<span class="bar-amt">${{fmtB(d.total)}}</span><span class="bar-pct">${{d.pct_of_total.toFixed(1)}}%</span></div>
    <div class="bar-tooltip"><b>${{fmtFull(d.total)}}</b> &middot; ${{d.pct_of_total.toFixed(1)}}% of total DoD obligations<br>Primary business: ${{d.top_naics || 'n/a'}}<br>Non-specific share: ${{d.catchall_share.toFixed(1)}}% ${{d.top_catchall ? '(mostly \u201c' + d.top_catchall + '\u201d)' : ''}}<span class="tt-examples">${{note ? '<br>' + note : ''}}</span></div>
  `;
  vbarsEl.appendChild(row);

  const tr = document.createElement('tr');
  tr.className = 'tier-' + d.tier;
  tr.innerHTML = `
    <td class="rank">${{i+1}}</td>
    <td class="cat"><span class="dot"></span>${{d.name}}</td>
    <td class="num">${{fmtFull(d.total)}}</td>
    <td class="num">${{d.pct_of_total.toFixed(1)}}%</td>
    <td class="num">${{tierBadge(d) || d.catchall_share.toFixed(1) + '%'}}</td>
    <td class="ex">${{d.top_naics || '&mdash;'}}</td>
    <td class="note">${{note || '&mdash;'}}</td>
  `;
  vtbodyEl.appendChild(tr);
}});

/* ---------- Yearly chart ---------- */
const YEARS = {year_json};
const yearMax = Math.max(...YEARS.map(y => y.total));
const yearPeakIdx = YEARS.reduce((best, y, i) => y.total > YEARS[best].total ? i : best, 0);
const yearChartEl = document.getElementById('yearChart');
YEARS.forEach((y, i) => {{
  const col = document.createElement('div');
  col.className = 'month-col' + (i === yearPeakIdx ? ' is-peak' : '') + (y.year.includes('YTD') ? ' is-ncpeak' : '');
  const heightPct = (y.total / yearMax * 100).toFixed(2);
  col.innerHTML = `
    <span class="month-ncpct">${{y.year.includes('YTD') ? '7 mo.' : 'full yr'}}</span>
    <div class="month-bar-track">
      ${{i === yearPeakIdx ? '<span class="month-peak-tag">Peak</span>' : ''}}
      <div class="month-bar" style="height:${{heightPct}}%"></div>
    </div>
    <span class="month-label">${{y.year}}</span>
    <span class="month-amt">${{fmtB(y.total)}}</span>
  `;
  yearChartEl.appendChild(col);
}});

/* ---------- Monthly chart ---------- */
const MONTHLY = {monthly_json};
const monthMax = Math.max(...MONTHLY.map(m => m.total));
const monthAvg = {MONTHLY_AVG};
const peakMonthIdx = MONTHLY.reduce((best, m, i) => m.total > MONTHLY[best].total ? i : best, 0);
const peakNcIdx = MONTHLY.reduce((best, m, i) => m.noncompete_pct > MONTHLY[best].noncompete_pct ? i : best, 0);

const monthChartEl = document.getElementById('monthChart');
const avgPct = (monthAvg / monthMax * 100).toFixed(2);
MONTHLY.forEach((m, i) => {{
  const col = document.createElement('div');
  col.className = 'month-col' + (i === peakMonthIdx ? ' is-peak' : '') + (i === peakNcIdx ? ' is-ncpeak' : '');
  const heightPct = (m.total / monthMax * 100).toFixed(2);
  col.innerHTML = `
    <span class="month-ncpct">${{m.noncompete_pct.toFixed(0)}}% NC</span>
    <div class="month-bar-track">
      ${{i === peakMonthIdx ? '<span class="month-peak-tag">Peak</span>' : ''}}
      <div class="month-bar" style="height:${{heightPct}}%"></div>
    </div>
    <span class="month-label">${{m.month}}</span>
    <span class="month-amt">${{fmtB(m.total)}}</span>
  `;
  monthChartEl.appendChild(col);
}});
const avgLine = document.createElement('div');
avgLine.className = 'month-avg-line';
avgLine.style.bottom = `calc(${{avgPct}}% + 34px)`;
avgLine.innerHTML = '<span class="month-avg-label">avg</span>';
monthChartEl.style.position = 'relative';
monthChartEl.appendChild(avgLine);

/* ---------- Cost-type mix bars ---------- */
const CTDATA = {costtype_json};
const ctMax = Math.max(...CTDATA.map(d => d.cost_type_amt));
const ctbarsEl = document.getElementById('ctbars');
CTDATA.forEach((d, i) => {{
  const row = document.createElement('div');
  row.className = 'bar-row';
  row.tabIndex = 0;
  const widthPct = ctMax > 0 ? (d.cost_type_amt / ctMax * 100).toFixed(2) : 0;
  row.innerHTML = `
    <div class="bar-row-label">
      <span class="bar-rank">${{String(i+1).padStart(2,'0')}}</span>
      <span class="bar-name">${{d.name}}</span>
    </div>
    <div class="bar-track"><div class="bar-fill" style="width:${{widthPct}}%"></div></div>
    <div class="bar-figures"><span class="pill">${{d.cost_type_share.toFixed(0)}}% of their business</span><span class="bar-amt">${{fmtB(d.cost_type_amt)}}</span></div>
    <div class="bar-tooltip"><b>${{fmtFull(d.cost_type_amt)}}</b> cost-reimbursement &middot; ${{d.cost_type_share.toFixed(1)}}% of this vendor's total DoD business (${{fmtFull(d.total)}})</div>
  `;
  ctbarsEl.appendChild(row);
}});

/* ---------- Single-bid vendor bars ---------- */
const SBDATA = {singlebid_json};
const sbMax = Math.max(...SBDATA.map(d => d.value));
const sbbarsEl = document.getElementById('sbbars');
SBDATA.forEach((d, i) => {{
  const row = document.createElement('div');
  row.className = 'bar-row';
  row.tabIndex = 0;
  const widthPct = sbMax > 0 ? (d.value / sbMax * 100).toFixed(2) : 0;
  row.innerHTML = `
    <div class="bar-row-label">
      <span class="bar-rank">${{String(i+1).padStart(2,'0')}}</span>
      <span class="bar-name">${{d.name}}</span>
    </div>
    <div class="bar-track"><div class="bar-fill" style="width:${{widthPct}}%"></div></div>
    <div class="bar-figures"><span class="pill">${{d.count}} contract${{d.count===1?'':'s'}}</span><span class="bar-amt">${{fmtB(d.value)}}</span></div>
    <div class="bar-tooltip"><b>${{fmtFull(d.value)}}</b> across ${{d.count}} single-bid "competed" contract${{d.count===1?'':'s'}}</div>
  `;
  sbbarsEl.appendChild(row);
}});

/* ---------- Drill-down: branch pills ---------- */
const BRANCH_NEAR = {branch_near_json};
const branchRowEl = document.getElementById('branchRow');
BRANCH_NEAR.forEach(([branch, count]) => {{
  const pill = document.createElement('span');
  pill.className = 'branch-pill';
  pill.innerHTML = `<b>${{count}}</b> ${{branch}}`;
  branchRowEl.appendChild(pill);
}});

/* ---------- Drill-down: Leland case table ---------- */
const LELAND = {json.dumps(DD_LELAND)};
const lelandBodyEl = document.getElementById('lelandBody');
LELAND.forEach(r => {{
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td>${{r.date}}</td>
    <td class="ex">${{r.award_id}}</td>
    <td class="num">${{fmtFull(r.amount)}}</td>
    <td class="ex">${{r.extent_competed}}</td>
  `;
  lelandBodyEl.appendChild(tr);
}});

/* ---------- Drill-down: full table ---------- */
const DDROWS = {drilldown_json};
const ddBodyEl = document.getElementById('ddBody');
DDROWS.forEach((r, i) => {{
  const tr = document.createElement('tr');
  if (r.near_threshold) tr.className = 'near-threshold';
  tr.innerHTML = `
    <td class="rank">${{i+1}}</td>
    <td class="cat">${{r.vendor}}</td>
    <td class="num">${{fmtFull(r.amount)}}</td>
    <td class="branch">${{r.branch}}</td>
    <td class="ex">${{r.extent_competed}}</td>
    <td class="ex">${{r.date || '&mdash;'}}</td>
    <td class="ex">${{r.award_id}}</td>
  `;
  ddBodyEl.appendChild(tr);
}});

/* ---------- Contract Detail tab ---------- */
const CD_RECORDS = {cd_records_json};
const CD_COLUMNS = [
  ["award_id", "Award ID"], ["parent_award_id", "Parent Award ID"], ["vendor", "Vendor"],
  ["vendor_uei", "Vendor UEI"], ["amount", "Amount"], ["near_threshold", "Near Threshold"],
  ["branch_short", "Branch"], ["awarding_sub_agency", "Awarding Sub-Agency"], ["awarding_office", "Awarding Office"],
  ["funding_agency", "Funding Agency"], ["funding_sub_agency", "Funding Sub-Agency"], ["extent_competed", "Extent Competed"],
  ["solicitation_procedures", "Solicitation Procedures"], ["solicitation_id", "Solicitation ID"],
  ["type_of_contract_pricing", "Contract Pricing Type"], ["number_of_offers", "Offers Received"],
  ["award_date", "Award Date"], ["pop_start_date", "Period of Perf. Start"], ["pop_end_date", "Period of Perf. End"],
  ["description", "Description / Memo"], ["psc_description", "Product/Service Code"], ["naics_description", "NAICS Description"],
  ["pop_city", "POP City"], ["pop_state", "POP State"], ["pop_country", "POP Country"],
  ["vendor_city", "Vendor City"], ["vendor_state", "Vendor State"], ["vendor_country", "Vendor Country"],
  ["place_of_manufacture", "Place of Manufacture"],
];

const cdBodyEl = document.getElementById('cdBody');
const cdCountEl = document.getElementById('cdCount');
const cdEmptyEl = document.getElementById('cdEmpty');
const cdSearchInput = document.getElementById('cdSearchInput');
let cdFiltered = CD_RECORDS.slice();

function cdPop(r) {{
  const parts = [r.pop_city, r.pop_state].filter(Boolean);
  return parts.length ? parts.join(', ') : (r.pop_country || '&mdash;');
}}
function cdVendorLoc(r) {{
  const parts = [r.vendor_city, r.vendor_state].filter(Boolean);
  return parts.length ? parts.join(', ') : (r.vendor_country || '&mdash;');
}}
function cdPeriod(r) {{
  if (!r.pop_start_date && !r.pop_end_date) return '&mdash;';
  return `${{r.pop_start_date || '?'}} &rarr; ${{r.pop_end_date || '?'}}`;
}}

function cdRender() {{
  cdBodyEl.innerHTML = '';
  cdCountEl.textContent = `${{cdFiltered.length}} of ${{CD_RECORDS.length}} contracts`;
  cdEmptyEl.style.display = cdFiltered.length === 0 ? 'block' : 'none';
  const frag = document.createDocumentFragment();
  cdFiltered.forEach((r, i) => {{
    const tr = document.createElement('tr');
    if (r.near_threshold) tr.className = 'near-threshold';
    tr.innerHTML = `
      <td class="rank">${{i+1}}</td>
      <td class="cat">${{r.vendor}}</td>
      <td class="num">${{fmtFull(r.amount)}}</td>
      <td class="branch">${{r.branch_short}}</td>
      <td class="ex">${{r.award_date || '&mdash;'}}</td>
      <td class="geo">${{cdPeriod(r)}}</td>
      <td class="memo">${{r.description || '&mdash;'}}</td>
      <td class="ex">${{r.psc_description || '&mdash;'}}</td>
      <td class="geo">${{cdPop(r)}}</td>
      <td class="geo">${{cdVendorLoc(r)}}</td>
      <td class="ex">${{r.type_of_contract_pricing || '&mdash;'}}</td>
      <td class="ex">${{r.award_id}}</td>
    `;
    frag.appendChild(tr);
  }});
  cdBodyEl.appendChild(frag);
}}
cdRender();

cdSearchInput.addEventListener('input', () => {{
  const q = cdSearchInput.value.trim().toLowerCase();
  if (!q) {{
    cdFiltered = CD_RECORDS.slice();
  }} else {{
    cdFiltered = CD_RECORDS.filter(r => {{
      return (r.vendor || '').toLowerCase().includes(q)
        || (r.description || '').toLowerCase().includes(q)
        || (r.psc_description || '').toLowerCase().includes(q)
        || (r.naics_description || '').toLowerCase().includes(q)
        || (r.branch_short || '').toLowerCase().includes(q)
        || (r.awarding_sub_agency || '').toLowerCase().includes(q)
        || (r.awarding_office || '').toLowerCase().includes(q)
        || (r.pop_city || '').toLowerCase().includes(q)
        || (r.pop_state || '').toLowerCase().includes(q)
        || (r.vendor_city || '').toLowerCase().includes(q)
        || (r.vendor_state || '').toLowerCase().includes(q)
        || (r.award_id || '').toLowerCase().includes(q);
    }});
  }}
  cdRender();
}});

function csvEscape(v) {{
  if (v === null || v === undefined) return '';
  const s = String(v);
  if (/[",\\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
  return s;
}}

document.getElementById('cdDownloadBtn').addEventListener('click', () => {{
  const header = CD_COLUMNS.map(([, label]) => csvEscape(label)).join(',');
  const lines = cdFiltered.map(r => CD_COLUMNS.map(([key]) => csvEscape(r[key])).join(','));
  const csv = [header, ...lines].join('\\r\\n');
  const blob = new Blob([csv], {{ type: 'text/csv;charset=utf-8;' }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'dod_singlebid_contracts_under_350k_fy20_fy26ytd.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}});

/* ---------- Tabs ---------- */
const tabBtns = document.querySelectorAll('.tab-btn');
tabBtns.forEach(btn => {{
  btn.addEventListener('click', () => {{
    tabBtns.forEach(b => b.setAttribute('aria-selected', 'false'));
    document.querySelectorAll('.tabpanel').forEach(p => p.classList.remove('is-active'));
    btn.setAttribute('aria-selected', 'true');
    document.getElementById(btn.getAttribute('aria-controls')).classList.add('is-active');
  }});
}});
</script>
"""

with open(r"C:\finances\data\sba_loans\dod_fy20_fy26ytd_dashboard.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Written", len(html), "chars")
