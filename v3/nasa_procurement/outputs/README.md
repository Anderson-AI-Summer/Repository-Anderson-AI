# Publishing the NASA Procurement Intelligence Dashboard

**Publish this file:**

```
v3/nasa_procurement/outputs/nasa_procurement_dashboard_web.html
```

It is a single self-contained HTML file — no server, no build step, no
external requests. Drop it on any static host (GitHub Pages, Netlify,
S3, Vercel) and the URL works. Rename it to `index.html` if you want it
served at the root of a directory.

---

## Before you publish: the disclaimers must stay

This dashboard is styled like a NASA product and is named after NASA, but
it is a student project with no connection to the agency. Three things in
the page exist specifically to prevent a reader from mistaking it for an
official source. **Do not remove or downplay any of them** when you host it:

1. The `UNOFFICIAL · NOT NASA-AFFILIATED` badge in the header
2. The line "Unofficial educational project. Not affiliated with or endorsed by NASA."
3. The per-section notes explaining that flagged items are *disclosed signals, not findings*

If the hosted page gets a title or description of its own (repo name, page
`<title>`, link preview text), keep "unofficial" in it. A URL strips the
context that a file passed around in class still had.

Nothing in the page is a NASA logo or trademark — the mark in the header is
an original graphic drawn for this project, not the NASA insignia.

---

## What's in it

Real prime-contract transaction data pulled from the public
[USAspending.gov](https://www.usaspending.gov/) API.

| | |
|---|---|
| Period | 2019-10-01 → 2026-08-11 (FY2020–FY2026) |
| Transactions | 142,290 |
| Net obligations | $102.67B |
| Unique awards | 41,411 |
| Normalized suppliers | 7,049 |

### Tabs

- **Executive Overview** — headline KPIs, annual obligation trend, category composition, top suppliers/contracts, key findings. Every KPI has a click-to-explain "HOW?" breakdown showing the underlying arithmetic and contributing transactions.
- **Standout Suppliers & Contracts** — up to 5 suppliers and 5 awards surfaced by disclosed signals (spend concentration, deobligations, year-over-year swings, growth via modifications). Precomputed for all 28 fiscal-year range combinations, so it updates instantly with the Timeframe control.
- **Year-over-Year Trends** — obligations, deobligations, supplier/award counts, and concentration (HHI, top-5 share) across the selected range.
- **Transaction Explorer** — filterable/sortable transaction table with CSV export.
- **Supplier Analysis** — per-supplier drill-down: annual spend, category mix, consolidated name variants, awarding offices, data-quality flags.
- **Categories & Opportunities** — per-category spend, leading suppliers, concentration, tail spend, and a low-confidence review queue.
- **Action Center** — mitigation workflow tracker. 9 playbooks (deobligation mitigation, supplier-continuity review, scope/ceiling review, market diversification, strategic sourcing, dedup audit, …) with visual step trackers.
- **Misuse Protection** — screens for suppliers whose sub-threshold awards (default $350K) are concentrated in single-bid or non-competed procurements.

### The Timeframe control (header)

The `FY … to FY …` range picker at the top scopes Executive Overview,
Year-over-Year, Transaction Explorer, Standouts, and Action Center at once.
Supplier and Category tabs highlight the selected range in their charts
while keeping their KPI tiles all-time (only net obligations is broken out
per year for those two — summing the rest would be invented precision).

---

## Two things to know before you present it

**1. The Action Center is a demonstration, not a live system.**
Starting a workflow, advancing steps, adding notes — all of it saves to the
viewer's own browser (`localStorage`). Nothing is sent anywhere, nothing
reaches NASA or any contracting system, and no real contracting action is
executed. The tab says so in a banner. Two people opening the same URL will
not see each other's workflows. Present it as a model of what such a tool
could look like.

**2. Misuse Protection flags legitimate contracts by design.**
The top hits are COMSOL, ANSYS, Siemens, and DS Government Solutions — all
at 100% single-bid. These are proprietary engineering-software vendors,
where sole-source is correct: nobody else sells COMSOL licenses. This is the
screen working as intended, not a finding against those companies. The tab
leads with "Disclosed signal, not a finding" for exactly this reason. If
someone asks "so did you find fraud?", the honest answer is no — this
surfaces patterns a human reviewer would then clear or escalate, and the
visible examples are ones a reviewer clears in seconds.

---

## Known limits (say these before someone finds them)

- **Obligations ≠ spending.** Net obligations are signed transaction amounts, not payments or outlays.
- **FY2026 is partial** (data ends 2026-08-11) and is not comparable to complete fiscal years. The dashboard shows a warning banner about this.
- **The Explorer embeds 2,500 of 142,290 transactions** — the most recent ones, to keep the file hostable. All analytics are computed over the full dataset; only that one table's rows are capped. The complete processed dataset lives in `data/processed/`.
- **Competition data covers 28,085 of 41,411 awards.** USASpending only exposes offers-received / extent-competed on its per-award endpoint, so it was backfilled for the sub-threshold awards Misuse Protection examines. Awards without it are excluded from that screen rather than assumed competitive.
- **Supplier names are normalized heuristically** (UEI/DUNS match, then fuzzy name clustering). The Supplier Analysis tab shows the raw name variants merged into each supplier and a confidence score, so this is auditable rather than a black box.
- **Spend categories are assigned** by deterministic PSC/NAICS/keyword rules with an AI pass for the remainder. Low-confidence rows are surfaced in a review queue rather than silently trusted, and "Other or Unclassified" is kept out of the ranked category chart because it's a review queue, not a real category.

---

## Other builds in this folder

| File | Size | Use |
|---|---|---|
| `nasa_procurement_dashboard_web.html` | 13.3 MB | **Publish this one.** Full analytics, 2,500 Explorer rows. |
| `nasa_fy2019_present_realdata_dashboard.html` | 17.7 MB | Same data, 8,000 Explorer rows. Better for local review, heavy for a web page. |
| `nasa_fy2025_realdata_dashboard.html` | 13.6 MB | FY2025 only, from the repo CSV. Misuse Protection is unavailable here (that CSV has no award IDs to look competition data up with) and the tab says so. |
| `nasa_procurement_dashboard.html` | 5.4 MB | 200-transaction sample from a fast dev pull. Not for presenting. |

Even the recommended file is 13 MB, so first load takes a few seconds on a
normal connection — worth knowing before you demo it live. It renders
entirely client-side after that, with no further requests.

## Regenerating

See `../README.md` for the pipeline. Short version, from `v3/nasa_procurement/`:

```bash
pip install -r requirements.txt
python -m src.cli refresh --start 2019-10-01   # full pull (slow)
python -m src.cli build                        # rebuild HTML from processed data
python -m pytest                               # 65 tests, offline
```
