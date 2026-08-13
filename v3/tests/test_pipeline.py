import tempfile
import unittest
from unittest.mock import patch

from spend_agent.llm_classifier import LlmClassification
from spend_agent.pipeline import run_pipeline
from spend_agent.taxonomy import UNCATEGORIZED


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.results, self.clusters = run_pipeline(
            "data/sample_transactions.csv",
            "config/taxonomy.json",
            "config/preferred_suppliers.json",
            "config/vendor_aliases.json",
        )

    def test_processes_every_row(self):
        self.assertEqual(len(self.results), 23)

    def test_staples_variants_resolve_to_one_vendor(self):
        staples_rows = [r for r in self.results if "STAPLES" in r.transaction.vendor_raw.upper()]
        cluster_ids = {r.vendor_cluster_id for r in staples_rows}
        self.assertEqual(len(cluster_ids), 1)
        self.assertEqual(staples_rows[0].vendor_alias_count, 4)

    def test_none_of_the_staples_purchases_are_flagged(self):
        staples_rows = [r for r in self.results if "STAPLES" in r.transaction.vendor_raw.upper()]
        self.assertTrue(all(not r.bypassed_preferred_supplier for r in staples_rows))

    def test_flags_non_preferred_it_hardware_purchases(self):
        dell = next(r for r in self.results if r.transaction.vendor_raw == "Dell Technologies")
        self.assertTrue(dell.bypassed_preferred_supplier)
        self.assertEqual(dell.preferred_supplier, "CDW")

    def test_aws_abbreviation_not_flagged_as_bypass(self):
        aws_row = next(r for r in self.results if r.transaction.vendor_raw == "AWS")
        self.assertFalse(aws_row.bypassed_preferred_supplier)

    def test_category_without_preferred_supplier_never_flagged(self):
        travel_rows = [r for r in self.results if r.category == "Travel"]
        self.assertTrue(travel_rows)
        self.assertTrue(all(not r.bypassed_preferred_supplier for r in travel_rows))


class TestPipelineLlmFallback(unittest.TestCase):
    def test_llm_fallback_is_off_by_default(self):
        results, _ = run_pipeline(
            "data/sample_transactions.csv",
            "config/taxonomy.json",
            "config/preferred_suppliers.json",
            "config/vendor_aliases.json",
        )
        self.assertTrue(all(not r.llm_assisted for r in results))

    def test_llm_fallback_only_runs_on_uncategorized_rows(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write("Date,Vendor,Description,Amount\n")
            fh.write("2024-01-01,Staples,paper and pens,25.00\n")
            fh.write("2024-01-02,Zzyzx Widgets LLC,miscellaneous purchase,500.00\n")
            path = fh.name

        with patch("spend_agent.llm_classifier.classify_with_llm") as mock_classify:
            mock_classify.return_value = LlmClassification(
                category="Office Supplies", reasoning="test reasoning"
            )
            results, _ = run_pipeline(
                path,
                "config/taxonomy.json",
                "config/preferred_suppliers.json",
                "config/vendor_aliases.json",
                use_llm_fallback=True,
            )

        self.assertEqual(sum(1 for r in results if r.category == UNCATEGORIZED), 0)
        assisted = [r for r in results if r.llm_assisted]
        self.assertEqual(len(assisted), 1)
        self.assertEqual(assisted[0].transaction.vendor_raw, "Zzyzx Widgets LLC")
        self.assertEqual(assisted[0].category, "Office Supplies")
        self.assertEqual(assisted[0].llm_reasoning, "test reasoning")
        # Only called for the row the keyword classifier actually left Uncategorized.
        self.assertEqual(mock_classify.call_count, 1)


if __name__ == "__main__":
    unittest.main()
