import json
from pathlib import Path

import pandas as pd
import pytest

from src.analytics import compute_analytics
from src.dashboard.data_prep import build_payload
from src.dashboard.generate import render_dashboard
from src.dashboard.validate import validate_dashboard_html
from src.enrich import enrich_transactions
from src.agents.base import AgentRunStats


def _minimal_payload():
    analytics = compute_analytics([])
    return build_payload([], analytics, [], {"source": "test"}, "DETERMINISTIC_FALLBACK")


def test_analytics_handles_empty_transaction_list_without_crashing():
    analytics = compute_analytics([])
    assert analytics["totals"] == {}
    assert analytics["annual"] == []


def test_dashboard_generation_with_real_data(make_txn, tmp_path):
    txns = [
        make_txn(transaction_id="1", transaction_obligated_amount=1000.0),
        make_txn(transaction_id="2", transaction_obligated_amount=-100.0, award_id_piid="AWD001"),
    ]
    stats = AgentRunStats()
    enriched = enrich_transactions(txns, stats)
    analytics = compute_analytics(enriched)
    payload = build_payload(enriched, analytics, [], {"source": "test"}, "DETERMINISTIC_FALLBACK")

    out_path = tmp_path / "dashboard.html"
    render_dashboard(payload, out_path)

    assert out_path.exists()
    errors = validate_dashboard_html(out_path, expected_transaction_count=2)
    assert errors == []


def test_dashboard_generation_with_empty_dataset_does_not_crash(tmp_path):
    payload = _minimal_payload()
    out_path = tmp_path / "empty_dashboard.html"
    render_dashboard(payload, out_path)
    assert out_path.exists()
    errors = validate_dashboard_html(out_path, expected_transaction_count=0)
    assert errors == []


def test_dashboard_generation_refuses_to_write_embedded_secret(tmp_path):
    payload = _minimal_payload()
    payload["meta"]["note"] = "leaked key sk-ant-abcdefghij1234567890"
    out_path = tmp_path / "should_not_exist.html"
    with pytest.raises(RuntimeError, match="Secret-shaped string"):
        render_dashboard(payload, out_path)


def test_no_nan_literals_leak_into_payload_json(make_txn, tmp_path):
    # A transaction with no award detail leaves several numeric fields None;
    # pandas aggregation of a single-row group can produce NaN means, which
    # must be sanitized to null before reaching the browser as JSON.
    txns = [make_txn(transaction_id="1", award_detail_available=False, number_of_offers_received=None)]
    stats = AgentRunStats()
    enriched = enrich_transactions(txns, stats)
    analytics = compute_analytics(enriched)
    payload = build_payload(enriched, analytics, [], {"source": "test"}, "DETERMINISTIC_FALLBACK")
    out_path = tmp_path / "dashboard.html"
    render_dashboard(payload, out_path)
    text = out_path.read_text()
    m = text.split('<script id="dashboard-data" type="application/json">')[1].split("</script>")[0]
    json.loads(m)  # must not raise -- strict JSON, no bare NaN/Infinity tokens


def test_rebuild_from_cached_processed_data(make_txn, tmp_path, monkeypatch):
    import src.pipeline as pipeline

    enriched_csv = tmp_path / "enriched_transactions_latest.csv"
    manifest_json = tmp_path / "refresh_manifest_latest.json"
    dashboard_html = tmp_path / "nasa_procurement_dashboard.html"

    stats = AgentRunStats()
    txns = [make_txn(transaction_id="1", transaction_obligated_amount=500.0)]
    enriched = enrich_transactions(txns, stats)
    df = pd.DataFrame([e.model_dump(mode="json") for e in enriched])
    df.to_csv(enriched_csv, index=False)

    monkeypatch.setattr(pipeline, "ENRICHED_LATEST", enriched_csv)
    monkeypatch.setattr(pipeline, "MANIFEST_LATEST", manifest_json)
    monkeypatch.setattr(pipeline, "DASHBOARD_PATH", dashboard_html)

    result = pipeline.run_pipeline(mode="rebuild")

    assert result["status"] == "ok"
    assert dashboard_html.exists()
    assert result["row_counts"]["enriched_transactions"] == 1
