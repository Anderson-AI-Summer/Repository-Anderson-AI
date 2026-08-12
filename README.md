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

## Config

- `config/taxonomy.json` — category name → keyword list.
- `config/preferred_suppliers.json` — category name → preferred supplier
  name. Categories with no entry are never flagged.
- `config/vendor_aliases.json` — known abbreviation → full vendor name,
  consulted before fuzzy matching.

## Sample data

`data/sample_transactions.csv` is a deliberately messy 23-row example: mixed
date formats, currency symbols/commas, a blank line, and one vendor (Staples)
appearing under four different raw names. Running the CLI against it
produces the reports checked into behavior by `tests/test_pipeline.py`.

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

## Tests

```bash
python3 -m unittest discover -s tests -v
```

No third-party dependencies — everything runs on the Python 3 standard
library.
