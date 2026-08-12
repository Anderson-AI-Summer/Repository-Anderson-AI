"""Heuristic PPP loan risk-indicator scoring.

IMPORTANT: this is NOT a fraud determination. It is a transparent, rule-based
score built from red flags that public oversight bodies (GAO, SBA Office of
Inspector General) have documented as *worth further review* in PPP data —
not proof of wrongdoing. Any of these can have an innocent explanation (a
round number is just as easily a simplified self-employed application as a
fabricated one). This dataset also carries no borrower name for loans under
$150K (SBA redacts it), so no individual business is identified or accused
by this score — only lender/date/amount/NAICS-level patterns.

Each indicator below cites the documented pattern it's based on. Weights are
illustrative, not calibrated against confirmed-fraud outcomes.
"""

from collections import defaultdict
from typing import Dict, List, NamedTuple

# (name, weight, description)
INDICATORS = {
    "round_dollar_amount": (
        20,
        "Loan amount is an exact multiple of $1,000. Real payroll-based "
        "calculations rarely land on an exact round thousand; DOJ PPP fraud "
        "prosecutions have repeatedly cited suspiciously round requested "
        "amounts as a red flag.",
    ),
    "missing_naics": (
        20,
        "Industry (NAICS) code is blank or a placeholder value. GAO cited "
        "missing/invalid NAICS codes as a data-integrity screening indicator "
        "for further review.",
    ),
    "near_threshold": (
        15,
        "Loan amount falls in $149,000–$149,999, just under the $150,000 "
        "disclosure/documentation threshold — a documented pattern of "
        "amounts apparently tuned to avoid the greater scrutiny given to "
        "loans at or above that threshold.",
    ),
    "batch_duplicate": (
        25,
        "This loan shares an identical lender, amount, and approval date "
        "with at least two other loans in the dataset. Clusters of "
        "identical-amount, same-day, same-lender loans are a documented "
        "\"loan mill\" / batch-processing fraud-ring pattern from DOJ PPP "
        "prosecutions of certain high-volume fintech lenders.",
    ),
    "zero_jobs_large_loan": (
        20,
        "Loan amount is $10,000 or more but zero jobs were reported "
        "retained. SBA OIG audits flagged large loans paired with zero "
        "reported jobs as an application-integrity indicator.",
    ),
}

MAX_SCORE = sum(w for w, _ in [(v[0], v[1]) for v in INDICATORS.values()])


class RiskResult(NamedTuple):
    score: int
    tier: str
    flags: List[str]


def _tier(score: int) -> str:
    if score >= 75:
        return "Very High"
    if score >= 50:
        return "High"
    if score >= 25:
        return "Elevated"
    return "Low"


def score_loans(loans: List[dict]) -> List[RiskResult]:
    """Score a list of loan dicts with keys: amount, naics, date, lender, jobs_retained.

    amount: float, naics: str, date: str (MM/DD/YYYY), lender: str,
    jobs_retained: float or None.
    """
    batch_counts: Dict[tuple, int] = defaultdict(int)
    for loan in loans:
        key = (loan["lender"], round(loan["amount"], 2), loan["date"])
        batch_counts[key] += 1

    results = []
    for loan in loans:
        flags = []
        score = 0

        if loan["amount"] % 1000 == 0:
            flags.append("round_dollar_amount")
            score += INDICATORS["round_dollar_amount"][0]

        naics = (loan.get("naics") or "").strip()
        if not naics or naics in {"0", "000000", "999990"}:
            flags.append("missing_naics")
            score += INDICATORS["missing_naics"][0]

        if 149000 <= loan["amount"] < 150000:
            flags.append("near_threshold")
            score += INDICATORS["near_threshold"][0]

        key = (loan["lender"], round(loan["amount"], 2), loan["date"])
        if batch_counts[key] >= 3:
            flags.append("batch_duplicate")
            score += INDICATORS["batch_duplicate"][0]

        jobs = loan.get("jobs_retained")
        if loan["amount"] >= 10000 and (jobs is None or jobs == 0):
            flags.append("zero_jobs_large_loan")
            score += INDICATORS["zero_jobs_large_loan"][0]

        results.append(RiskResult(score=score, tier=_tier(score), flags=flags))

    return results
