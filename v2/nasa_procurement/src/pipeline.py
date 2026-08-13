"""End-to-end pipeline orchestration: ingest -> clean -> enrich -> analytics
-> insights -> dashboard. Shared by the `sample`, `refresh`, and `rebuild`
CLI commands.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import time
import uuid
from pathlib import Path

import pandas as pd

from src.agents.base import AgentRunStats
from src.agents.insights_agent import generate_insights
from src.analytics import compute_analytics
from src.config import (
    DASHBOARD_PATH,
    FY2020_START,
    NASA_AGENCY_NAME,
    PROCESSED_DIR,
)
from src.dashboard.data_prep import build_payload
from src.dashboard.generate import render_dashboard
from src.dashboard.validate import validate_dashboard_html
from src.clean import deduplicate as _dedupe_clean
from src.enrich import enrich_transactions
from src.fiscal import federal_fiscal_year, fiscal_year_bounds
from src.ingest import fetch_from_api, load_offline_sample
from src.schema import CleanTransaction, EnrichedTransaction, RefreshManifest

logger = logging.getLogger("pipeline")

CLEAN_LATEST = PROCESSED_DIR / "clean_transactions_latest.csv"
ENRICHED_LATEST = PROCESSED_DIR / "enriched_transactions_latest.csv"
MANIFEST_LATEST = PROCESSED_DIR / "refresh_manifest_latest.json"
STANDOUTS_SNAPSHOT = PROCESSED_DIR / "standouts_snapshot.json"

_SNAPSHOT_LIST_KEYS = {
    "standout_suppliers": "supplier",
    "standout_awards": "award_id",
    "consolidation_opportunities": "category",
    "duplicate_purchase_candidates": "pair_id",
}


def _load_snapshot() -> dict:
    """Empty snapshot (nothing marked new) if this is the first run ever, or
    the file is missing/unreadable -- fails soft, never blocks a refresh."""
    if not STANDOUTS_SNAPSHOT.exists():
        return {}
    try:
        return json.loads(STANDOUTS_SNAPSHOT.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _mark_new_since_last_run(payload: dict) -> bool:
    """Tags each standout/opportunity/candidate item with is_new: True if it
    was not present in the previous run's snapshot -- the "autonomous
    monitoring" angle from the professor's review: a static one-shot report
    re-surfaces the same handful of items every time, so this distinguishes
    "still true" from "just appeared." Returns whether a previous snapshot
    existed at all (the UI treats "first run" differently from "nothing new").
    """
    previous = _load_snapshot()
    had_previous = bool(previous)
    for list_key, id_field in _SNAPSHOT_LIST_KEYS.items():
        previous_ids = set(previous.get(list_key, []))
        for item in payload.get(list_key, []):
            item["is_new"] = had_previous and item[id_field] not in previous_ids
    return had_previous


def _save_snapshot(payload: dict) -> None:
    snapshot = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    for list_key, id_field in _SNAPSHOT_LIST_KEYS.items():
        snapshot[list_key] = [item[id_field] for item in payload.get(list_key, [])]
    STANDOUTS_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    STANDOUTS_SNAPSHOT.write_text(json.dumps(snapshot, indent=2))


def _save_processed(clean: list[CleanTransaction], enriched: list[EnrichedTransaction]) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    clean_df = pd.DataFrame([c.model_dump(mode="json") for c in clean])
    clean_df.to_csv(CLEAN_LATEST, index=False)
    clean_df.to_csv(PROCESSED_DIR / f"clean_transactions_{ts}.csv", index=False)

    enriched_df = pd.DataFrame([e.model_dump(mode="json") for e in enriched])
    enriched_df.to_csv(ENRICHED_LATEST, index=False)
    enriched_df.to_csv(PROCESSED_DIR / f"enriched_transactions_{ts}.csv", index=False)


def _load_processed_enriched() -> list[EnrichedTransaction]:
    if not ENRICHED_LATEST.exists():
        raise FileNotFoundError(
            f"No processed dataset found at {ENRICHED_LATEST}. Run 'sample' or 'refresh' first."
        )
    from src.csv_io import coerce_record, string_field_names

    df = pd.read_csv(ENRICHED_LATEST)
    string_fields = string_field_names(EnrichedTransaction)
    rows = []
    for _, r in df.iterrows():
        record = coerce_record(r.to_dict(), string_fields)
        for list_field in ("opportunity_flags", "data_quality_flags"):
            v = record.get(list_field)
            if isinstance(v, str):
                record[list_field] = json.loads(v.replace("'", '"')) if v.startswith("[") else ([] if not v else [v])
            elif v is None:
                record[list_field] = []
        rows.append(EnrichedTransaction.model_validate(record))
    return rows


FISCAL_YEAR_RETRY_ATTEMPTS = 3
FISCAL_YEAR_RETRY_PAUSE_SECONDS = 15


def _fetch_spread_across_fiscal_years(
    start_date: str, end_date: str, max_records: int | None, max_workers: int, fetch_award_details: bool = True
) -> tuple[list[CleanTransaction], dict]:
    """Pulls from the official USAspending API only, one fetch_from_api call
    per fiscal year in [start_date, end_date] -- always, whether or not
    max_records is set. This does two things:

    1. When max_records is set, the cap is spread evenly across fiscal years
       so a time-bounded refresh still yields genuine multi-year coverage --
       sorting by most-recent action date with a single flat cap would
       otherwise only capture the last few months.
    2. Each fiscal year is isolated: a transient failure part-way through
       one year's pagination (observed in practice against the real
       USAspending API at this volume) is retried up to
       FISCAL_YEAR_RETRY_ATTEMPTS times, and if it still fails, that year is
       skipped with a recorded warning rather than discarding every other
       fiscal year's already-successful data. Award-detail lookups are also
       disk-cached per award, so re-running after a partial failure does not
       re-fetch work already done.
    """
    start = dt.date.fromisoformat(start_date)
    end = dt.date.fromisoformat(end_date)
    fiscal_years = list(range(federal_fiscal_year(start), federal_fiscal_year(end) + 1))
    per_year_cap = None if max_records is None else max(1, max_records // len(fiscal_years))

    clean: list[CleanTransaction] = []
    row_counts: dict = {}
    assistance_errors: list[str] = []
    failed_fiscal_years: list[dict] = []

    for fy in fiscal_years:
        fy_start, fy_end = fiscal_year_bounds(fy)
        window_start = max(fy_start, start).isoformat()
        window_end = min(fy_end, end).isoformat()
        if window_start > window_end:
            continue

        last_exc: Exception | None = None
        for attempt in range(1, FISCAL_YEAR_RETRY_ATTEMPTS + 1):
            try:
                fy_clean, fy_manifest = fetch_from_api(
                    window_start, window_end, per_year_cap, fetch_award_details=fetch_award_details, max_workers=max_workers
                )
                clean.extend(fy_clean)
                for k, v in fy_manifest["row_counts"].items():
                    row_counts[k] = row_counts.get(k, 0) + v
                assistance_errors.extend(fy_manifest["validation_results"]["assistance_award_leak_errors"])
                last_exc = None
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "FY%d fetch failed (attempt %d/%d): %s", fy, attempt, FISCAL_YEAR_RETRY_ATTEMPTS, exc
                )
                if attempt < FISCAL_YEAR_RETRY_ATTEMPTS:
                    time.sleep(FISCAL_YEAR_RETRY_PAUSE_SECONDS)

        if last_exc is not None:
            logger.error("FY%d permanently failed after %d attempts; skipping this year, keeping other years' data.", fy, FISCAL_YEAR_RETRY_ATTEMPTS)
            failed_fiscal_years.append({"fiscal_year": fy, "error": str(last_exc)})

    if not clean and failed_fiscal_years:
        raise RuntimeError(f"Every fiscal year failed: {failed_fiscal_years}")

    clean, cross_year_dupes = _dedupe_clean(clean)
    row_counts["duplicate_rows_removed_cross_fiscal_year"] = cross_year_dupes
    manifest = {
        "source": "usaspending_api",
        "query_parameters": {
            "awarding_agency": NASA_AGENCY_NAME,
            "start_date": start_date,
            "end_date": end_date,
            "max_records_total": max_records,
            "per_fiscal_year_cap": per_year_cap,
            "fiscal_years_covered": fiscal_years,
            "fiscal_years_failed": failed_fiscal_years,
            "award_detail_enrichment_requested": fetch_award_details,
        },
        "row_counts": row_counts,
        "validation_results": {"assistance_award_leak_errors": assistance_errors, "passed": len(assistance_errors) == 0},
    }
    return clean, manifest


def run_pipeline(
    mode: str,
    start_date: str | None = None,
    end_date: str | None = None,
    max_records: int | None = None,
    offline: bool = False,
    max_workers: int = 8,
    fetch_award_details: bool = True,
) -> dict:
    """mode: 'sample' | 'refresh' | 'rebuild'. Returns a result summary dict.

    The only ingestion source for 'sample' and 'refresh' is the official
    USAspending API. Any NASA CSV already present in the repository (see
    src.ingest.fetch_from_repo_csv, data/samples/nasa_sample_transactions_clean.csv)
    is supported only as an optional sample/fallback input -- e.g. when the
    live API is unreachable -- and is never blended into or used to replace
    the required API-sourced refresh.
    """
    run_id = uuid.uuid4().hex[:12]
    today = dt.date.today()
    warnings: list[str] = []
    errors: list[str] = []

    if mode == "rebuild":
        enriched = _load_processed_enriched()
        manifest = {"source": "cached_processed_dataset", "row_counts": {"enriched_transactions": len(enriched)}}
        stats = AgentRunStats()
        processing_mode = "CACHED_AGENT" if any(
            (Path("data/cache/agent_cache")).exists() for _ in [0]
        ) else "DETERMINISTIC_FALLBACK"
    else:
        start_date = start_date or FY2020_START
        end_date = end_date or today.isoformat()
        stats = AgentRunStats()
        try:
            if mode == "refresh":
                clean, manifest = _fetch_spread_across_fiscal_years(
                    start_date, end_date, max_records, max_workers, fetch_award_details=fetch_award_details
                )
            else:
                clean, manifest = fetch_from_api(
                    start_date, end_date, max_records, fetch_award_details=fetch_award_details, max_workers=max_workers
                )
            if not clean:
                warnings.append("API returned zero usable transactions for the requested window")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Live API ingestion failed (%s); falling back to offline sample", exc)
            errors.append(f"live_ingest_failed: {exc}")
            clean, manifest = load_offline_sample()

        enriched = enrich_transactions(clean, stats)
        _save_processed(clean, enriched)
        processing_mode = stats.overall_mode().value

    analytics = compute_analytics(enriched, today=today)
    insights = generate_insights(analytics, stats)
    insights_dicts = [f.model_dump() for f in insights.findings]

    payload = build_payload(enriched, analytics, insights_dicts, manifest, processing_mode, today=today)
    payload["meta"]["has_previous_snapshot"] = _mark_new_since_last_run(payload)

    refresh_manifest = RefreshManifest(
        run_id=run_id,
        retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        source=manifest.get("source", "unknown"),
        query_parameters=manifest.get("query_parameters", {}),
        processing_mode=processing_mode,
        row_counts={**manifest.get("row_counts", {}), "enriched_transactions": len(enriched)},
        validation_results=manifest.get("validation_results", {"assistance_award_leak_errors": [], "passed": True}),
        warnings=warnings,
        errors=errors,
    )
    MANIFEST_LATEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_LATEST.write_text(refresh_manifest.model_dump_json(indent=2))

    tmp_out = DASHBOARD_PATH.with_name("nasa_procurement_dashboard.candidate.html")
    render_dashboard(payload, tmp_out)
    html_errors = validate_dashboard_html(tmp_out, expected_transaction_count=len(enriched))

    if html_errors:
        logger.error("Generated dashboard failed validation: %s", html_errors)
        if tmp_out.exists():
            tmp_out.unlink()
        return {
            "run_id": run_id, "status": "failed_validation", "errors": html_errors,
            "kept_previous_dashboard": DASHBOARD_PATH.exists(),
            "row_counts": refresh_manifest.row_counts, "processing_mode": processing_mode,
        }

    tmp_out.replace(DASHBOARD_PATH)
    _save_snapshot(payload)

    return {
        "run_id": run_id, "status": "ok", "dashboard_path": str(DASHBOARD_PATH),
        "row_counts": refresh_manifest.row_counts, "processing_mode": processing_mode,
        "manifest_path": str(MANIFEST_LATEST), "warnings": warnings, "errors": errors,
        "agent_stats": stats.as_dict(),
    }
