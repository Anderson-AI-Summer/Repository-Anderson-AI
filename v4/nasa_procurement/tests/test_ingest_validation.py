from src.clean import clean_transaction, deduplicate
from src.ingest import validate_contract_only


def test_contract_only_validation_passes_for_cont_awd_ids():
    rows = [{"generated_internal_id": "CONT_AWD_80NSSC20P0024_8000_-NONE-_-NONE-"}]
    assert validate_contract_only(rows) == []


def test_contract_only_validation_flags_non_contract_ids():
    rows = [{"generated_internal_id": "ASST_NON_1234_8000"}]
    errors = validate_contract_only(rows)
    assert len(errors) == 1
    assert "ASST_NON_1234_8000" in errors[0]


def test_clean_transaction_drops_row_missing_action_date():
    raw = {"Award ID": "AWD1", "Transaction Amount": 100.0, "Recipient Name": "ACME"}
    clean, flags = clean_transaction(raw, None)
    assert clean is None
    assert "missing_required_field:action_date_or_award_id" in flags[0]


def test_clean_transaction_flags_missing_recipient_but_keeps_row():
    raw = {"Award ID": "AWD1", "Action Date": "2020-01-01", "Transaction Amount": 100.0}
    clean, flags = clean_transaction(raw, None)
    assert clean is not None
    assert clean.recipient_name_raw == "UNKNOWN RECIPIENT"
    assert "missing_recipient_name" in flags
    assert "award_detail_unavailable" in flags


def test_clean_transaction_malformed_amount_defaults_to_zero_and_flags():
    raw = {"Award ID": "AWD1", "Action Date": "2020-01-01", "Transaction Amount": "not-a-number", "Recipient Name": "ACME"}
    clean, flags = clean_transaction(raw, None)
    assert clean.transaction_obligated_amount == 0.0
    assert "missing_transaction_amount" in flags


def test_clean_transaction_id_not_solely_from_internal_id():
    # USAspending's "internal_id" on spending_by_transaction rows is shared
    # across distinct modifications of the same award (confirmed against
    # real data). Two rows with the same internal_id but different Mod,
    # Action Date, and Amount must produce DIFFERENT transaction_ids, or
    # deduplicate() silently discards real transactions.
    raw_a = {
        "Award ID": "80NSSC24PC354", "Mod": "0", "Action Date": "2024-09-11",
        "Transaction Amount": 165532.0, "Recipient Name": "ACME", "internal_id": 291848173,
    }
    raw_b = {
        "Award ID": "80NSSC24PC354", "Mod": "P00001", "Action Date": "2024-09-30",
        "Transaction Amount": 0.0, "Recipient Name": "ACME", "internal_id": 291848173,
    }
    clean_a, _ = clean_transaction(raw_a, None)
    clean_b, _ = clean_transaction(raw_b, None)
    assert clean_a.transaction_id != clean_b.transaction_id
    out, duplicates = deduplicate([clean_a, clean_b])
    assert len(out) == 2
    assert duplicates == 0


def test_deduplicate_removes_exact_duplicate_transaction_ids(make_txn):
    a = make_txn(transaction_id="dup")
    b = make_txn(transaction_id="dup")
    c = make_txn(transaction_id="unique")
    out, duplicates = deduplicate([a, b, c])
    assert len(out) == 2
    assert duplicates == 1
    assert {t.transaction_id for t in out} == {"dup", "unique"}
