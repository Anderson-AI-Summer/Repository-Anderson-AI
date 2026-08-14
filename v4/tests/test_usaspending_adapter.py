import csv
import tempfile
import unittest

from spend_agent.usaspending_adapter import convert_usaspending_csv


def _write_csv(rows_with_header):
    fh = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
    writer = csv.writer(fh)
    writer.writerows(rows_with_header)
    fh.close()
    return fh.name


class TestUsaspendingAdapter(unittest.TestCase):
    def test_converts_snake_case_bulk_download_schema(self):
        input_path = _write_csv([
            [
                "recipient_name", "awarding_agency_name", "action_date",
                "federal_action_obligation", "naics_description",
                "product_or_service_code_description", "award_description",
            ],
            [
                "Acme Corp", "Department of Example", "2025-01-01", "125000.00",
                "Computer Systems Design Services", "Information Technology Services",
                "Cloud migration",
            ],
        ])
        output_path = tempfile.mktemp(suffix=".csv")

        written = convert_usaspending_csv(input_path, output_path)

        self.assertEqual(written, 1)
        with open(output_path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(rows[0]["Vendor"], "Acme Corp")
        self.assertEqual(rows[0]["Amount"], "125000.00")
        self.assertEqual(rows[0]["Date"], "2025-01-01")
        self.assertIn("Information Technology Services", rows[0]["Description"])
        self.assertIn("Computer Systems Design Services", rows[0]["Description"])
        self.assertIn("Cloud migration", rows[0]["Description"])

    def test_converts_title_case_award_search_api_schema(self):
        input_path = _write_csv([
            ["Recipient Name", "Award Amount", "Start Date", "NAICS Description"],
            ["Beta LLC", "50000", "2025-02-02", "Engineering Services"],
        ])
        output_path = tempfile.mktemp(suffix=".csv")

        written = convert_usaspending_csv(input_path, output_path)

        self.assertEqual(written, 1)
        with open(output_path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(rows[0]["Vendor"], "Beta LLC")
        self.assertEqual(rows[0]["Amount"], "50000.00")
        self.assertIn("Engineering Services", rows[0]["Description"])

    def test_skips_rows_missing_recipient_or_amount(self):
        input_path = _write_csv([
            ["recipient_name", "federal_action_obligation"],
            ["", "1000.00"],
            ["Gamma Inc", ""],
            ["Delta Inc", "2000.00"],
        ])
        output_path = tempfile.mktemp(suffix=".csv")

        written = convert_usaspending_csv(input_path, output_path)

        self.assertEqual(written, 1)
        with open(output_path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(rows[0]["Vendor"], "Delta Inc")

    def test_raises_when_required_columns_are_missing(self):
        input_path = _write_csv([
            ["some_other_column"],
            ["value"],
        ])
        output_path = tempfile.mktemp(suffix=".csv")

        with self.assertRaises(ValueError):
            convert_usaspending_csv(input_path, output_path)

    def test_handles_deobligation_amounts_in_parentheses(self):
        input_path = _write_csv([
            ["recipient_name", "federal_action_obligation"],
            ["Epsilon Co", "(500.00)"],
        ])
        output_path = tempfile.mktemp(suffix=".csv")

        written = convert_usaspending_csv(input_path, output_path)

        self.assertEqual(written, 1)
        with open(output_path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(rows[0]["Amount"], "-500.00")


if __name__ == "__main__":
    unittest.main()
