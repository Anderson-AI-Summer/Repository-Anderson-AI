import datetime as dt

from src.obligations import (
    compute_cumulative_award_obligation,
    deobligation_rate,
    detect_reversal_pairs,
    flag_negative_obligation_anomalies,
    gross_deobligations,
    gross_positive_obligations,
    net_obligations,
    obligation_direction,
    transaction_activity,
)
from src.schema import ObligationDirection


def test_obligation_direction_positive():
    assert obligation_direction(500.0) == ObligationDirection.OBLIGATION


def test_obligation_direction_negative():
    assert obligation_direction(-500.0) == ObligationDirection.DEOBLIGATION


def test_obligation_direction_zero():
    assert obligation_direction(0.0) == ObligationDirection.ZERO_DOLLAR_ACTION


def test_signed_amount_is_never_converted_to_absolute(make_txn):
    t = make_txn(transaction_obligated_amount=-250.0)
    assert t.transaction_obligated_amount == -250.0  # never coerced to positive


def test_net_gross_deob_and_rate(make_txn):
    txns = [
        make_txn(transaction_id="1", transaction_obligated_amount=1000.0),
        make_txn(transaction_id="2", transaction_obligated_amount=-200.0),
        make_txn(transaction_id="3", transaction_obligated_amount=0.0),
    ]
    assert net_obligations(txns) == 800.0
    assert gross_positive_obligations(txns) == 1000.0
    assert gross_deobligations(txns) == 200.0
    assert deobligation_rate(txns) == 0.2
    assert transaction_activity(txns) == 1200.0


def test_deobligation_rate_zero_when_no_gross_positive(make_txn):
    txns = [make_txn(transaction_id="1", transaction_obligated_amount=-100.0)]
    assert deobligation_rate(txns) == 0.0


def test_cumulative_award_obligation_running_total_ordered_by_date_and_mod(make_txn):
    txns = [
        make_txn(transaction_id="1", award_id_piid="A1", action_date=dt.date(2020, 1, 1), modification_number="0", transaction_obligated_amount=1000.0),
        make_txn(transaction_id="2", award_id_piid="A1", action_date=dt.date(2020, 2, 1), modification_number="1", transaction_obligated_amount=500.0),
        make_txn(transaction_id="3", award_id_piid="A1", action_date=dt.date(2020, 3, 1), modification_number="2", transaction_obligated_amount=-300.0),
        make_txn(transaction_id="4", award_id_piid="A2", action_date=dt.date(2020, 1, 1), modification_number="0", transaction_obligated_amount=200.0),
    ]
    cumulative = compute_cumulative_award_obligation(txns)
    assert cumulative["1"] == 1000.0
    assert cumulative["2"] == 1500.0
    assert cumulative["3"] == 1200.0
    assert cumulative["4"] == 200.0  # separate award, independent running total


def test_cumulative_handles_mixed_numeric_and_alphanumeric_modification_numbers(make_txn):
    # Real data mixes purely numeric mods ("0", "67") with alphanumeric ones
    # ("P00032") -- sorting must not raise TypeError when two rows share an
    # action_date but have differently-typed modification numbers.
    txns = [
        make_txn(transaction_id="1", award_id_piid="A1", action_date=dt.date(2020, 1, 1), modification_number="0", transaction_obligated_amount=100.0),
        make_txn(transaction_id="2", award_id_piid="A1", action_date=dt.date(2020, 1, 1), modification_number="P00032", transaction_obligated_amount=50.0),
    ]
    cumulative = compute_cumulative_award_obligation(txns)
    assert set(cumulative.keys()) == {"1", "2"}
    assert max(cumulative.values()) == 150.0  # final running total is the full sum regardless of tie-break order
    assert min(cumulative.values()) in (100.0, 50.0)  # the first-applied amount, whichever tie-break order was used


def test_cumulative_handles_out_of_order_input(make_txn):
    # Rows arrive out of date order; cumulative must still be computed chronologically.
    txns = [
        make_txn(transaction_id="2", award_id_piid="A1", action_date=dt.date(2020, 2, 1), modification_number="1", transaction_obligated_amount=500.0),
        make_txn(transaction_id="1", award_id_piid="A1", action_date=dt.date(2020, 1, 1), modification_number="0", transaction_obligated_amount=1000.0),
    ]
    cumulative = compute_cumulative_award_obligation(txns)
    assert cumulative["1"] == 1000.0
    assert cumulative["2"] == 1500.0


def test_flag_negative_missing_award_id(make_txn):
    t = make_txn(award_id_piid="", transaction_obligated_amount=-100.0)
    flags = flag_negative_obligation_anomalies(t, cumulative_award_obligation=-100.0, preceding_positive_total=0.0)
    assert "negative_missing_award_id" in flags
    assert "cumulative_award_obligation_negative" in flags
    assert "deobligation_exceeds_known_prior_obligations" in flags


def test_flag_negative_within_known_prior_obligations_not_flagged_as_exceeding(make_txn):
    t = make_txn(award_id_piid="A1", transaction_obligated_amount=-100.0)
    flags = flag_negative_obligation_anomalies(t, cumulative_award_obligation=900.0, preceding_positive_total=1000.0)
    assert "deobligation_exceeds_known_prior_obligations" not in flags
    assert "cumulative_award_obligation_negative" not in flags


def test_flag_cancellation_keyword_in_description(make_txn):
    t = make_txn(transaction_obligated_amount=-50.0, transaction_description="Contract termination for convenience")
    flags = flag_negative_obligation_anomalies(t, cumulative_award_obligation=0.0, preceding_positive_total=100.0)
    assert "description_suggests_cancellation_or_correction" in flags


def test_zero_dollar_transactions_never_flagged_as_negative(make_txn):
    t = make_txn(transaction_obligated_amount=0.0)
    flags = flag_negative_obligation_anomalies(t, cumulative_award_obligation=0.0, preceding_positive_total=0.0)
    assert flags == []


def test_detect_same_day_reversal_pairs(make_txn):
    txns = [
        make_txn(transaction_id="1", award_id_piid="A1", action_date=dt.date(2020, 1, 1), transaction_obligated_amount=500.0),
        make_txn(transaction_id="2", award_id_piid="A1", action_date=dt.date(2020, 1, 1), transaction_obligated_amount=-500.0),
        make_txn(transaction_id="3", award_id_piid="A1", action_date=dt.date(2020, 1, 2), transaction_obligated_amount=100.0),
    ]
    flagged = detect_reversal_pairs(txns)
    assert flagged == {"1", "2"}
