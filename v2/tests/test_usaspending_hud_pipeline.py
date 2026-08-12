import os
import tempfile
import unittest

from spend_agent.pipeline import run_pipeline
from spend_agent.usaspending_adapter import convert_usaspending_csv


class TestUsaspendingHudPipeline(unittest.TestCase):
    def setUp(self):
        outdir = tempfile.mkdtemp()
        transactions_path = os.path.join(outdir, "converted_transactions.csv")
        convert_usaspending_csv("usaspending/data/sample_hud_contracts.csv", transactions_path)
        self.results, self.clusters = run_pipeline(
            transactions_path,
            "config/usaspending_taxonomy.json",
            "usaspending/data/sample_hud_preferred_suppliers.json",
            "config/vendor_aliases.json",
        )

    def test_processes_every_award(self):
        self.assertEqual(len(self.results), 26)

    def test_crestpoint_variants_resolve_to_one_vendor(self):
        crestpoint_rows = [
            r for r in self.results if "CRESTPOINT" in r.transaction.vendor_raw.upper()
        ]
        cluster_ids = {r.vendor_cluster_id for r in crestpoint_rows}
        self.assertEqual(len(cluster_ids), 1)
        self.assertEqual(crestpoint_rows[0].vendor_alias_count, 4)

    def test_no_category_left_uncategorized(self):
        from spend_agent.taxonomy import UNCATEGORIZED

        uncategorized = [r for r in self.results if r.category == UNCATEGORIZED]
        self.assertEqual(uncategorized, [])

    def test_flags_it_awards_routed_away_from_preferred_supplier(self):
        for vendor_raw in ("ValueTech Resellers LLC", "Coastline Data Systems Inc"):
            row = next(r for r in self.results if r.transaction.vendor_raw == vendor_raw)
            self.assertTrue(row.bypassed_preferred_supplier)
            self.assertEqual(row.preferred_supplier, "Meadowbrook IT Solutions")

    def test_meadowbrook_awards_not_flagged(self):
        meadowbrook_rows = [
            r for r in self.results if r.canonical_vendor == "Meadowbrook IT Solutions"
        ]
        self.assertTrue(meadowbrook_rows)
        self.assertTrue(all(not r.bypassed_preferred_supplier for r in meadowbrook_rows))

    def test_flags_transportation_award_routed_away_from_preferred_supplier(self):
        speedvine = next(
            r for r in self.results if r.transaction.vendor_raw == "Speedvine Courier Solutions LLC"
        )
        self.assertEqual(speedvine.category, "Transportation & Logistics")
        self.assertTrue(speedvine.bypassed_preferred_supplier)
        self.assertEqual(speedvine.preferred_supplier, "Keystone Logistics Partners")

    def test_category_without_preferred_supplier_never_flagged(self):
        medical_rows = [r for r in self.results if r.category == "Medical & Health Services"]
        self.assertTrue(medical_rows)
        self.assertTrue(all(not r.bypassed_preferred_supplier for r in medical_rows))


if __name__ == "__main__":
    unittest.main()
