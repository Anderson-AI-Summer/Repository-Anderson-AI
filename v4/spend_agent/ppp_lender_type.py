"""Classifies a PPP lender as a fintech/non-bank lender or a traditional
bank/credit union.

The reference list of fintech-associated PPP lenders is drawn from public
reporting and the peer-reviewed study this analysis replicates a small-scale
version of:

    Griffin, J. M., Kruger, S., & Mahajan, P. (2023). "Did FinTech Lenders
    Facilitate PPP Fraud?" The Journal of Finance, 78(3), 1777-1827.

That paper found loans from fintech-affiliated lenders had substantially
elevated rates of characteristics associated with suspicious applications
compared to traditional banks. Being on this list is a peer-group label for
comparison, not an accusation about any individual loan or lender.
"""

from typing import Set

FINTECH_LENDER_MARKERS: Set[str] = {
    "cross river bank",
    "celtic bank",
    "customers bank",
    "capital plus financial",
    "harvest small business finance",
    "benworth capital",
    "fountainhead sbf",
    "readycap lending",
    "fc marketplace",  # dba Funding Circle
    "funding circle",
    "kabbage",
    "womply",
    "bluevine",
    "fundbox",
    "cambr",
    "customers bank",
    "prestamos",
}

FINTECH = "Fintech/non-bank lender"
TRADITIONAL = "Traditional bank or credit union"


def classify_lender_type(canonical_lender_name: str) -> str:
    name = canonical_lender_name.lower()
    if any(marker in name for marker in FINTECH_LENDER_MARKERS):
        return FINTECH
    return TRADITIONAL
