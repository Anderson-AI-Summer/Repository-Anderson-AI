# NASA Procurement Intelligence Dashboard

An unofficial, educational-project pipeline that retrieves NASA prime-contract
transaction data from [USAspending.gov](https://www.usaspending.gov/), cleans
and standardizes it, runs it through a three-agent workflow (supplier
resolution, spend classification, procurement insights), and renders a
single self-contained, interactive HTML dashboard that opens in any modern
browser with no network access required.

**Not affiliated with or endorsed by NASA.**

## Quickstart

```bash
cd "Lindsay Work"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m src.cli setup       # environment check
python -m src.cli sample      # fast real-data pull (default: 300 txns) -> outputs/nasa_procurement_dashboard.html
python -m pytest              # 54 tests, all offline/deterministic
```

Open `outputs/nasa_procurement_dashboard.html` directly in a browser -- no
server needed.

## Commands

| Command | What it does | Network? |
|---|---|---|
| `python -m src.cli setup` | Checks Python version, dependencies, and whether `ANTHROPIC_API_KEY` is configured | No |
| `python -m src.cli sample` | Pulls a small, real (capped) set of NASA transactions for fast iteration | Yes |
| `python -m src.cli refresh` | Full NASA FY2020-present pull, processes, and regenerates the dashboard | Yes |
| `python -m src.cli build` | Rebuilds the dashboard HTML from the last processed dataset on disk | No |
| `python -m pytest` | Runs the test suite | No |

`refresh` accepts `--start`, `--end`, `--limit`, and `--max-workers`. Omitting
`--limit` runs a genuinely uncapped full refresh (may take a long time --
award-detail lookups are the bottleneck, parallelized with a thread pool).
`sample` always applies a disclosed cap (default 300) for fast dev iteration.

## Architecture

```
src/
  config.py              paths, constants, NASA agency scope, env loading
  fiscal.py              federal fiscal year math
  usaspending_client.py  paginated USAspending API client (retries, backoff)
  ingest.py              orchestrates API pull + award-detail enrichment + raw extract
  clean.py               raw -> clean field mapping/typing/standardization
  obligations.py         signed-obligation derivation, negative-obligation flags
  taxonomy.py            deterministic PSC/NAICS/keyword spend classification
  supplier_resolution.py deterministic supplier clustering (UEI/DUNS/name/fuzzy)
  enrich.py              clean -> enriched (wires in the three agents)
  analytics.py           all deterministic metrics (annual, HHI, tail spend, ...)
  agents/
    base.py              shared caching/validation/mode-tracking harness
    supplier_agent.py     Agent 1: adjudicates ambiguous fuzzy name-match candidates
    classification_agent.py  Agent 2: classifies transactions the deterministic pass couldn't
    insights_agent.py     Agent 3: narrates deterministic metrics into grounded findings
  dashboard/
    data_prep.py          builds the single JSON payload embedded in the HTML
    generate.py            renders the self-contained HTML (Jinja2 + inlined Plotly.js)
    template.html.j2 / app.js / (CSS inline in template)
    validate.py            pre-swap sanity checks on freshly generated HTML
  pipeline.py             ties it all together for sample/refresh/rebuild
  cli.py                  argparse entry point
```

### Data layers

1. **Raw** -- unmodified USAspending API responses, saved as immutable
   timestamped JSON under `data/raw/` (never mutated after write).
2. **Clean** -- typed, standardized fields mapped from raw (see field mapping
   below), saved to `data/processed/clean_transactions_latest.csv` (+
   timestamped snapshots).
3. **Enriched** -- clean + supplier resolution + spend classification +
   negative-obligation flags, saved to
   `data/processed/enriched_transactions_latest.csv`. This is what feeds
   analytics and the dashboard.

### USAspending ingestion

Two USAspending endpoints are combined:

- `POST /api/v2/search/spending_by_transaction/` -- paginated transaction
  list (the per-transaction signed amount, action date, modification
  number, recipient, PSC/NAICS). Filtered to `award_type_codes: [A, B, C, D]`
  (prime contracts only -- no assistance, no subawards) and
  `agencies: [{type: awarding, tier: toptier, name: "National Aeronautics
  and Space Administration"}]`.
- `GET /api/v2/awards/<generated_id>/` -- full award-level detail (parent
  award ID, recipient UEI/DUNS, period of performance, extent competed,
  contract pricing type, set-aside type, number of offers received). Fetched
  once per unique award (not per transaction), cached to
  `data/cache/award_details/`, and parallelized with a thread pool for
  larger pulls.

**Why not the bulk async download endpoint** (`/api/v2/download/transactions/`)?
It was tested directly against the live API from this environment and
intermittently failed (`"status": "failed", "message": "An error occurred."`
after ~40s) with no more specific diagnostic. The paginated search + award-detail
join above was verified reliable end-to-end against real data and is used as
the primary ingestion path instead. The bulk endpoint remains a documented,
known-flaky alternative for future work.

Post-ingestion validation confirms every `generated_internal_id` in the raw
extract starts with `CONT_AWD_` (contract), never `ASST_` (assistance) --
recorded in the refresh manifest's `validation_results`.

### Field mapping (source -> internal)

| Internal field | Source |
|---|---|
| `transaction_id` | `internal_id` (transaction search) |
| `award_id_piid` | `Award ID` |
| `parent_award_id` | award detail `parent_award.piid` |
| `modification_number` | `Mod` |
| `action_date` | `Action Date` |
| `transaction_obligated_amount` | `Transaction Amount` (kept signed) |
| `recipient_uei` / `recipient_duns` | `Recipient UEI` / award detail `recipient.recipient_unique_id` |
| `psc_code` / `psc_description` | `product_or_service_code` / `_description` |
| `naics_code` / `naics_description` | `naics_code` / `naics_description` |
| `period_of_performance_*` | award detail `period_of_performance.*` |
| `current_award_amount` / `potential_award_amount` | award detail `total_obligation` / `base_and_all_options` |
| `extent_competed`, `contract_pricing_type`, `set_aside_type`, `number_of_offers_received` | award detail `latest_transaction_contract_data.*` |

Award-detail fields reflect the award's **latest known state**, not its
state at the time of each individual transaction -- USAspending does not
expose point-in-time award snapshots per transaction through this API. This
is disclosed in `PROJECT_SUMMARY.md` and flagged in the data-quality summary.

### Negative obligations

Signed amounts are preserved end to end. `transaction_obligation_signed` /
`_absolute` / `obligation_direction` (`OBLIGATION` / `DEOBLIGATION` /
`ZERO_DOLLAR_ACTION`) are derived, never overwritten. Deobligations are
flagged (missing award ID, cumulative award total gone negative, deobligation
exceeding known prior obligations, same-day reversal pairs, cancellation-
suggesting description keywords) but **never deleted or zeroed**. See
`src/obligations.py`.

### Three-agent workflow

Each agent has structured (pydantic) input/output, disk caching keyed by a
hash of its inputs + prompt version (+ taxonomy version for classification),
and runs in `LIVE_AGENT` mode when `ANTHROPIC_API_KEY` is configured,
`CACHED_AGENT` mode when a prior live result is reused, or
`DETERMINISTIC_FALLBACK` mode otherwise -- disclosed in the dashboard header.
See `PROJECT_SUMMARY.md` for full rationale.

1. **Supplier Resolution Agent** -- adjudicates only the ambiguous fuzzy
   name-match *candidates* that deterministic UEI/DUNS/exact-name clustering
   left unresolved. Never merges two different non-null UEIs.
2. **Spend Classification Agent** -- classifies only the transactions the
   deterministic PSC/NAICS/keyword pass couldn't confidently place.
3. **Procurement Insights Agent** -- narrates metrics already computed by
   `src/analytics.py`; never performs its own arithmetic, never claims
   fraud/policy violations/guaranteed savings/preferred-supplier status.

### Offline sample / fallback CSVs

**The official USAspending API is the only source used to build the primary
refresh** (`python -m src.cli refresh`, which produces
`outputs/nasa_procurement_dashboard.html`). Any NASA CSV is supported only
as an optional sample or fallback input -- never blended into or used to
replace the required API-sourced refresh:

- `data/samples/nasa_sample_transactions_clean.csv` is a small (187-row),
  real (not fabricated) extract: the first ~200 NASA prime-contract
  transactions returned by a live API pull for October-December 2019
  (FY2020 Q1), deduplicated. It is loaded automatically (`load_offline_sample`
  in `src/ingest.py`) only if a live API pull fails, and can be forced for
  offline development.
- `src/ingest.fetch_from_repo_csv()` can parse any other pre-existing NASA
  CSV committed elsewhere in the repository (e.g. a teammate's
  `data/nasa_fy2025_contract_transactions.csv`) for standalone sample/demo
  use. It is a separate, explicitly-invoked utility -- `refresh` never calls
  it automatically, and its output is never merged into the API-sourced
  dataset.

### Full-refresh coverage across fiscal years

`refresh` always queries the official API for the full requested date range
(`--start`/`--end`, default `2019-10-01` through today). If `--limit` is
given, the cap is spread evenly across each fiscal year in that range (one
API call per FY, see `_fetch_spread_across_fiscal_years` in
`src/pipeline.py`) so a time-bounded run still yields genuine multi-year
coverage, rather than only the most recent months (which is what a single
flat cap on a most-recent-first sort would otherwise produce). Omitting
`--limit` runs a fully uncapped refresh across the entire range.

## Dashboard: branding, Standout Suppliers, and Top Contracts (added in v2)

Additions on top of the original five-tab dashboard, all computed in Python
and rendered the same disclosed way as everything else here (never
hand-edited):

- **Top Contracts & Awards panel** (Executive Overview tab, `_standout_awards`
  in `src/dashboard/data_prep.py`). The same idea as Standout Suppliers, one
  level down: up to 5 contract awards (grouped by `award_id_piid`) surfaced
  by value and by two disclosed signals -- deobligation share, and growth
  via modifications (current net obligations vs. the award's first recorded
  transaction). Explicitly **not** a cost-overrun finding -- a repo-CSV- or
  even API-sourced dataset has no contract ceiling/scope-of-record to
  compare against, only what the transaction history itself shows, and the
  card language says so. Each card shows the award's actual, unedited
  transaction description from the government record (the closest thing to
  "what was purchased" this data provides), a category icon, and the same
  three actions as supplier cards (View award on USAspending.gov, Export
  contract CSV, Mark for review).
  - **No web-fetched product/mission photography.** This was considered and
    intentionally not done: the dashboard's core design principle is
    "self-contained, works fully offline, no network call at view time,"
    and this build environment's outbound network access is blocked (a
    direct test against `nasa.gov` itself returned a 403 at the connection
    level), so no image could even be fetched and verified at *generation*
    time either. Category icons are small inline SVGs generated locally
    (`CATEGORY_ICONS` in `src/dashboard/app.js`) -- illustrative of the
    spend category, not a photo of the actual hardware/product. A future
    version could fetch real (public-domain) NASA imagery for well-known,
    keyword-recognizable programs at *build* time and embed it as a data
    URI (the same technique already used for fonts and Plotly.js), from an
    environment where outbound network access isn't blocked.

- **NASA-themed header.** A stylized orbit/rocket mark and "NASA" wordmark in
  NASA's brand blue/red, plus a visible "Unofficial · Not NASA-affiliated"
  badge. This intentionally does **not** use NASA's actual insignia (the
  "meatball") or wordmark logotype -- both are protected under 14 CFR Part
  1221, and reproducing them risks implying an official endorsement this
  project explicitly disclaims. The color palette and a generic space icon
  make the domain obvious without borrowing the real mark.
- **Standout Suppliers panel** (Executive Overview tab, `_standout_suppliers`
  in `src/dashboard/data_prep.py`). Surfaces up to 5 suppliers via three
  disclosed, evidence-based signals -- spend concentration, deobligation
  share, and year-over-year swings -- each citing the exact supporting
  metric. Same rule as the Insights Agent: never a performance rating or a
  claim of wrongdoing, only "worth confirming against the award record."
  Each card has three actions: **View on USAspending.gov** (opens the real
  public search for that recipient), **Export supplier CSV** (client-side,
  from the embedded transaction rows), and **Mark for review** (a local
  annotation saved to this browser's `localStorage` only -- it does not
  notify or file anything anywhere).

`outputs/nasa_fy2025_realdata_dashboard.html` demonstrates both against a
teammate's real 21,240-row NASA FY2025 pull (`../data/nasa_fy2025_contract_transactions.csv`,
ingested via `fetch_from_repo_csv`) rather than the small offline sample:
$15.78B net obligations, 20,354 deduplicated transactions, 2,867 normalized
suppliers. `outputs/nasa_procurement_dashboard_presentation.html` (the
originally frozen live-API pull) is left untouched.

## Live Lookup mode (added in v3)

`outputs/nasa_live_dashboard.html` (Harrison) is a second, independent
dashboard mode: it queries `api.usaspending.gov` directly from the browser
-- no server, no embedded data -- for any fiscal year back to FY2008,
including the in-progress current year. A fiscal-year selector re-fetches
the monthly trend, award-type breakdown, and top-20-recipients panels, and
a transaction register is live-paginated (50 rows/page) against the API with
debounced keyword search, an award-type filter, and sortable columns, so it
stays fast regardless of a fiscal year's volume rather than trying to hold
every transaction in memory. It's cross-linked with the main analysis
dashboard ("🛰 Live Lookup (any year)" in the header / "← Deep Analysis
Dashboard" in its own masthead) and carries the same "Unofficial ·
Not NASA-affiliated" disclosure as the rest of this project.

**Why this is a second page instead of a live mode for the existing
dashboard.** The Executive Overview / Standout Suppliers / Categories tabs
above depend on this project's own Python pipeline -- UEI/DUNS supplier
resolution, PSC/NAICS taxonomy classification, HHI concentration, tail
spend, deobligation flagging, the standout/consolidation/duplicate-purchase
signals -- none of which exist as a live API endpoint to call. Reproducing
that logic in the browser would mean re-implementing a tested Python
pipeline in client-side JS against a much larger pull (a full fiscal year
of transactions, not the ~300-row page a human browses), with no way to
verify correctness the way the 61-test suite does today. Instead, Live
Lookup surfaces exactly what the raw API returns -- **raw, unnormalized
recipient names, no spend-category taxonomy, no supplier resolution, no
standout signals** -- and says so explicitly in its own masthead, so it's
never confused with the analyzed numbers above it.

**Why this needed no change to this project's "self-contained, offline"
design principle.** The rest of this README (and the note under "No
web-fetched product/mission photography" above) explains that *this build
environment's* outbound network access is blocked at the connection level.
That constraint is about where the HTML is *generated* -- it has no bearing
on Live Lookup, whose `fetch()` calls run in whoever's browser has the page
open, not in this build environment. The analysis dashboard stays exactly
as self-contained as before; Live Lookup is opt-in, one click away, and
degrades to a clear per-panel error message (not a crash) if the viewer's
own connection can't reach `api.usaspending.gov`.

## Three more signals, from the professor's assignment review

Added directly in response to recorded class feedback (see
`PROJECT_SUMMARY.md` for the full discussion of each). All three follow the
same rule as the rest of the dashboard: disclosed, evidence-cited, never a
claim the data can't back.

- **Consolidation Opportunities** (`_consolidation_opportunities` in
  `src/dashboard/data_prep.py`). *"Within a category they're spending with
  various vendors -- opportunity to reach a volume-based discount if they
  stick with one preferred supplier."* Surfaces categories where spend is
  split across 3+ suppliers with no dominant one (HHI < 2500, DOJ/FTC's own
  "unconcentrated/moderate" cutoff). Deliberately does **not** name a
  replacement vendor or estimate a dollar savings -- there's no per-vendor
  unit-price or contract-tier data available to back either claim.
- **"New since last run"** (`_mark_new_since_last_run` in `src/pipeline.py`,
  a small JSON snapshot at `data/processed/standouts_snapshot.json`,
  regenerable/gitignored like the rest of that folder). *"We only catch
  about 10% [of financial malfeasance] -- the deterrence is the goal...
  agents autonomously monitoring is a huge deterrence boost."* Every prior
  version of this dashboard re-surfaced the same handful of flagged items
  on every run with no memory of the last one. Now each standout supplier,
  contract, consolidation opportunity, and duplicate-purchase candidate
  carries an `is_new` flag, and the dashboard shows a green "New" badge for
  anything that wasn't flagged last time -- the beginning of an actual
  monitoring workflow instead of a static snapshot. First-ever run marks
  nothing as new (nothing to compare against yet); this is disclosed in a
  banner at the top of the Standouts tab.
- **Possible Duplicate Purchases** (`_duplicate_purchase_candidates`). The
  "school chair pass" story -- budget rules driving a second, separate
  purchase instead of one consolidated one. Flags pairs of *separate*
  awards (contract modifications on the same award are already covered by
  the existing "grew via modifications" signal) to the same supplier, same
  category, similar dollar amount (within 30%), close together in time
  (within 120 days). Capped between $5K and $2M per award on purpose: above
  that, two same-supplier awards close together are more likely parallel
  program funding to a major prime (observed directly on the real NASA
  data -- Boeing/Caltech-JPL routinely have multiple large, legitimately
  distinct awards close together) than an administrative duplicate; this
  signal targets the smaller, more mundane purchase pattern the professor
  described, not big-program contracting.

## Environment / secrets

Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY` to enable
`LIVE_AGENT` mode. Without it, every agent runs in a clearly labeled
`DETERMINISTIC_FALLBACK` mode -- the pipeline is fully functional either way.
`.env` is gitignored. No secret ever appears in generated HTML, logs, cache
files, or committed config (`src/dashboard/generate.py` refuses to write the
dashboard if a secret-shaped string is detected in it).

## Limitations

- USAspending's bulk async transaction-download endpoint is flaky in this
  environment (documented above); the paginated-search + award-detail-join
  path is used instead.
- Award-level fields (parent award, period of performance, extent competed,
  pricing type, set-aside, offers received) reflect the award's latest known
  state, not a point-in-time snapshot at each transaction's action date.
- The hand-authored PSC/NAICS/keyword taxonomy is a deterministic first pass,
  not an official government crosswalk; ambiguous records are routed to the
  classification agent or left "Needs Review" rather than guessed.
- Supplier-name resolution is evidence-based (UEI/DUNS/exact-name/fuzzy) but
  cannot detect shell-company relationships or common ownership that share
  no identifying evidence.
- The Transaction Explorer embeds a disclosed, configurable row cap
  (`EXPLORER_EMBED_ROW_LIMIT`, default 8,000) of the most recent transactions
  directly in the HTML; the complete processed dataset always remains in
  `data/processed/` outside the HTML.
