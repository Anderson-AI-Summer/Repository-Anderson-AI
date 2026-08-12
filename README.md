# Spend Classification Agent

Takes a messy transaction export, classifies each line against a spend
taxonomy, resolves vendor name variants (e.g. `STAPLES #04521`, `Staples
Business Advantage`, `STAPLES.COM`, `Staples Inc` → one vendor), and flags
purchases in categories with a designated preferred supplier that were
routed to a different vendor ("maverick spend").

## Usage

```bash
python3 -m spend_agent.cli data/sample_transactions.csv --outdir out
```

This CLI is one way to run the pipeline directly. For wiring it into a
conversational, tool-calling LLM agent instead — a system prompt plus a
tool interface mapped to the functions below — see
[`spend_agent/AGENT_SYSTEM_PROMPT.md`](spend_agent/AGENT_SYSTEM_PROMPT.md).

Optional flags let you point at different config:

```bash
python3 -m spend_agent.cli path/to/transactions.csv \
  --taxonomy config/taxonomy.json \
  --suppliers config/preferred_suppliers.json \
  --aliases config/vendor_aliases.json \
  --outdir out
```

Reports are written to `--outdir`:

- `classified_transactions.csv` — every row with its resolved vendor, category, and bypass flag
- `vendor_alias_report.md` — vendors detected under more than one raw name
- `maverick_spend_report.md` — flagged purchases, grouped by category, with totals
- `llm_assisted_report.md` — only written when `--llm-fallback` classified at least one row (see below)

### Optional LLM fallback for unresolved rows

The taxonomy classifier is intentionally rule-based (see below) — but a fixed
keyword list can't resolve every row, and those are worth a second look
smarter than "leave it Uncategorized forever." Pass `--llm-fallback` to have
`spend_agent/llm_classifier.py` ask Claude (`claude-opus-5`, via the
`anthropic` SDK) to pick a category from the same taxonomy for any row the
keyword classifier leaves as `Uncategorized`, or to honestly say none fit:

```bash
python3 -m spend_agent.cli data/sample_transactions.csv --outdir out --llm-fallback
```

This is genuinely optional, in the same sense as `ppp/`: nothing else in the
package imports `llm_classifier.py`, it requires `pip install anthropic` and
an `ANTHROPIC_API_KEY`, and the CLI degrades gracefully (prints a warning,
runs the deterministic pipeline as normal) if either is missing. The base
package's "no third-party dependencies" claim below only applies without this
flag. Every LLM-assisted row is marked in the CSV (`llm_assisted` column) and
gets its stated reasoning logged to `llm_assisted_report.md`, so — consistent
with the auditability goal that made the base classifier rule-based in the
first place — a reviewer can see *why* a non-keyword-matched row landed where
it did instead of just trusting it.

## How it works

- **`spend_agent/ingest.py`** — tolerant CSV parsing; matches header aliases
  (`Vendor`/`Merchant`/`Payee`, `Amount`/`Total`, ...) instead of requiring
  an exact schema, and handles currency formatting (`$1,204.55`, `(50.00)`).
- **`spend_agent/vendor_resolution.py`** — normalizes vendor strings (strips
  store numbers, legal suffixes, punctuation) and clusters aliases that
  share a leading token (e.g. "STAPLES ..."). A small seed alias table
  (`config/vendor_aliases.json`) bridges abbreviations fuzzy matching can't
  reach on its own, like `AWS` → `Amazon Web Services`.
- **`spend_agent/taxonomy.py`** — keyword-based classification against
  `config/taxonomy.json`. Rule-based on purpose: classification decisions
  need to be auditable, and unmatched rows fall into `Uncategorized` for
  manual review rather than being guessed at.
- **`spend_agent/supplier_check.py`** — compares each transaction's resolved
  vendor against `config/preferred_suppliers.json` for its category and
  flags a mismatch as bypassed preferred supplier.
- **`spend_agent/pipeline.py`** / **`spend_agent/report.py`** — orchestrate
  the above and render the reports.

## Dashboard (demo)

`dashboard/spend_ledger_dashboard.html` is a self-contained interactive
dashboard (no server, no external requests — fonts and data are inlined) for
demoing a pipeline run: category breakdown, the vendor-alias merges shown
explicitly (e.g. all 4 Staples aliases collapsing into one card), a
maverick-spend table, and a searchable/filterable/sortable transaction
register. Open it directly in a browser.

Regenerate it for a different transaction file with:

```bash
python3 dashboard/generate_dashboard.py data/sample_transactions.csv \
  --out dashboard/spend_ledger_dashboard.html
```

`dashboard/template.html` is the static shell; `generate_dashboard.py` runs
the real pipeline and substitutes the results in — the numbers on the page
are always a live run, never hand-edited.

## Config

- `config/taxonomy.json` — category name → keyword list.
- `config/preferred_suppliers.json` — category name → preferred supplier
  name. Categories with no entry are never flagged.
- `config/vendor_aliases.json` — known abbreviation → full vendor name,
  consulted before fuzzy matching.
- `config/ppp_taxonomy.json`, `config/ppp_preferred_lenders.json`,
  `config/usaspending_taxonomy.json`, `config/usaspending_preferred_suppliers.json`
  — same shapes as above, for the PPP and USASpending.gov adapters.

## Sample data

`data/sample_transactions.csv` is a deliberately messy 23-row example: mixed
date formats, currency symbols/commas, a blank line, and one vendor (Staples)
appearing under four different raw names. Running the CLI against it
produces the reports checked into behavior by `tests/test_pipeline.py`.

## USASpending.gov (federal contract award data)

`usaspending/` adapts the same pipeline to federal contract award data from
[usaspending.gov](https://www.usaspending.gov/), the official public source
of U.S. government spending: the **recipient** (contractor) is treated as
the "vendor" for alias resolution, and the award's **NAICS description**
and **Product/Service Code (PSC) description** drive classification into
procurement categories via `config/usaspending_taxonomy.json`, since federal
contracts are categorized by PSC/NAICS rather than a free-text memo line.
The bundled sample is scoped to a single awarding agency, NASA, rather than
a mix of agencies — see below.

```bash
python3 usaspending/run_usaspending_agent.py usaspending/data/sample_nasa_contracts.csv \
  --suppliers usaspending/data/sample_preferred_suppliers.json \
  --outdir usaspending/out
```

`spend_agent/usaspending_adapter.py` accepts either shape USASpending.gov
data actually comes in: a **Custom Award Data** bulk CSV download (from
[the download center](https://www.usaspending.gov/download_center/custom-award-data)),
whose columns are snake_case (`recipient_name`, `federal_action_obligation`,
`naics_description`, `product_or_service_code_description`), or a CSV export
of the **Award Search API**'s `spending_by_award` results, whose columns are
Title Case (`Recipient Name`, `Award Amount`, `NAICS Description`). Header
matching is tolerant across both, the same approach `ingest.py` uses for
messy transaction exports.

A second synthetic sample, `usaspending/data/sample_hud_contracts.csv` (with
its own `usaspending/data/sample_hud_preferred_suppliers.json` policy),
scopes the same demo to a different single agency (HUD) to show the pipeline
isn't NASA-specific — same synthetic-data caveat applies. Generate its
dashboard with:

```bash
python3 usaspending/run_usaspending_agent.py usaspending/data/sample_hud_contracts.csv \
  --suppliers usaspending/data/sample_hud_preferred_suppliers.json --outdir usaspending/out
python3 dashboard/generate_dashboard.py usaspending/out/converted_transactions.csv \
  --taxonomy config/usaspending_taxonomy.json \
  --suppliers usaspending/data/sample_hud_preferred_suppliers.json \
  --out dashboard/usaspending_hud_dashboard.html
```

### Sample data is synthetic, not a live pull, and scoped to NASA

This environment's egress policy blocks outbound requests to
`api.usaspending.gov`, so `usaspending/data/sample_nasa_contracts.csv` was
**not** fetched from the live API — it's a hand-built, clearly-labeled
illustrative sample using fictional contractor names (e.g. "Meridian
Defense Systems", "Northgate IT Solutions") built to exercise every feature
of the pipeline: one recipient under 4 raw name variants, ten spend
categories, and two awards routed away from a documented (equally
fictional) preferred-supplier policy. Every row's awarding agency is set to
NASA and the award descriptions are flavored accordingly (spacecraft
sensors, launch vehicle ground systems, center facility maintenance, and
so on) — this is the "just NASA" version of the demo rather than a
mixed-agency one; NAICS/PSC descriptions (the fields that actually drive
classification) are unchanged, so results are identical to the prior
mixed-agency version. None of it should be read as, or confused with, a
real award record — consistent with this repo's stance elsewhere (see the
PPP section below) of never attaching a real-data-shaped claim to an entity
without real data behind it. `spend_agent/usaspending_adapter.py` itself is
written against USASpending.gov's real, documented column schema — including
an `awarding_agency_name`/`Awarding Agency` filter a caller can apply
upstream before conversion — so it works unmodified against an actual bulk
download or API export (e.g. one already filtered to NASA on
usaspending.gov's download center); only the bundled demo file is
synthetic.

As with `ppp/`, no preferred-supplier policy is asserted by default
(`config/usaspending_preferred_suppliers.json` is empty) — asserting one
against real award data without an actual agency policy behind it would
misrepresent the output as a compliance finding.
`usaspending/data/sample_preferred_suppliers.json` is the fictional policy
used only for the sample run above; don't point it at real data.

## PPP loan data (real-world example)

`ppp/` adapts the same pipeline to public SBA PPP loan data as a real-data
example: the **lender** is treated as the "vendor" (so lender name variants
get resolved the same way), and the **NAICS code** drives classification
into industry sectors via `config/ppp_taxonomy.json`.

```bash
python3 ppp/run_ppp_agent.py ppp/data/wyoming_ppp_sample.csv --outdir ppp/out
```

`ppp/data/wyoming_ppp_sample.csv` is a 500-row sample of real Wyoming PPP
loans (April–June 2020) from the SBA's public FOIA release. No
preferred-lender policy is configured (`config/ppp_preferred_lenders.json`
is empty) — asserting one against real named businesses without an actual
policy to check against would misrepresent the output as a compliance
finding. The maverick-spend flag stays available for anyone who supplies a
real policy to check against.

### Risk-indicator scoring (heuristic, not a fraud determination)

`spend_agent/ppp_risk_score.py` scores raw PPP loan records against five
documented public-oversight red flags (round-dollar amounts, missing NAICS
codes, near-$150K-threshold amounts, same-lender/amount/date batches, and
large loans with zero jobs reported). Every indicator is a published
GAO/SBA-OIG screening pattern, not proof of wrongdoing — a loan can trip
several and still be entirely legitimate (the $20,833 amount, for example,
is simply the standard PPP maximum for a self-employed applicant with no
employees, not a red flag on its own). Loans under $150K carry no borrower
name in the public data, so this never identifies or accuses a specific
business — only lender/date/amount/NAICS-level patterns.

Run it against the *full* raw per-state file, not the 500-row sample above —
the near-threshold indicator is only meaningful against the full amount
distribution:

```bash
python3 ppp/run_ppp_risk_score.py path/to/foia_up_to_150k_WY.csv --outdir ppp/out
```

### Statistical anomaly analysis (peer-reviewed methodology, replicated at small scale)

`ppp/run_ppp_anomaly_analysis.py` is a more rigorous alternative to the
heuristic score above: it replicates, at small scale, the peer-group
comparison method of Griffin, Kruger & Mahajan (2023, *Journal of Finance*),
["Did FinTech Lenders Facilitate PPP Fraud?"](https://onlinelibrary.wiley.com/doi/10.1111/jofi.13209),
comparing loan characteristics between fintech/non-bank lenders
(`spend_agent/ppp_lender_type.py`) and traditional banks using actual
statistical tests instead of arbitrary point weights:

- **Amount z-score** — how many standard deviations a loan's amount is from
  the mean for its NAICS industry (peer-group benchmark), compared between
  lender types with Welch's t-test.
- **Salary-cap-implied rate** — the specific Griffin et al. red flag: a loan
  amount that, divided by reported jobs retained, implies (almost) every
  employee earns exactly the PPP $100,000 salary cap — statistically
  improbable for genuine payroll. Compared with a two-proportion z-test.
- **Statistical outlier rate** (`|z| > 2`) and **round-dollar rate**, same test.

`spend_agent/ppp_stats.py` implements Welch's t-test and the two-proportion
z-test in pure Python (no scipy dependency) — the t-distribution p-value
uses a regularized-incomplete-beta continued fraction, verified against
`scipy.stats` to better than 1e-12 absolute error during development (see
`tests/test_ppp_stats.py`).

**On the full Wyoming dataset (11,866 loans, 432 fintech-lender / 11,434
bank), results are mixed** — not a simple confirmation of the "fintech is
riskier" headline: fintech loans skewed *smaller* relative to industry peers
(t = -8.57, p < 0.0001) and had a *lower* statistical-outlier rate (3.2% vs
6.4%, p = 0.0084), while the salary-cap-implied rate was elevated for
fintech loans as the cited study found, but only marginally significant at
this sample size (4.4% vs 2.8%, p = 0.050). That's a legitimate finding in
its own right — a national-level effect need not replicate in one state's
under-$150K loan tier — and a good discussion point on sample size and
external validity for a written report.

```bash
python3 ppp/run_ppp_anomaly_analysis.py path/to/foia_up_to_150k_WY.csv --outdir ppp/out
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

No third-party dependencies — everything runs on the Python 3 standard
library, except the optional `--llm-fallback` flag above, which needs
`pip install anthropic` and an `ANTHROPIC_API_KEY` only if you opt into it.
