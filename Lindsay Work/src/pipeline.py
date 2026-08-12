"""End-to-end pipeline orchestration: ingest -> clean -> enrich -> analytics
-> insights -> dashboard. Shared by the `sample`, `refresh`, and `rebuild`
CLI commands.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
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
from src.ingest import fetch_from_api, load_offline_sample
from src.schema import CleanTransaction, EnrichedTransaction, RefreshManifest

logger = logging.getLogger("pipeline")

CLEAN_LATEST = PROCESSED_DIR / "clean_transactions_latest.csv"
ENRICHED_LATEST = PROCESSED_DIR / "enriched_transactions_latest.csv"
MANIFEST_LATEST = PROCESSED_DIR / "refresh_manifest_latest.json"


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


def run_pipeline(
    mode: str,
    start_date: str | None = None,
    end_date: str | None = None,
    max_records: int | None = None,
    offline: bool = False,
    max_workers: int = 8,
    extra_csv_paths: list[Path] | None = None,
) -> dict:
    """mode: 'sample' | 'refresh' | 'rebuild'. Returns a result summary dict.

    extra_csv_paths: additional pre-existing NASA CSVs (e.g. a teammate's
    repo-committed extract) to merge in and deduplicate against the live
    API pull -- used to build the largest reliable combined refresh without
    depending entirely on live API throughput.
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
            clean, manifest = fetch_from_api(start_date, end_date, max_records, max_workers=max_workers)
            if not clean:
                warnings.append("API returned zero usable transactions for the requested window")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Live API ingestion failed (%s); falling back to offline sample", exc)
            errors.append(f"live_ingest_failed: {exc}")
            clean, manifest = load_offline_sample()

        if extra_csv_paths:
            from src.ingest import fetch_from_repo_csv

            combined_sources = [manifest.get("source", "usaspending_api")]
            combined_row_counts = dict(manifest.get("row_counts", {}))
            for csv_path in extra_csv_paths:
                extra_clean, extra_manifest = fetch_from_repo_csv(csv_path)
                clean = clean + extra_clean
                combined_sources.append(extra_manifest["source"])
                for k, v in extra_manifest["row_counts"].items():
                    combined_row_counts[k] = combined_row_counts.get(k, 0) + v
                warnings.extend(extra_manifest["validation_results"].get("assistance_award_leak_errors", []))
            clean, extra_duplicates = _dedupe_clean(clean)
            combined_row_counts["duplicate_rows_removed_across_sources"] = extra_duplicates
            manifest = {**manifest, "source": " + ".join(combined_sources), "row_counts": combined_row_counts}

        enriched = enrich_transactions(clean, stats)
        _save_processed(clean, enriched)
        processing_mode = stats.overall_mode().value

    analytics = compute_analytics(enriched, today=today)
    insights = generate_insights(analytics, stats)
    insights_dicts = [f.model_dump() for f in insights.findings]

    payload = build_payload(enriched, analytics, insights_dicts, manifest, processing_mode, today=today)

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

    return {
        "run_id": run_id, "status": "ok", "dashboard_path": str(DASHBOARD_PATH),
        "row_counts": refresh_manifest.row_counts, "processing_mode": processing_mode,
        "manifest_path": str(MANIFEST_LATEST), "warnings": warnings, "errors": errors,
        "agent_stats": stats.as_dict(),
    }
