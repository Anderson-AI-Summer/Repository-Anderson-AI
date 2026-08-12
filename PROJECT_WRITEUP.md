# Spend Classification Agent — Project Write-Up

## Problem

Given a messy transaction export, produce a system that:

1. classifies each line into a spend taxonomy,
2. recognizes when the same vendor appears under different raw names, and
3. flags purchases in categories with a designated preferred supplier that
   were routed to a different vendor instead ("maverick spend").

## Design principles

- **Auditability over cleverness.** Classification is rule-based
  (`spend_agent/taxonomy.py`) so every decision traces back to a keyword a
  reviewer can check. Rows that match nothing are left `Uncategorized`
  rather than guessed at — a wrong-but-confident category is worse than an
  honest "needs review."
- **Vendor resolution is precision-first.** Two vendor strings are only
  merged if the shorter normalized name is a whole-token prefix of the
  longer one (`spend_agent/vendor_resolution.is_same_vendor`), not on
  looser string similarity. Two failure modes drove this design — see
  *Vendor resolution: two false-merge bugs* below.
- **No unearned claims against real entities.** Everywhere this agent runs
  against real data (the PPP section), it never asserts a finding of
  wrongdoing against a named business, and any heuristic is labeled as a
  heuristic, not a determination.

## Architecture

```
ingest.py          tolerant CSV parsing (header aliases, currency strings)
vendor_resolution.py   normalize + union-find cluster vendor name variants
taxonomy.py         keyword classification against config/taxonomy.json
supplier_check.py   compares resolved vendor to config/preferred_suppliers.json
llm_classifier.py   optional: LLM fallback for rows taxonomy.py leaves Uncategorized
pipeline.py          orchestrates the above
report.py            renders CSV + Markdown reports
cli.py                argparse entry point
```

Run it:

```bash
python3 -m spend_agent.cli data/sample_transactions.csv --outdir out
```

## Vendor resolution: two false-merge bugs

The matching rule went through two iterations, both caught by testing
against real-looking vendor names rather than only the constructed demo
data:

1. **Dell Technologies / Slack Technologies.** An early version clustered
   vendors sharing any token, which merged unrelated companies that happen
   to share a generic trailing word ("Technologies"). Fixed by requiring
   agreement on the *leading* token.
2. **First Interstate Bank / First Republic Bank, Bank of Jackson Hole /
   Bank of America.** Found while testing on real Wyoming PPP lender names:
   leading-token agreement alone still merges unrelated companies that
   share a generic *leading* word — entire industries do this (many banks
   start with "First" or "Bank of"). Fixed by requiring the shorter
   normalized name to be a whole-token *prefix* of the longer one, so
   "Staples" correctly matches "Staples Business Advantage" but "First
   Interstate Bank" does not match "First Republic Bank." Regression tests
   for both bugs live in `tests/test_vendor_resolution.py`.

## Optional LLM fallback (`--llm-fallback`)

The taxonomy classifier's refusal to guess is a feature for auditability,
but it means a fixed keyword list under-serves rows a human would resolve
in seconds — a new vendor, an ambiguous description. `spend_agent/llm_classifier.py`
adds an opt-in step: for rows the keyword classifier leaves `Uncategorized`,
it asks Claude (`claude-opus-5`) to pick a category from the *same*
taxonomy, constrained to a fixed JSON schema so the response is always one
of the known category names (or an honest `Uncategorized`). The model's
stated reasoning is preserved and written to `llm_assisted_report.md`, and
every LLM-assisted row is marked in the CSV output — keeping the same
auditability goal that made the base classifier rule-based in the first
place, instead of trading it away for coverage.

This is deliberately optional and side-effect-free when unused: nothing
else in the package imports the module, it requires `pip install anthropic`
and `ANTHROPIC_API_KEY`, and both `classify_with_llm` and `is_available`
fail soft (return `None` / `False`) rather than raise, so the CLI falls back
to the deterministic pipeline with a printed warning if the SDK or key
isn't present. Tests (`tests/test_llm_classifier.py`) mock the Anthropic
client entirely — no real network calls run in the test suite.

## Real-world example: SBA PPP loan data (`ppp/`)

The same pipeline is adapted to public SBA Paycheck Protection Program loan
data: the **lender** stands in for "vendor" (so lender name variants get
resolved the same way vendor variants do), and the **NAICS industry code**
drives classification (`config/ppp_taxonomy.json`). `ppp/data/wyoming_ppp_sample.csv`
is a 500-row sample of real Wyoming PPP loans (April–June 2020) from the
SBA's public FOIA release; the CLI scripts also accept a path to any state's
full raw CSV, so this generalizes beyond Wyoming without code changes.

No preferred-lender policy is configured
(`config/ppp_preferred_lenders.json` is deliberately empty) — asserting one
against real named businesses with no actual policy to check against would
misrepresent the output as a compliance finding.

### Two analysis modes, and why there are two

- **`ppp_risk_score.py` (heuristic).** Scores loans against five published
  GAO/SBA-OIG red-flag patterns with point weights. Useful for intuition,
  explicitly documented as *not* a fraud determination, but the weights
  are arbitrary and unvalidated — a legitimate loan can trip several flags
  (e.g. the PPP self-employed maximum, $20,833, is a round number by
  construction, not evidence of anything).
- **`ppp_anomaly_analysis.py` (statistical).** Replaces the heuristic with
  actual hypothesis tests, replicating at small scale the peer-group
  comparison method of Griffin, Kruger & Mahajan (2023, *Journal of
  Finance*), ["Did FinTech Lenders Facilitate PPP Fraud?"](https://onlinelibrary.wiley.com/doi/10.1111/jofi.13209) —
  specifically its fintech-vs-bank lender comparison and its
  salary-cap-implied red flag (loan amount ÷ jobs retained implying
  everyone earns exactly the PPP $100,000 cap). Comparisons use Welch's
  t-test (unequal-variance) and a two-proportion z-test, implemented
  dependency-free in `spend_agent/ppp_stats.py` and verified against
  `scipy.stats` to <1e-12 absolute error during development (not shipped as
  a runtime dependency — see `tests/test_ppp_stats.py`).

This second mode is the one worth citing: it swaps an unvalidated
heuristic for a peer-reviewed, reproducible methodology, and it's honest
about the result rather than steering toward a predetermined conclusion.

### Result on the full Wyoming dataset (11,866 loans)

Mixed — not a simple confirmation of the "fintech is riskier" headline:

| Test | Result |
|---|---|
| Amount z-score vs. industry peers (Welch's t) | fintech loans *smaller* relative to peers (t = −8.57, p < 0.0001) |
| Statistical outlier rate, \|z\| > 2 (two-proportion z) | fintech *lower*: 3.2% vs 6.4% (p = 0.0084) |
| Salary-cap-implied rate (two-proportion z) | fintech *elevated*, as the cited study found, but only marginal at this sample size: 4.4% vs 2.8% (p = 0.050) |
| Round-dollar rate (two-proportion z) | see `ppp/out/anomaly_scored_loans.csv` / script console output for the full breakdown |

That mixed result is a legitimate finding, not a null result to explain
away — a national-level effect need not replicate in one state's
under-$150K loan tier, and it's a genuine discussion point about sample
size and external validity.

## Federal contract data: USASpending.gov (`usaspending/`)

A second real-schema adapter targets [usaspending.gov](https://www.usaspending.gov/),
the official public source of U.S. government contract spending. The
**recipient** (contractor) stands in for "vendor," and the award's **NAICS
description** and **Product/Service Code description** — federal contracts
are categorized by PSC/NAICS, not a free-text memo — drive classification
via `config/usaspending_taxonomy.json`. `spend_agent/usaspending_adapter.py`
tolerantly matches both real column shapes USASpending.gov data comes in:
the snake_case "Custom Award Data" bulk CSV download, and the Title Case
columns returned by the Award Search API's `spending_by_award` endpoint.

This adapter was built without a live pull: the execution environment's
egress policy blocks outbound requests to `api.usaspending.gov` (confirmed
via a direct test — the request was rejected by the policy, not by
USASpending.gov itself). Rather than fabricate something that could be
mistaken for a real award record, `usaspending/data/sample_nasa_contracts.csv`
is an explicitly synthetic demo file with fictional contractor names,
scoped to a single awarding agency (NASA) rather than a mixed-agency set,
built to exercise every feature end to end (one recipient under 4 name
variants, ten spend categories, two awards flagged against a fictional
preferred-supplier policy) without attaching invented dollar figures to any
real, named company — the same "no unearned claims against real entities"
principle the PPP section above follows. As with the PPP adapter, no real
preferred-supplier policy is asserted by default
(`config/usaspending_preferred_suppliers.json` is empty); the demo's policy
lives separately in `usaspending/data/sample_preferred_suppliers.json` and
is documented as fictional. The adapter code itself targets USASpending's
real documented schema, so it is expected to work unmodified against an
actual bulk download or API export — only the bundled sample is synthetic.

## Limitations

- The keyword taxonomy is only as good as its keyword list; category
  boundaries are hand-authored, not learned.
- `--llm-fallback` introduces model nondeterminism on the rows it touches
  — it's marked and logged for that reason, not silently blended into the
  deterministic output.
- The PPP risk-score module is explicitly a heuristic; only the anomaly
  analysis module makes a methodologically grounded comparison, and even
  that is a small-scale, single-state replication of a national study —
  not a claim that any individual Wyoming loan is fraudulent.
- Vendor/lender resolution is name-based; it cannot detect shell-company
  relationships or common ownership that don't share a name prefix.
- The USASpending.gov adapter has not been run against real award data in
  this environment (network access to the API is blocked here); it has
  only been validated against the documented schema and the synthetic
  sample.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

54 tests, all offline/deterministic (the LLM fallback tests mock the
Anthropic client; nothing in the suite makes a network call).
