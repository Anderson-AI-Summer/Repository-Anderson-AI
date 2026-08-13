# Project Summary: NASA Procurement Intelligence Dashboard

## Problem

USAspending.gov publishes every federal contract transaction, but the raw
data is not analysis-ready: recipient names appear under dozens of string
variants, spend has no category taxonomy, contract modifications and
deobligations mix in with new obligations, and there is no single view that
lets a reviewer ask "who are we buying from, in what categories, and does
anything here warrant a closer look?" This project builds a pipeline that
retrieves NASA's prime-contract transactions (FY2020-present), cleans and
standardizes them, resolves supplier identity, classifies spend into a
NASA-specific taxonomy, and surfaces evidence-grounded procurement
observations -- all rendered into one self-contained HTML file that opens
offline in any browser.

## Architecture

Three data layers (raw -> clean -> enriched), computed once and cached to
disk, feed a deterministic analytics module, which in turn feeds both the
LLM-based Insights Agent and the dashboard's charts and tables directly. See
`README.md` "Architecture" for the full module map. The guiding principle
throughout: **deterministic code owns the arithmetic; agents only
adjudicate ambiguity or narrate results the code already computed.**

## The three agents

1. **Supplier Resolution Agent** -- Deterministic clustering (shared UEI,
   then legacy DUNS, then exact normalized name) resolves the large majority
   of records with high confidence and zero LLM calls. Only the leftover
   *fuzzy candidates* -- name pairs that survive a similarity threshold and a
   whole-token-prefix check -- are sent to the agent for adjudication. The
   agent is explicitly instructed never to merge on a shared generic word
   (the "First National Bank" vs "First Republic Bank" failure mode
   documented in `v1/PROJECT_WRITEUP.md` from earlier coursework informed
   this design), and two records with different non-null UEIs are excluded
   from candidate generation entirely -- they can never be merged, by either
   the agent or the deterministic fallback, regardless of name similarity.

2. **Spend Classification Agent** -- A hand-authored, versioned two-level
   taxonomy (`config/taxonomy.json`) with per-subcategory PSC-prefix,
   NAICS-code, and keyword evidence handles the clear-cut cases
   deterministically (evidence order: PSC, then NAICS, then description
   keywords). Only transactions with no deterministic match go to the agent,
   batched by a cache key of `(psc_code, naics_code, description[:300])` so
   identical ambiguous combinations share one call. The agent must pick from
   the same fixed taxonomy or abstain to "Other or Unclassified / Needs
   Review" -- it can never invent a category.

3. **Procurement Insights Agent** -- Receives the fully-computed metrics
   dict from `src/analytics.py` (HHI, top-5 share, deobligation rate, tail
   spend, category YoY changes) and narrates it into findings that cite the
   exact supporting metric. The system prompt explicitly forbids claiming
   fraud, illegality, preferred-supplier status, guaranteed savings, or
   performing its own arithmetic. The deterministic fallback
   (`_fallback_findings` in `src/agents/insights_agent.py`) applies the same
   rules via fixed templates when no live model is available, so the
   dashboard's "Key Findings" panel is never empty just because
   `ANTHROPIC_API_KEY` isn't set.

### Processing modes

Every pipeline run is labeled `LIVE_AGENT`, `CACHED_AGENT`, or
`DETERMINISTIC_FALLBACK` in the dashboard header, based on whether any agent
call this run actually hit the live API, reused a prior live result from
cache, or fell back to deterministic logic. `ANTHROPIC_API_KEY` was **not**
configured in this environment during development, so the dashboard shipped
here was built and fully tested in `DETERMINISTIC_FALLBACK` /
`CACHED_AGENT` mode. To enable live agents: copy `.env.example` to `.env`,
set `ANTHROPIC_API_KEY`, and re-run `python -m src.cli refresh` or
`sample` -- no code changes needed.

## Negative obligations and contract modifications

Federal contract spending is not monotonic: modifications routinely reduce
("deobligate") a prior obligation, and a transaction's sign matters as much
as its magnitude. This pipeline treats the signed amount as the ground
truth throughout:

- `transaction_obligation_signed` is never deleted, zeroed, or replaced with
  its absolute value. `transaction_obligation_absolute` and
  `obligation_direction` (`OBLIGATION` / `DEOBLIGATION` / `ZERO_DOLLAR_ACTION`)
  are *derived*, additive fields.
- `cumulative_award_obligation` is a running signed total per Award ID,
  ordered by action date then modification number -- computed in
  `src/obligations.compute_cumulative_award_obligation`, pure deterministic
  code, no LLM.
- Deobligations are flagged, never hidden: missing Award ID, cumulative
  award total gone negative, a deobligation larger than the award's known
  prior positive obligations, same-day exact-reversal pairs, missing action
  type, and description keywords suggesting cancellation/correction/
  termination/closeout. Awards whose first visible transaction falls in
  FY2020 are additionally flagged as possibly having obligation history that
  predates the extraction window (USAspending data existed before FY2020;
  this project's scope starts there per the assignment).
- The dashboard states explicitly, in the header and the Year-over-Year tab,
  that **net obligations are not the same as payments, expenditures, or
  outlays**.

## Deterministic analytics

All metrics displayed anywhere in the dashboard -- annual net/gross/deobligated
totals, HHI supplier concentration, top-5/top-10 share, tail spend, supplier-
category overlap, confidence distributions, year-over-year percent changes --
are computed once in `src/analytics.py` using pandas, before the HTML is
generated. The browser only filters, sorts, and re-renders what it is given;
it never recomputes the analytical model. This is also why the Insights
Agent is instructed never to perform its own arithmetic.

## Three signals added from class review

The professor's recorded feedback on this assignment mapped onto three
concrete, buildable gaps, added directly (see `README.md` "Three more
signals" for the mechanics of each):

1. **Consolidation opportunities.** The professor described finding
   categories split across many vendors as an opening to negotiate
   volume-based pricing with one preferred supplier. The pipeline already
   flags when a *designated* preferred supplier is bypassed; it had no way
   to proactively surface categories that don't have one yet because spend
   is fragmented. `_consolidation_opportunities` closes that gap using the
   category-level HHI already computed in `categories_detail` -- no new
   data pass required. It intentionally stops short of naming a specific
   replacement vendor or a savings number, since neither is backed by data
   this pipeline has (no per-vendor unit pricing).
2. **New-since-last-run flagging.** The professor's framing of deterrence
   ("we only catch ~10%... agents autonomously monitoring is a huge
   deterrence boost") implies something ongoing, not a fresh unrelated
   snapshot every time. A small JSON file
   (`data/processed/standouts_snapshot.json`, regenerable like the rest of
   that folder) now persists what was flagged last run, and every
   standout/opportunity/candidate list is diffed against it.
3. **Possible duplicate purchases.** Directly from the "school chair pass"
   anecdote -- budget rules causing a second purchase instead of one
   consolidated one. Implemented as same-supplier, same-category award
   pairs, similar amount, close in time. Calibration note: an unbounded
   version of this signal was dominated by pairs of huge, genuinely
   distinct NASA prime contracts (e.g. two $300M+ JPL awards nine days
   apart) -- normal parallel program funding, not administrative
   duplication. Capping it to $5K-$2M per award removed that noise and
   left the smaller, more plausible candidates the professor's example
   was actually describing.

## Limitations and future improvements

See `README.md` "Limitations" for the full list (bulk-download endpoint
flakiness, award-detail state being "latest known" rather than
point-in-time, taxonomy being a hand-authored first pass, name-based
supplier resolution's blind spot on shell companies). Future improvements
worth pursuing with more time: point-in-time award snapshots (would require
a different USAspending endpoint or historical crawl), a validated PSC/NAICS
crosswalk instead of a hand-authored one, and batched (rather than per-
candidate) live calls to the Supplier Resolution Agent to reduce latency on
very large refreshes.
