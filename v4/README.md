# Version 4

Working copy, forked from `v3/` at commit `e24de18` so development can
continue while v3 is being published to a public URL. **`v3/` is frozen for
that publication — make changes here, not there.**

At the fork point this is a byte-identical copy of v3's tracked files
(109 files). Regenerable material was deliberately not copied: the
award-detail cache and processed datasets under `nasa_procurement/data/`
(~988 MB, gitignored) rebuild from the API via `python -m src.cli refresh`.

Two tiers, unchanged from v3:

1. **[`nasa_procurement/`](nasa_procurement/)** — the flagship real-data
   implementation. Pulls NASA prime-contract transactions from the
   USAspending.gov API (FY2020–FY2026 embedded: 142,290 transactions,
   $102.67B net obligations, 41,411 awards, 7,049 normalized suppliers),
   resolves supplier identity on UEI/DUNS evidence (not just name matching),
   classifies spend on a NASA-specific PSC/NAICS taxonomy, derives
   signed/deobligation-aware analytics (HHI concentration, tail spend, YoY
   category shifts), and narrates findings through a three-agent workflow —
   deterministic code owns all arithmetic; agents only adjudicate ambiguity
   or narrate results already computed — into one self-contained interactive
   dashboard. 68 tests, all offline/deterministic.

   Eight tabs: Executive Overview, Standout Suppliers & Contracts,
   Year-over-Year Trends, Transaction Explorer, Supplier Analysis,
   Categories & Opportunities, Action Center (mitigation workflows), and
   Misuse Protection (sub-threshold single-bid screen). A global `FY … to
   FY …` Timeframe control in the header scopes them together.

2. **[`spend_agent/`](spend_agent/)** — the general-purpose engine the
   flagship is a specialization of, plus the PPP and USAspending
   explorations under `ppp/` and `usaspending/`.

## Start here

```bash
cd v4/nasa_procurement
pip install -r requirements.txt
python -m pytest                # 68 tests, offline
python -m src.cli build         # rebuild dashboard from processed data
```

`nasa_procurement/README.md` has the full architecture and the reasoning
behind each design decision. `nasa_procurement/outputs/README.md` covers
publishing a built dashboard and the disclaimers that must travel with it.

## Carried-over caveats worth re-reading before changing anything

- **The Action Center is a demonstration.** Workflow state lives in the
  viewer's `localStorage`; nothing is transmitted and no contracting action
  is executed. If v4 makes it real, that banner has to change with it.
- **Misuse Protection flags legitimate contracts by design.** Its top hits
  are proprietary software vendors (COMSOL, ANSYS, Siemens) at 100%
  single-bid, which is correct for sole-source licensing. It produces
  candidates for human review, not findings.
- **Competition data comes only from USASpending's per-award endpoint** —
  both bulk search endpoints return null for those fields. It was backfilled
  for the 34,413 sub-threshold awards Misuse Protection examines; 28,085 of
  41,411 awards carry it. A fresh `refresh --skip-award-details` will not
  have it, and the tab will correctly report itself unavailable.
- **`REVIEW_V3.md`** is kept as the historical record of the v3 review and
  still refers to `v3/` paths on purpose.

## Implemented in v4

All three items parked at the fork are done. Each was verified rather than
assumed -- see the commit for measurements.

**1. Misuse Protection no longer buries real signals under software licensing.**
Awards whose PSC identifies a proprietary licence (`7030`, `DA10`, `7A*` --
see `nasa_procurement/config/misuse_excluded_psc.json`, editable without a
code change) are set aside from the ranking: a single offer for a product
only one vendor sells is the expected outcome, not a competition-avoidance
signal. They are *set aside, not deleted* -- a dedicated panel reports how
many awards and suppliers were excluded, with the PSC codes and the reason
for each, so the screen never silently hides a supplier. Deliberately not
excluded: labour/support services (`DA01`, `D311`), hardware-with-bundled-
licence products (`7B*`, `7C*`, `7E*`, …) and lab equipment (`6640`,
`6695`), which have genuine competitive markets.

**2. Supplier and Category KPIs follow the Timeframe control.**
`_supplier_detail` and `_category_detail` now emit the full metric set per
fiscal year, so those tabs' KPI tiles scope to the selected range instead of
being stuck at all-time. Net obligations, gross, deobligations and
transaction counts sum exactly; supplier "share of total obligations" is
recomputed against the *same range's* agency-wide total rather than an
all-time denominator.

Distinct counts are the honest exception. Unique Awards (supplier tab) and
Unique Suppliers (category tab) do not sum across years -- an award running
through three selected years is counted once per year -- so a multi-year
range labels them `≤` and says why. Concentration (HHI) and Tail Spend Share
stay all-time and say so: both are ratios over the whole supplier
distribution, and no combination of yearly values reproduces a range's real
figure.

**3. Builds are roughly 10x faster.**
`_award_rows` and `_supplier_detail` were Python loops over pandas groupby
groups -- 41k iterations each, run once per fiscal-year range by
`_standout_by_range` (28 ranges), which is what made a full build take ~32
minutes. Both are now vectorized aggregations, as is
`_bid_competition_review`. Measured on the 142,290-transaction dataset:

| stage | before | after |
|---|---|---|
| `_award_rows` | 96s | 4.5s (21x) |
| full build | ~32 min | **2m 40s** (12x) |

Output equivalence was checked award by award against the original
implementation across all 41,411 awards. The only differences are 23 awards
(0.06%) where the source data contains an exact tie -- two transactions
sharing the earliest date, or a 1-1 split between two suppliers/categories
on the same award. The old code broke those ties with pandas' default
*unstable* quicksort, so its answer was not reproducible run to run; the new
code sorts stably, so it is. No metric changed.

**4. Drill-down rows drive the workflow starter.**
In a KPI drill-down, clicking a row selects it and sets "Apply to" below, so a
workflow attaches to the supplier or award you were already looking at instead
of being re-found in a 60-entry dropdown. A row usually names both a supplier
and an award, so the two cells are individually pickable (dotted underline);
clicking anywhere else on the row falls back to the supplier, which is what
most playbooks act on. Selection runs both ways -- choosing from the dropdown
highlights the matching rows. Findings opened from the Overview share this
modal and now re-render their own starter rather than inheriting whichever
KPI was opened before them.

## Ideas parked for later

- Per-range HHI and tail-spend, which would need the supplier distribution
  recomputed per range rather than summed.
- Exact distinct counts across ranges, which would need per-year award and
  supplier ID sets in the payload (feasible: roughly 600 KB) rather than the
  current disclosed upper bound.
- Shorter payload keys for the per-year blocks. The new per-year metrics
  added ~2 MB to `suppliers_detail`, almost all of it repeated JSON key
  names (`gross_positive_obligations` written 7,049 x 7 times). Renaming
  them would recover most of that, at the cost of a rename across both
  `data_prep.py` and `app.js`; for now the hostable build absorbs it by
  caching 1,500 Explorer rows instead of 2,500.
