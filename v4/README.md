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
   dashboard. 65 tests, all offline/deterministic.

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
python -m pytest                # 65 tests, offline
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

## Ideas parked for v4

Not started — noted so they aren't lost:

- Exclude proprietary-software PSC codes from Misuse Protection so genuinely
  irregular patterns surface above routine license sole-sourcing.
- Per-year supplier/category KPI aggregates, so those two tabs' KPI tiles
  can follow the Timeframe control instead of staying all-time.
- Faster builds: `_standout_by_range` recomputes 28 fiscal-year combinations
  over the full dataset and dominates the ~30-minute build.
