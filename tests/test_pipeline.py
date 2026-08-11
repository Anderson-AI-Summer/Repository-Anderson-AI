import unittest

from spend_agent.pipeline import run_pipeline


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


if __name__ == "__main__":
    unittest.main()
