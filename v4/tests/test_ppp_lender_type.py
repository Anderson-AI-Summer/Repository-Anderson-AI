import unittest

from spend_agent.ppp_lender_type import FINTECH, TRADITIONAL, classify_lender_type


class TestPPPLenderType(unittest.TestCase):
    def test_known_fintech_lenders(self):
        self.assertEqual(classify_lender_type("Cross River Bank"), FINTECH)
        self.assertEqual(classify_lender_type("Celtic Bank Corporation"), FINTECH)
        self.assertEqual(classify_lender_type("Readycap Lending, LLC"), FINTECH)
        self.assertEqual(classify_lender_type("FC Marketplace, LLC (dba Funding Circle)"), FINTECH)

    def test_traditional_banks(self):
        self.assertEqual(classify_lender_type("First Interstate Bank"), TRADITIONAL)
        self.assertEqual(classify_lender_type("Bank of Jackson Hole"), TRADITIONAL)
        self.assertEqual(classify_lender_type("Wells Fargo Bank, National Association"), TRADITIONAL)


if __name__ == "__main__":
    unittest.main()
