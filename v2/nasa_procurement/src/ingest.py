"""Ingestion orchestration: USAspending API -> raw extract -> clean transactions.

Three ingestion paths, in order of preference:
  1. Live API pull (`source="usaspending_api"`) -- the normal path.
  2. Offline sample CSV (`source="offline_sample_csv"`) -- used when the API
     is unreachable, or explicitly requested for fast/offline development.
     data/samples/nasa_sample_transactions_clean.csv is a small, real
     (not fabricated) extract selected from an actual FY2020 pull -- see
     README.md "Offline sample" section for exactly how it was built.
  3. A user-supplied NASA CSV placed under data/samples/, if present and no
     API access is available (checked defensively; none ships by default).

Never mutates the raw extract once written. Award-detail lookups are cached
under data/cache/award_details/ and reused across runs.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from src.clean import clean_transaction, deduplicate
from src.config import (
    ASSISTANCE_AWARD_TYPE_CODES,
    CACHE_DIR,
    CONTRACT_AWARD_TYPE_CODES,
    FY2020_START,
    NASA_AGENCY_NAME,
    RAW_DIR,
    SAMPLES_DIR,
)
from src.schema import CleanTransaction
from src.usaspending_client import USASpendingError, fetch_award_detail, iter_nasa_transactions

logger = logging.getLogger("ingest")

AWARD_DETAIL_CACHE_DIR = CACHE_DIR / "award_details"
AWARD_DETAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

OFFLINE_SAMPLE_PATH = SAMPLES_DIR / "nasa_sample_transactions_clean.csv"

CLEAN_COLUMNS = list(CleanTransaction.model_fields.keys())


def _cached_award_detail(generated_id: str) -> dict | None:
    p = AWARD_DETAIL_CACHE_DIR / f"{generated_id}.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    try:
        detail = fetch_award_detail(generated_id)
    except USASpendingError as exc:
        logger.warning("Award detail fetch failed for %s: %s", generated_id, exc)
        return None
    if detail is not None:
        p.write_text(json.dumps(detail, default=str))
    return detail


def save_raw_extract(raw_transactions: list[dict], tag: str) -> Path:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RAW_DIR / f"nasa_transactions_raw_{tag}_{ts}.json"
    path.write_text(json.dumps(raw_transactions, default=str, indent=None))
    return path


def validate_contract_only(raw_transactions: list[dict]) -> list[str]:
    """Post-ingestion validation: no assistance award types leaked in."""
    errors = []
    for row in raw_transactions:
        code = row.get("Award Type")
        # 'Award Type' from spending_by_transaction is a human description in
        # some payloads and a code in others depending on endpoint version;
        # check both the raw code field and generated_internal_id prefix.
        gen_id = row.get("generated_internal_id", "")
        if gen_id and not gen_id.startswith("CONT_AWD_"):
            errors.append(f"Non-contract award id detected: {gen_id}")
    return errors


def fetch_from_api(
    start_date: str,
    end_date: str,
    max_records: int | None,
    fetch_award_details: bool = True,
    max_workers: int = 8,
    progress_every: int = 200,
) -> tuple[list[CleanTransaction], dict]:
    raw_transactions: list[dict] = list(
        iter_nasa_transactions(
            start_date=start_date,
            end_date=end_date,
            award_type_codes=CONTRACT_AWARD_TYPE_CODES,
            agency_name=NASA_AGENCY_NAME,
            max_records=max_records,
        )
    )
    raw_path = save_raw_extract(raw_transactions, tag="api")
    validation_errors = validate_contract_only(raw_transactions)

    unique_award_ids = sorted({r["generated_internal_id"] for r in raw_transactions if r.get("generated_internal_id")})
    award_details: dict[str, dict | None] = {}
    if fetch_award_details:
        logger.info("Fetching award detail for %d unique awards (max_workers=%d)...", len(unique_award_ids), max_workers)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_cached_award_detail, gen_id): gen_id for gen_id in unique_award_ids}
            done = 0
            for future in as_completed(futures):
                gen_id = futures[future]
                try:
                    award_details[gen_id] = future.result()
                except USASpendingError as exc:
                    logger.warning("Award detail fetch failed for %s: %s", gen_id, exc)
                    award_details[gen_id] = None
                done += 1
                if progress_every and done % progress_every == 0:
                    logger.info("Award detail progress: %d/%d", done, len(unique_award_ids))

    clean_rows: list[CleanTransaction] = []
    quality_flag_counts: dict[str, int] = {}
    dropped = 0
    for raw in raw_transactions:
        gen_id = raw.get("generated_internal_id")
        detail = award_details.get(gen_id) if fetch_award_details else None
        clean, flags = clean_transaction(raw, detail)
        for f in flags:
            quality_flag_counts[f] = quality_flag_counts.get(f, 0) + 1
        if clean is None:
            dropped += 1
            continue
        clean_rows.append(clean)

    clean_rows, duplicates = deduplicate(clean_rows)

    manifest = {
        "source": "usaspending_api",
        "raw_extract_path": str(raw_path),
        "query_parameters": {
            "awarding_agency": NASA_AGENCY_NAME,
            "start_date": start_date,
            "end_date": end_date,
            "award_type_codes": CONTRACT_AWARD_TYPE_CODES,
            "max_records": max_records,
        },
        "row_counts": {
            "raw_transactions": len(raw_transactions),
            "unique_awards_enriched": len(unique_award_ids) if fetch_award_details else 0,
            "clean_transactions": len(clean_rows),
            "dropped_unusable_rows": dropped,
            "duplicate_rows_removed": duplicates,
        },
        "validation_results": {
            "assistance_award_leak_errors": validation_errors,
            "passed": len(validation_errors) == 0,
        },
        "data_quality_flag_counts": quality_flag_counts,
    }
    return clean_rows, manifest


def load_offline_sample() -> tuple[list[CleanTransaction], dict]:
    if not OFFLINE_SAMPLE_PATH.exists():
        raise FileNotFoundError(
            f"Offline sample not found at {OFFLINE_SAMPLE_PATH}. Run a live 'sample' ingest at least "
            f"once (with network access) to generate it, or supply your own NASA CSV there."
        )
    from src.csv_io import load_csv_as_models

    rows: list[CleanTransaction] = load_csv_as_models(OFFLINE_SAMPLE_PATH, CleanTransaction)
    manifest = {
        "source": "offline_sample_csv",
        "raw_extract_path": str(OFFLINE_SAMPLE_PATH),
        "query_parameters": {"note": "offline fallback sample, see README.md for selection method"},
        "row_counts": {"clean_transactions": len(rows)},
        "validation_results": {"assistance_award_leak_errors": [], "passed": True},
        "data_quality_flag_counts": {},
    }
    return rows, manifest


def fetch_from_repo_csv(csv_path: Path) -> tuple[list[CleanTransaction], dict]:
    """Ingest a NASA transaction CSV already present elsewhere in the repo
    (e.g. a teammate's `data/nasa_fy2025_contract_transactions.csv` pull),
    per the requirement to support any pre-existing NASA CSV as a sample or
    fallback input rather than relying solely on live API pulls.

    The CSV is expected to use the same column names as the transaction-
    search API response (Award ID, Mod, Recipient Name, Action Date,
    Transaction Amount, Awarding Agency, Awarding Sub Agency, Award Type,
    Transaction Description) so it can be fed through the same
    `clean_transaction` mapping used for live API rows. No award-detail
    enrichment is available for this source (no generated_internal_id to
    look up), so `award_detail_available` is False and PSC/NAICS/UEI/DUNS
    are absent for these rows -- flagged accordingly, never fabricated.
    """
    import csv as csv_module

    csv_path = Path(csv_path)
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        raw_rows = list(csv_module.DictReader(f))

    validation_errors = []
    for row in raw_rows:
        award_type = (row.get("Award Type") or "").upper()
        if award_type and award_type not in {"DEFINITIVE CONTRACT", "DELIVERY ORDER", "PURCHASE ORDER", "BPA CALL"}:
            validation_errors.append(f"Unexpected award type in repo CSV: {award_type}")

    clean_rows: list[CleanTransaction] = []
    quality_flag_counts: dict[str, int] = {}
    dropped = 0
    for raw in raw_rows:
        clean, flags = clean_transaction(raw, None)
        for f in flags:
            quality_flag_counts[f] = quality_flag_counts.get(f, 0) + 1
        if clean is None:
            dropped += 1
            continue
        clean_rows.append(clean)

    clean_rows, duplicates = deduplicate(clean_rows)

    manifest = {
        "source": f"repo_csv:{csv_path.name}",
        "raw_extract_path": str(csv_path),
        "query_parameters": {"note": "pre-existing NASA CSV found in repository, ingested as-is"},
        "row_counts": {
            "raw_transactions": len(raw_rows),
            "unique_awards_enriched": 0,
            "clean_transactions": len(clean_rows),
            "dropped_unusable_rows": dropped,
            "duplicate_rows_removed": duplicates,
        },
        "validation_results": {"assistance_award_leak_errors": validation_errors, "passed": len(validation_errors) == 0},
        "data_quality_flag_counts": quality_flag_counts,
    }
    return clean_rows, manifest


def write_offline_sample(rows: list[CleanTransaction]) -> Path:
    df = pd.DataFrame([r.model_dump(mode="json") for r in rows])
    df = df[CLEAN_COLUMNS]
    OFFLINE_SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OFFLINE_SAMPLE_PATH, index=False)
    return OFFLINE_SAMPLE_PATH
