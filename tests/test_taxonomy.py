import unittest

from spend_agent.taxonomy import classify, load_preferred_suppliers, load_taxonomy


class TestTaxonomy(unittest.TestCase):
    def setUp(self):
        self.taxonomy = load_taxonomy("config/taxonomy.json")

    def test_classifies_known_vendor(self):
        self.assertEqual(classify("Staples Inc", "copy paper", self.taxonomy), "Office Supplies")
        self.assertEqual(
            classify("Amazon Web Services", "ec2 compute", self.taxonomy), "Cloud & Software"
        )

    def test_falls_back_to_uncategorized(self):
        self.assertEqual(classify("Mystery Vendor Co", "assorted goods", self.taxonomy), "Uncategorized")

    def test_loads_preferred_suppliers(self):
        suppliers = load_preferred_suppliers("config/preferred_suppliers.json")
        self.assertEqual(suppliers["Office Supplies"], "Staples Business Advantage")


if __name__ == "__main__":
    unittest.main()
