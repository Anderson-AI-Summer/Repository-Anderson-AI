import unittest

from spend_agent.ppp_risk_score import score_loans


def _loan(amount, naics="722513", date="04/06/2020", lender="Test Bank", jobs=5):
    return {"amount": amount, "naics": naics, "date": date, "lender": lender, "jobs_retained": jobs}


class TestPPPRiskScore(unittest.TestCase):
    def test_clean_loan_scores_low(self):
        result = score_loans([_loan(83417.32)])[0]
        self.assertEqual(result.flags, [])
        self.assertEqual(result.score, 0)
        self.assertEqual(result.tier, "Low")

    def test_round_dollar_amount_flagged(self):
        result = score_loans([_loan(20000)])[0]
        self.assertIn("round_dollar_amount", result.flags)

    def test_missing_naics_flagged(self):
        result = score_loans([_loan(83417.32, naics="")])[0]
        self.assertIn("missing_naics", result.flags)
        result2 = score_loans([_loan(83417.32, naics="999990")])[0]
        self.assertIn("missing_naics", result2.flags)

    def test_near_threshold_flagged(self):
        result = score_loans([_loan(149500)])[0]
        self.assertIn("near_threshold", result.flags)
        result2 = score_loans([_loan(148000)])[0]
        self.assertNotIn("near_threshold", result2.flags)

    def test_zero_jobs_large_loan_flagged(self):
        result = score_loans([_loan(15000, jobs=0)])[0]
        self.assertIn("zero_jobs_large_loan", result.flags)
        result2 = score_loans([_loan(5000, jobs=0)])[0]
        self.assertNotIn("zero_jobs_large_loan", result2.flags)

    def test_batch_duplicate_requires_at_least_three(self):
        two = [_loan(20833, lender="Wells Fargo"), _loan(20833, lender="Wells Fargo")]
        results_two = score_loans(two)
        self.assertTrue(all("batch_duplicate" not in r.flags for r in results_two))

        three = two + [_loan(20833, lender="Wells Fargo")]
        results_three = score_loans(three)
        self.assertTrue(all("batch_duplicate" in r.flags for r in results_three))

    def test_tier_thresholds(self):
        # round + near_threshold = 35 -> Elevated
        result = score_loans([_loan(149000)])[0]
        self.assertEqual(result.tier, "Elevated")


if __name__ == "__main__":
    unittest.main()
