# Reviewing v3 — instructions for the team

This is a walkthrough for anyone on the team who hasn't looked at `v3/` yet.
Should take about 10-15 minutes. No install required for the review itself —
only the "run it yourself" section at the bottom needs Python.

## 1. Get it

```bash
git checkout main
git pull
```

Everything below lives under `v3/nasa_procurement/outputs/`. Open these
directly in a browser — double-click, or drag into a tab. No server, no
`npm install`, nothing to set up:

- **`nasa_fy2025_realdata_dashboard.html`** — the main analysis dashboard.
  Real 20,354-transaction FY2025 NASA pull, fully self-contained (works with
  wifi off).
- **`nasa_live_dashboard.html`** — Harrison's live USAspending.gov lookup.
  Needs a **real internet connection** to actually show numbers (see
  limitations below).

## 2. What's new in v3 (vs the v2 milestone)

`v3/` is a complete copy of `v2/` (nothing in `v2/` was touched) plus:

- **Live Lookup integration.** Harrison's `nasa_live_dashboard.html` — query
  `api.usaspending.gov` directly from the browser for any fiscal year back
  to FY2008, no server, always current — is now wired into the main
  dashboard. A "🛰 Live Lookup" button sits in the header; the Executive
  Overview, Year-over-Year Trends, and Transaction Explorer tabs each have a
  Fiscal Year selector that offers every year back to 2008 — pick the
  embedded year (FY2025) and it behaves as before, pick any other year and
  it hands off to Harrison's live page pre-set to that year.
- **Interactive UI.** Command palette (`Ctrl`/`Cmd`+`K`) to jump to any
  supplier/award/category/tab, a persistent light/dark theme toggle,
  sortable table headers, toast notifications on mark-for-review/export
  actions, animated KPI counters.
- **Click-to-explain KPI tiles.** Every big number on Executive Overview and
  the Categories tab (Net Obligations, Deobligations, Unique Awards, HHI,
  etc.) is clickable — shows the exact formula plus the actual rows behind
  it, not just the aggregate.
- **Fixed Overview charts.** The two charts that used to be unreadable
  (Category Composition dominated by "Other or Unclassified"; a single-bar
  "Annual Trend" for a one-year dataset) now split that category into its
  own callout and fall back to monthly granularity.
- **Three signals from the professor's review**: Consolidation Opportunities,
  "new since last run" flags, and Possible Duplicate Purchases — all under
  the Standout Suppliers & Contracts tab.

## 3. Review checklist

- [ ] **Executive Overview** loads with $15.78B net obligations, 20,354
      transactions, 9,383 unique awards, 2,867 normalized suppliers.
- [ ] Click the **"🛰 Live Lookup"** button in the header → opens
      `nasa_live_dashboard.html` in a new tab.
- [ ] On **Executive Overview**, change the **Fiscal Year** dropdown to any
      `(live →)` option → an inline notice appears, clicking it opens Live
      Lookup pre-set to that exact year. Switch back to `FY2025 (embedded)`
      → notice disappears, KPIs unchanged.
- [ ] Same check on **Transaction Explorer** (table clears with a notice
      instead of silently showing 0 rows) and **Year-over-Year Trends**
      (charts stay on FY2025, notice explains why).
- [ ] Click any KPI tile's **"⋯ HOW?"** hint (e.g. Net Obligations) →
      modal shows the formula and the actual largest transactions behind it.
- [ ] `Ctrl`/`Cmd`+`K` → type a supplier name → `Enter` jumps to it.
- [ ] Toggle **☀/🌙 theme** (top right) → confirm it persists after reload.
- [ ] **Standout Suppliers & Contracts** tab → check the Consolidation
      Opportunities and Possible Duplicate Purchases panels exist and each
      card cites a specific supporting number (never an unsupported claim).
- [ ] Open **`nasa_live_dashboard.html`** directly (not through this repo's
      preview, an actual browser tab) with real wifi on → pick a few
      different fiscal years from its own dropdown → confirm real numbers
      load (this is the one thing I could not verify myself — see below).

## 4. Known limitations — please help verify these

- **I could not confirm Live Lookup actually pulls real data.** This build
  environment's own network is blocked (`api.usaspending.gov` returns 403
  here), so I only verified the page loads and fails *gracefully* (a clear
  per-panel error, not a crash) — never a successful live fetch. Whoever has
  a normal internet connection, please open `nasa_live_dashboard.html`
  directly and confirm a few years actually populate with real numbers.
- **Live Lookup won't work embedded in some previews** (e.g. this repo's
  Claude Artifact link, or any sandboxed webview) — it needs a real browser
  tab's normal network access. Open the file directly if a preview looks
  broken.
- **Only FY2025 has the full analysis** (supplier resolution, spend
  classification, standout signals). Other years, reached via Live Lookup,
  show raw USAspending.gov figures only — no normalized supplier names, no
  category taxonomy. This is intentional and disclosed on that page itself,
  not a bug.

## 5. Where to go deeper

- `v3/README.md` — two-tier layout (flagship vs. general engine)
- `v3/nasa_procurement/README.md` — full architecture, three-agent workflow,
  and the "Live Lookup mode" section explaining why it's a separate page
- `v3/nasa_procurement/PROJECT_SUMMARY.md` — pitch-level summary

## 6. Run it yourself (optional, needs Python)

```bash
cd v3/nasa_procurement
pip install -r requirements.txt
python3 -m src.cli build      # rebuilds outputs/nasa_procurement_dashboard.html, no network needed
python3 -m pytest             # 61 tests
```
