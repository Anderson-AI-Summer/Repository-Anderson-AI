# Repository-Anderson-AI

Group project repo for the UCLA August Block 2026 assignment: an agent
that takes a messy transaction file, classifies each line into a spend
taxonomy, identifies the same vendor appearing under different names, and
flags purchases that bypassed the preferred supplier (usaspending.gov).

## Versioning convention

Each milestone lives in its own top-level folder — `v1/`, `v2/`, `v3/`, ...
Every folder is a complete, runnable copy of the project at that point, so
older versions stay intact and comparable instead of being overwritten.

- **`v1/`** — first version. Base spend-classification engine (ingest,
  vendor resolution, taxonomy, preferred-supplier check), the SBA PPP
  real-data example, optional LLM fallback classifier, and the demo
  dashboard. See `v1/README.md` for usage and `v1/PROJECT_WRITEUP.md` for
  the design write-up.
- **`v2/`** — second version. Consolidates everyone's work from the second
  day into one place: the general engine gained a second USASpending.gov
  demo scoped to HUD and a multi-dataset comparison dashboard, plus a new
  flagship implementation at `v2/nasa_procurement/` — a live USASpending.gov
  API pipeline with UEI/DUNS supplier resolution, a three-agent workflow,
  and obligation-aware analytics, built independently by Lindsay. See
  `v2/README.md` for the two-tier layout and a real NASA FY2020–2026 dataset
  ($1.44B, 2,770 transactions) already rendered in
  `v2/nasa_procurement/outputs/`.
- **`v3/`** — third version. Copies `v2/` forward and adds a second, always-
  current mode to `v3/nasa_procurement/`: `outputs/nasa_live_dashboard.html`
  (built independently by Harrison) queries `api.usaspending.gov` directly
  from the browser for any fiscal year (FY2008–present), no server or stored
  data required. It's cross-linked with the flagship analysis dashboard
  ("🛰 Live Lookup" / "← Deep Analysis Dashboard") but deliberately kept as a
  separate page rather than merged into one: the flagship dashboard's
  supplier-resolution, classification, and standout/consolidation/duplicate
  signals are precomputed by the Python pipeline and can't be reproduced
  live in the browser, so the live page shows raw USAspending figures only
  and says so. See `v3/nasa_procurement/README.md` for the two-mode
  architecture.

### Starting the next version

When the team is ready to build on top of `v1` (or whatever the latest
version is):

1. Copy the latest version folder to a new one, e.g.:
   ```bash
   cp -r v1 v2
   ```
2. Do your work inside the new folder (`v2/`).
3. Commit and push. Leave the previous version folder untouched so we can
   always diff or fall back to it.
4. Update this README's list above with a one-line summary of what changed
   in the new version.

Each of the 5 of us can branch off the latest version folder for our own
feature work and merge back in — just don't edit an older version folder
once a newer one exists off of it.
