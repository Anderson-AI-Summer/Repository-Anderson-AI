import os
import tempfile
import unittest

from spend_agent.pipeline import run_pipeline
from spend_agent.usaspending_adapter import convert_usaspending_csv


class TestUsaspendingPipeline(unittest.TestCase):
    def setUp(self):
        outdir = tempfile.mkdtemp()
        transactions_path = os.path.join(outdir, "converted_transactions.csv")
        convert_usaspending_csv("usaspending/data/sample_nasa_contracts.csv", transactions_path)
        self.results, self.clusters = run_pipeline(
            transactions_path,
            "config/usaspending_taxonomy.json",
            "usaspending/data/sample_preferred_suppliers.json",
            "config/vendor_aliases.json",
        )

    def test_processes_every_award(self):
        self.assertEqual(len(self.results), 26)

    def test_meridian_defense_systems_variants_resolve_to_one_vendor(self):
        meridian_rows = [
            r for r in self.results if "MERIDIAN" in r.transaction.vendor_raw.upper()
        ]
        cluster_ids = {r.vendor_cluster_id for r in meridian_rows}
        self.assertEqual(len(cluster_ids), 1)
        self.assertEqual(meridian_rows[0].vendor_alias_count, 4)

    def test_no_category_left_uncategorized(self):
        from spend_agent.taxonomy import UNCATEGORIZED

        uncategorized = [r for r in self.results if r.category == UNCATEGORIZED]
        self.assertEqual(uncategorized, [])

    def test_flags_it_awards_routed_away_from_preferred_supplier(self):
        quicktech = next(
            r for r in self.results if r.transaction.vendor_raw == "QuickTech Reseller LLC"
        )
        self.assertTrue(quicktech.bypassed_preferred_supplier)
        self.assertEqual(quicktech.preferred_supplier, "Northgate IT Solutions")

    def test_northgate_awards_not_flagged(self):
        northgate_rows = [
            r for r in self.results if r.canonical_vendor == "Northgate IT Solutions"
        ]
        self.assertTrue(northgate_rows)
        self.assertTrue(all(not r.bypassed_preferred_supplier for r in northgate_rows))

    def test_flags_transportation_award_routed_away_from_preferred_supplier(self):
        cobalt = next(
            r for r in self.results if r.transaction.vendor_raw == "Cobalt Line Freight LLC"
        )
        self.assertEqual(cobalt.category, "Transportation & Logistics")
        self.assertTrue(cobalt.bypassed_preferred_supplier)
        self.assertEqual(cobalt.preferred_supplier, "Atlas Freight Systems")

    def test_category_without_preferred_supplier_never_flagged(self):
        medical_rows = [r for r in self.results if r.category == "Medical & Health Services"]
        self.assertTrue(medical_rows)
        self.assertTrue(all(not r.bypassed_preferred_supplier for r in medical_rows))


if __name__ == "__main__":
    unittest.main()
