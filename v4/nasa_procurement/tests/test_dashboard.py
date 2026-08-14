import datetime as dt
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
    snapshot_json = tmp_path / "standouts_snapshot.json"

    stats = AgentRunStats()
    txns = [make_txn(transaction_id="1", transaction_obligated_amount=500.0)]
    enriched = enrich_transactions(txns, stats)
    df = pd.DataFrame([e.model_dump(mode="json") for e in enriched])
    df.to_csv(enriched_csv, index=False)

    monkeypatch.setattr(pipeline, "ENRICHED_LATEST", enriched_csv)
    monkeypatch.setattr(pipeline, "MANIFEST_LATEST", manifest_json)
    monkeypatch.setattr(pipeline, "DASHBOARD_PATH", dashboard_html)
    monkeypatch.setattr(pipeline, "STANDOUTS_SNAPSHOT", snapshot_json)

    result = pipeline.run_pipeline(mode="rebuild")

    assert result["status"] == "ok"
    assert dashboard_html.exists()
    assert result["row_counts"]["enriched_transactions"] == 1


def test_rebuild_handles_missing_transaction_description(make_txn, tmp_path, monkeypatch):
    # A blank transaction_description round-trips through the processed-data
    # CSV as an empty cell, which pandas reads back as a float NaN -- not
    # None or "". NaN is truthy in Python, so a naive `if d` filter doesn't
    # exclude it, and _award_rows's "pick the longest description on record"
    # logic (max(descriptions, key=len)) crashed on this against a real
    # multi-year pull, where some award records have no description at all.
    import src.pipeline as pipeline

    enriched_csv = tmp_path / "enriched_transactions_latest.csv"
    manifest_json = tmp_path / "refresh_manifest_latest.json"
    dashboard_html = tmp_path / "nasa_procurement_dashboard.html"
    snapshot_json = tmp_path / "standouts_snapshot.json"

    stats = AgentRunStats()
    txns = [
        make_txn(transaction_id="1", award_id_piid="AWD001", transaction_description=""),
        make_txn(transaction_id="2", award_id_piid="AWD001", transaction_description="real description"),
    ]
    enriched = enrich_transactions(txns, stats)
    df = pd.DataFrame([e.model_dump(mode="json") for e in enriched])
    df.to_csv(enriched_csv, index=False)

    monkeypatch.setattr(pipeline, "ENRICHED_LATEST", enriched_csv)
    monkeypatch.setattr(pipeline, "MANIFEST_LATEST", manifest_json)
    monkeypatch.setattr(pipeline, "DASHBOARD_PATH", dashboard_html)
    monkeypatch.setattr(pipeline, "STANDOUTS_SNAPSHOT", snapshot_json)

    result = pipeline.run_pipeline(mode="rebuild")

    assert result["status"] == "ok"
    assert dashboard_html.exists()


def test_snapshot_marks_nothing_new_on_first_run(tmp_path, monkeypatch):
    import src.pipeline as pipeline

    monkeypatch.setattr(pipeline, "STANDOUTS_SNAPSHOT", tmp_path / "standouts_snapshot.json")
    payload = {
        "standout_suppliers": [{"supplier": "Acme Corp"}],
        "standout_awards": [{"award_id": "AWD1"}],
        "consolidation_opportunities": [{"category": "IT"}],
        "duplicate_purchase_candidates": [{"pair_id": "AWD1::AWD2"}],
    }
    had_previous = pipeline._mark_new_since_last_run(payload)
    assert had_previous is False
    assert payload["standout_suppliers"][0]["is_new"] is False
    assert payload["standout_awards"][0]["is_new"] is False


def test_snapshot_marks_genuinely_new_items_across_runs(tmp_path, monkeypatch):
    import src.pipeline as pipeline

    monkeypatch.setattr(pipeline, "STANDOUTS_SNAPSHOT", tmp_path / "standouts_snapshot.json")

    first_payload = {
        "standout_suppliers": [{"supplier": "Acme Corp"}],
        "standout_awards": [],
        "consolidation_opportunities": [],
        "duplicate_purchase_candidates": [],
    }
    pipeline._mark_new_since_last_run(first_payload)
    pipeline._save_snapshot(first_payload)

    second_payload = {
        "standout_suppliers": [{"supplier": "Acme Corp"}, {"supplier": "Globex LLC"}],
        "standout_awards": [{"award_id": "AWD1"}],
        "consolidation_opportunities": [],
        "duplicate_purchase_candidates": [],
    }
    had_previous = pipeline._mark_new_since_last_run(second_payload)

    assert had_previous is True
    suppliers_by_name = {s["supplier"]: s["is_new"] for s in second_payload["standout_suppliers"]}
    assert suppliers_by_name["Acme Corp"] is False  # present last run too
    assert suppliers_by_name["Globex LLC"] is True  # genuinely new
    assert second_payload["standout_awards"][0]["is_new"] is True


def test_bid_competition_review_flags_concentrated_low_competition_supplier(make_txn):
    txns = [
        make_txn(
            transaction_id=f"t{i}", award_id_piid=f"AWD00{i}", recipient_name_raw="ACME CORP",
            transaction_obligated_amount=100_000.0, current_award_amount=100_000.0,
            number_of_offers_received=1, extent_competed="C", extent_competed_description="NOT COMPETED",
            set_aside_type_description="8(A) SOLE SOURCE", award_detail_available=True,
        )
        for i in range(1, 4)
    ]
    stats = AgentRunStats()
    enriched = enrich_transactions(txns, stats)
    analytics = compute_analytics(enriched)
    payload = build_payload(enriched, analytics, [], {"source": "test"}, "DETERMINISTIC_FALLBACK")

    review = payload["bid_competition_review"]
    assert review["available"] is True
    assert review["awards_with_detail"] == 3
    suppliers = {s["supplier"]: s for s in review["suppliers"]}
    assert "ACME CORP" in suppliers
    assert suppliers["ACME CORP"]["sub_threshold_award_count"] == 3
    assert suppliers["ACME CORP"]["low_competition_award_count"] == 3
    assert suppliers["ACME CORP"]["low_competition_share"] == 1.0
    # Total contract count is over every award in the dataset, not just the
    # ones with competition detail fetched.
    assert suppliers["ACME CORP"]["total_award_count"] == 3
    assert suppliers["ACME CORP"]["awards"][0]["set_aside"] == "8(A) SOLE SOURCE"
    # Every sub-threshold award is embedded (flagged or not) so the UI's
    # threshold control can recompute the ratio exactly.
    assert all(a["low_competition"] for a in suppliers["ACME CORP"]["awards"])
    assert suppliers["ACME CORP"]["awards_truncated"] is False


def test_bid_competition_review_unavailable_without_award_detail(make_txn):
    # Large multi-year pulls in this project skip the per-award detail
    # fetch for speed, so number_of_offers_received/extent_competed are
    # absent -- the review must say so rather than showing an empty or
    # misleadingly-confident table.
    txns = [make_txn(transaction_id="1", award_detail_available=False, number_of_offers_received=None)]
    stats = AgentRunStats()
    enriched = enrich_transactions(txns, stats)
    analytics = compute_analytics(enriched)
    payload = build_payload(enriched, analytics, [], {"source": "test"}, "DETERMINISTIC_FALLBACK")

    review = payload["bid_competition_review"]
    assert review["available"] is False
    assert review["suppliers"] == []


def test_bid_competition_review_excludes_well_competed_suppliers(make_txn):
    txns = [
        make_txn(
            transaction_id="1", award_id_piid="AWD100", recipient_name_raw="GLOBEX LLC",
            transaction_obligated_amount=50_000.0, current_award_amount=50_000.0,
            number_of_offers_received=6, extent_competed="A", extent_competed_description="FULL AND OPEN COMPETITION",
            award_detail_available=True,
        ),
    ]
    stats = AgentRunStats()
    enriched = enrich_transactions(txns, stats)
    analytics = compute_analytics(enriched)
    payload = build_payload(enriched, analytics, [], {"source": "test"}, "DETERMINISTIC_FALLBACK")

    review = payload["bid_competition_review"]
    assert review["available"] is True
    assert review["suppliers"] == []  # well-competed -- nothing to flag


def test_misuse_screen_sets_aside_proprietary_software_psc(make_txn):
    # Two suppliers, both 100% single-bid below threshold. One sells a
    # proprietary software license (PSC 7A20), which is expected to be
    # sole-source; the other sells lab equipment, which is not.
    txns = []
    for i in range(1, 4):
        txns.append(make_txn(
            transaction_id=f"s{i}", award_id_piid=f"SOFT{i}", recipient_name_raw="COMSOL, INC.",
            recipient_uei="UEISOFT01",
            transaction_obligated_amount=100_000.0, current_award_amount=100_000.0,
            number_of_offers_received=1, extent_competed="C", extent_competed_description="NOT COMPETED",
            psc_code="7A20", award_detail_available=True,
        ))
        txns.append(make_txn(
            transaction_id=f"l{i}", award_id_piid=f"LAB{i}", recipient_name_raw="GENERIC LAB SUPPLY CO",
            recipient_uei="UEILAB001",
            transaction_obligated_amount=100_000.0, current_award_amount=100_000.0,
            number_of_offers_received=1, extent_competed="C", extent_competed_description="NOT COMPETED",
            psc_code="6640", award_detail_available=True,
        ))
    stats = AgentRunStats()
    payload = build_payload(enrich_transactions(txns, stats), compute_analytics(enrich_transactions(txns, AgentRunStats())),
                            [], {"source": "test"}, "DETERMINISTIC_FALLBACK")
    review = payload["bid_competition_review"]

    ranked = {s["supplier"] for s in review["suppliers"]}
    assert "GENERIC LAB SUPPLY CO" in ranked      # real competitive market -> still flagged
    assert "COMSOL, INC." not in ranked           # proprietary licence -> set aside

    # Set aside, not deleted: it is still reported with its award count.
    set_aside = {s["supplier"]: s for s in review["set_aside"]["suppliers"]}
    assert "COMSOL, INC." in set_aside
    assert set_aside["COMSOL, INC."]["award_count"] == 3
    assert review["set_aside"]["award_count"] == 3


def test_supplier_detail_annual_carries_full_metric_set(make_txn):
    txns = [
        make_txn(transaction_id="a", award_id_piid="AWD1", action_date=dt.date(2020, 1, 5),
                 fiscal_year=2020, transaction_obligated_amount=1000.0),
        make_txn(transaction_id="b", award_id_piid="AWD1", action_date=dt.date(2021, 1, 5),
                 fiscal_year=2021, transaction_obligated_amount=-250.0),
        make_txn(transaction_id="c", award_id_piid="AWD2", action_date=dt.date(2021, 3, 5),
                 fiscal_year=2021, transaction_obligated_amount=500.0),
    ]
    stats = AgentRunStats()
    enriched = enrich_transactions(txns, stats)
    payload = build_payload(enriched, compute_analytics(enriched), [], {"source": "test"}, "DETERMINISTIC_FALLBACK")
    annual = {r["fiscal_year"]: r for r in payload["suppliers_detail"]["ACME CORP"]["annual"]}

    # Per-year metrics are what lets the Timeframe control scope this tab.
    assert annual[2020]["net_obligations"] == 1000.0
    assert annual[2020]["gross_positive_obligations"] == 1000.0
    assert annual[2020]["deobligations"] == 0.0
    assert annual[2021]["deobligations"] == 250.0
    assert annual[2021]["transaction_count"] == 2
    assert annual[2021]["unique_awards"] == 2
    # Summing the exactly-summable metrics reproduces the all-time totals.
    d = payload["suppliers_detail"]["ACME CORP"]
    assert sum(r["net_obligations"] for r in d["annual"]) == d["total_net_obligations"]
    assert sum(r["transaction_count"] for r in d["annual"]) == d["transaction_count"]


def test_category_detail_annual_carries_per_year_counts(make_txn):
    txns = [
        make_txn(transaction_id="a", action_date=dt.date(2020, 1, 5), fiscal_year=2020,
                 transaction_obligated_amount=1000.0),
        make_txn(transaction_id="b", action_date=dt.date(2021, 1, 5), fiscal_year=2021,
                 transaction_obligated_amount=2000.0, recipient_name_raw="OTHER VENDOR LLC"),
    ]
    stats = AgentRunStats()
    enriched = enrich_transactions(txns, stats)
    payload = build_payload(enriched, compute_analytics(enriched), [], {"source": "test"}, "DETERMINISTIC_FALLBACK")
    cat = next(iter(payload["categories_detail"].values()))
    annual = {r["fiscal_year"]: r for r in cat["annual"]}
    assert annual[2020]["transaction_count"] == 1
    assert annual[2021]["unique_suppliers"] == 1
    assert sum(r["net_obligations"] for r in cat["annual"]) == 3000.0
