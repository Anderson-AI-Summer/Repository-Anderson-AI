# Final Checklist

## Setup

- [ ] `cd "Lindsay Work"`
- [ ] `python3 -m venv .venv && source .venv/bin/activate`
- [ ] `pip install -r requirements.txt`
- [ ] `python -m src.cli setup` -- confirms dependencies installed and reports
      whether `ANTHROPIC_API_KEY` is configured (fine either way)

## Pipeline

- [ ] `python -m src.cli sample` succeeds and writes
      `outputs/nasa_procurement_dashboard.html`
- [ ] `python -m pytest` -- all tests pass (54 as of the last full run)
- [ ] `python -m src.cli refresh --start 2019-10-01` for a larger/full pull
      (omit `--limit` for a genuinely uncapped run; expect it to take a
      while -- award-detail lookups are the bottleneck)
- [ ] `python -m src.cli build` rebuilds the dashboard from
      `data/processed/enriched_transactions_latest.csv` with **zero**
      network calls -- confirms offline rebuild works

## Fallback / reliability

- [ ] With no `ANTHROPIC_API_KEY` set, confirm the dashboard header shows
      `DETERMINISTIC_FALLBACK` (or `CACHED_AGENT` if agent_cache/ already has
      entries from a prior live run) -- never a crash, never a fake live claim
- [ ] Disconnect from the internet and open
      `outputs/nasa_procurement_dashboard_presentation.html` directly --
      confirm it renders and every tab/control works with zero network
      requests (check the browser's network panel)
- [ ] Confirm `data/samples/nasa_sample_transactions_clean.csv` exists and
      `load_offline_sample()` works standalone (see README "Offline sample")

## Data integrity

- [ ] Transaction Explorer contains real, non-placeholder NASA transactions
- [ ] At least one `DEOBLIGATION` row is visible with an intact **negative**
      signed amount (never zeroed or made positive)
- [ ] Refresh manifest (`data/processed/refresh_manifest_latest.json`)
      `validation_results.assistance_award_leak_errors` is empty --
      confirms no grant/loan/assistance awards leaked into the dataset
- [ ] Dashboard totals reconcile against `data/processed/enriched_transactions_latest.csv`
      (the `expected_transaction_count` check in `src/dashboard/validate.py`
      runs automatically on every generation)

## Secrets

- [ ] `.env` is not committed (`git status` / `.gitignore` confirms)
- [ ] `git grep` for `sk-ant-` / `ANTHROPIC_API_KEY=` across tracked files
      returns nothing but `.env.example`'s placeholder
- [ ] No secret appears in `outputs/*.html`, `data/cache/`, or any committed
      file (`src/dashboard/generate.py` refuses to write HTML containing a
      secret-shaped string; `tests/test_dashboard.py` covers this)

## GitHub

- [ ] `git status` reviewed before every commit -- only intended files staged
- [ ] Commits are small and scoped to one milestone each
- [ ] No force-push, no history rewrite
- [ ] Remote and branch verified before any push (see completion report for
      the exact remote/branch used, or the exact command to run manually if
      it couldn't be verified safely)

## Presentation

- [ ] `outputs/nasa_procurement_dashboard_presentation.html` exists and is a
      frozen copy that does not depend on any live API call
- [ ] `DEMO_SCRIPT.md` walks all 5 tabs within 5-7 minutes
- [ ] `PROJECT_SUMMARY.md` explains the architecture, three agents,
      deterministic calculations, and negative-obligation handling
