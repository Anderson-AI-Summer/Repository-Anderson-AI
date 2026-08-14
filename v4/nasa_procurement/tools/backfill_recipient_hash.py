"""Backfills recipient_hash onto the processed dataset so the "View on
USAspending.gov" buttons can deep-link straight to the real award/recipient
page instead of a keyword search.

Why this exists: the standout-supplier and standout-award cards linked out
via a plain `?keyword=` search, which the live usaspending.gov search page
does not read from the URL -- the button opened a generic search screen, not
the entity the user was looking at. USAspending's own award-detail endpoint
(the same one this pipeline already calls for competition data) returns two
identifiers built exactly for direct linking:

  - generated_unique_award_id -> https://www.usaspending.gov/award/<id>
  - recipient.recipient_hash  -> https://www.usaspending.gov/recipient/<hash>/latest

`generated_award_id` is already a column in the enriched CSV (100% coverage,
captured straight from the transaction-search row, no extra fetch needed).
`recipient_hash` only comes from the award-detail endpoint, which the
multi-year embedded pull was run without (`--skip-award-details`, for
speed) and which the earlier competition-data backfill only ran for
sub-threshold awards. This script fills the gap: reuses
data/cache/award_details/ where already populated (83.5% of awards, from
that earlier backfill), fetches the remainder, and writes recipient_hash
onto the processed CSV as a plain column patch -- no re-run of ingestion or
AI classification, so no analytical number changes.

Usage:  python3 tools/backfill_recipient_hash.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import PROCESSED_DIR, CACHE_DIR  # noqa: E402
from src.usaspending_client import USASpendingError, fetch_award_detail  # noqa: E402

ENRICHED_LATEST = PROCESSED_DIR / "enriched_transactions_latest.csv"
AWARD_DETAIL_CACHE_DIR = CACHE_DIR / "award_details"
MAX_WORKERS = 24


def _cached_recipient_hash(generated_id: str) -> str | None:
    p = AWARD_DETAIL_CACHE_DIR / f"{generated_id}.json"
    if p.exists():
        try:
            detail = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            detail = None
    else:
        try:
            detail = fetch_award_detail(generated_id)
        except USASpendingError:
            detail = None
        if detail is not None:
            AWARD_DETAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(detail, default=str))
    if not detail:
        return None
    return (detail.get("recipient") or {}).get("recipient_hash")


def main() -> None:
    print(f"Reading {ENRICHED_LATEST} ...")
    df = pd.read_csv(ENRICHED_LATEST)
    unique_ids = sorted(df["generated_award_id"].dropna().unique())
    print(f"{len(unique_ids):,} unique awards; {sum((AWARD_DETAIL_CACHE_DIR / f'{i}.json').exists() for i in unique_ids):,} already cached")

    hashes: dict[str, str | None] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_cached_recipient_hash, gid): gid for gid in unique_ids}
        done = 0
        for fut in as_completed(futures):
            gid = futures[fut]
            hashes[gid] = fut.result()
            done += 1
            if done % 1000 == 0:
                print(f"  {done:,}/{len(unique_ids):,}")

    resolved = sum(1 for v in hashes.values() if v)
    print(f"recipient_hash resolved for {resolved:,}/{len(unique_ids):,} awards ({resolved / len(unique_ids):.1%})")

    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = PROCESSED_DIR / f"enriched_transactions_pre_recipient_hash_{ts}.csv"
    df.to_csv(backup, index=False)
    print(f"backup written to {backup}")

    df["recipient_hash"] = df["generated_award_id"].map(hashes)
    df.to_csv(ENRICHED_LATEST, index=False)
    print(f"wrote {ENRICHED_LATEST} with recipient_hash column ({df['recipient_hash'].notna().sum():,}/{len(df):,} rows resolved)")


if __name__ == "__main__":
    main()
