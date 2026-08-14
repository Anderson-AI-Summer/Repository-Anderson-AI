import unittest

from spend_agent.vendor_resolution import build_vendor_registry, is_same_vendor, normalize_vendor


class TestVendorResolution(unittest.TestCase):
    def test_clusters_four_aliases_of_the_same_vendor(self):
        raw_names = [
            "STAPLES #04521",
            "Staples Business Advantage",
            "STAPLES.COM",
            "Staples Inc",
        ]
        raw_to_cluster_id, clusters = build_vendor_registry(raw_names)

        cluster_ids = {raw_to_cluster_id[name] for name in raw_names}
        self.assertEqual(len(cluster_ids), 1, "all four aliases should resolve to one cluster")

        cluster = clusters[next(iter(cluster_ids))]
        self.assertEqual(sorted(cluster.aliases), sorted(raw_names))

    def test_does_not_merge_unrelated_vendors_sharing_a_generic_word(self):
        raw_to_cluster_id, _ = build_vendor_registry(["Dell Technologies", "Slack Technologies"])
        self.assertNotEqual(
            raw_to_cluster_id["Dell Technologies"], raw_to_cluster_id["Slack Technologies"]
        )

    def test_alias_map_bridges_known_abbreviations(self):
        aliases = {"aws": "Amazon Web Services"}
        raw_to_cluster_id, _ = build_vendor_registry(
            ["AWS", "Amazon Web Services"], aliases=aliases
        )
        self.assertEqual(raw_to_cluster_id["AWS"], raw_to_cluster_id["Amazon Web Services"])

    def test_normalize_vendor_strips_store_numbers_and_legal_suffixes(self):
        self.assertEqual(normalize_vendor("STAPLES #04521"), "STAPLES")
        self.assertEqual(normalize_vendor("Staples Inc"), "STAPLES")
        self.assertEqual(normalize_vendor("STAPLES.COM"), "STAPLES")

    def test_is_same_vendor_requires_leading_token_agreement(self):
        self.assertTrue(is_same_vendor("STAPLES", "STAPLES BUSINESS ADVANTAGE"))
        self.assertFalse(is_same_vendor("DELL TECHNOLOGIES", "SLACK TECHNOLOGIES"))
        self.assertFalse(is_same_vendor("", "STAPLES"))

    def test_does_not_merge_unrelated_banks_sharing_a_leading_word(self):
        # Regression: matching on the leading token alone previously merged
        # unrelated banks that both start with "First" or "Bank of".
        raw_to_cluster_id, _ = build_vendor_registry(
            [
                "First Interstate Bank",
                "First Republic Bank",
                "Bank of Jackson Hole",
                "Bank of America, National Association",
            ]
        )
        self.assertNotEqual(
            raw_to_cluster_id["First Interstate Bank"], raw_to_cluster_id["First Republic Bank"]
        )
        self.assertNotEqual(
            raw_to_cluster_id["Bank of Jackson Hole"],
            raw_to_cluster_id["Bank of America, National Association"],
        )

    def test_merges_a_branch_name_that_is_a_true_prefix(self):
        raw_to_cluster_id, _ = build_vendor_registry(["Pinnacle Bank", "Pinnacle Bank-Wyoming"])
        self.assertEqual(raw_to_cluster_id["Pinnacle Bank"], raw_to_cluster_id["Pinnacle Bank-Wyoming"])


if __name__ == "__main__":
    unittest.main()
