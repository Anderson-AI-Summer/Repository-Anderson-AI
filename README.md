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
