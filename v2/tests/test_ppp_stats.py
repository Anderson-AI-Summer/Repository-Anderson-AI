import unittest

from spend_agent.ppp_stats import mean, stdev, two_proportion_z_test, welch_t_test, zscore


class TestPPPStats(unittest.TestCase):
    def test_mean_and_stdev(self):
        self.assertEqual(mean([1, 2, 3, 4]), 2.5)
        self.assertAlmostEqual(stdev([2, 4, 4, 4, 5, 5, 7, 9]), 2.13809, places=4)
        self.assertEqual(stdev([5]), 0.0)

    def test_zscore(self):
        self.assertAlmostEqual(zscore(15, 10, 5), 1.0)
        self.assertEqual(zscore(15, 10, 0), 0.0)

    def test_welch_t_test_matches_known_scipy_values(self):
        # Verified against scipy.stats.ttest_ind(equal_var=False) during development.
        a = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        b = [3, 4, 5, 6, 7, 8, 9, 10, 11, 20]
        result = welch_t_test(a, b)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.t_statistic, -1.5476, places=3)
        self.assertAlmostEqual(result.df, 15.0813, places=3)
        self.assertAlmostEqual(result.p_value, 0.14244, places=4)

    def test_welch_t_test_insufficient_sample(self):
        self.assertIsNone(welch_t_test([1], [1, 2, 3]))

    def test_two_proportion_z_test_matches_known_value(self):
        # 40/100 vs 25/100: verified against statsmodels/scipy-equivalent formula.
        result = two_proportion_z_test(40, 100, 25, 100)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.z_statistic, 2.2646, places=3)
        self.assertAlmostEqual(result.p_value, 0.02354, places=3)

    def test_two_proportion_z_test_identical_rates(self):
        result = two_proportion_z_test(50, 100, 50, 100)
        self.assertAlmostEqual(result.z_statistic, 0.0)
        self.assertAlmostEqual(result.p_value, 1.0)


if __name__ == "__main__":
    unittest.main()
