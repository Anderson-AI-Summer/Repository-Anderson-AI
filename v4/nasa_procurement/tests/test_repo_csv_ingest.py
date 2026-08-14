from src.ingest import fetch_from_repo_csv

CSV_HEADER = "Award ID,Mod,Recipient Name,Action Date,Transaction Amount,Awarding Agency,Awarding Sub Agency,Award Type,Transaction Description\n"


def test_fetch_from_repo_csv_parses_known_schema(tmp_path):
    csv_path = tmp_path / "nasa_sample.csv"
    csv_path.write_text(
        CSV_HEADER
        + '"80MSFC23CA014","P00032","BLUE ORIGIN WASHINGTON, LLC","2025-09-19","580000000.0",'
          '"National Aeronautics and Space Administration","National Aeronautics and Space Administration",'
          '"DEFINITIVE CONTRACT","LANDER DEMO"\n'
    )
    rows, manifest = fetch_from_repo_csv(csv_path)
    assert len(rows) == 1
    assert rows[0].recipient_name_raw == "BLUE ORIGIN WASHINGTON, LLC"
    assert rows[0].transaction_obligated_amount == 580000000.0
    assert rows[0].award_detail_available is False
    assert manifest["validation_results"]["passed"] is True
    assert manifest["source"].startswith("repo_csv:")


def test_fetch_from_repo_csv_flags_unexpected_award_type(tmp_path):
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text(
        CSV_HEADER
        + '"AWD1","0","ACME","2020-01-01","100.0","NASA","NASA","GRANT","test"\n'
    )
    rows, manifest = fetch_from_repo_csv(csv_path)
    assert manifest["validation_results"]["passed"] is False
    assert any("GRANT" in e for e in manifest["validation_results"]["assistance_award_leak_errors"])


def test_fetch_from_repo_csv_deduplicates_exact_repeat_rows(tmp_path):
    row = ('"AWD1","0","ACME","2020-01-01","100.0","NASA","NASA","PURCHASE ORDER","test"\n')
    csv_path = tmp_path / "dup.csv"
    csv_path.write_text(CSV_HEADER + row + row)
    rows, manifest = fetch_from_repo_csv(csv_path)
    assert len(rows) == 1
    assert manifest["row_counts"]["duplicate_rows_removed"] == 1
