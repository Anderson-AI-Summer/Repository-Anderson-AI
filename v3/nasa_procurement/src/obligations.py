"""Signed-obligation derivation and negative-obligation analytics.

Negative transactions (deobligations) are never deleted, zeroed, or
replaced with their absolute value here -- the signed amount is preserved
throughout. See PROJECT_SUMMARY.md for the rationale.
"""
from __future__ import annotations

from src.schema import CleanTransaction, ObligationDirection

CANCELLATION_KEYWORDS = (
    "cancel", "cancellation", "correct", "correction", "terminat",
    "closeout", "close-out", "close out", "reduce", "reduction", "deobligat",
)


def obligation_direction(amount: float) -> ObligationDirection:
    if amount > 0:
        return ObligationDirection.OBLIGATION
    if amount < 0:
        return ObligationDirection.DEOBLIGATION
    return ObligationDirection.ZERO_DOLLAR_ACTION


def derive_signed_fields(txn: CleanTransaction) -> dict:
    amount = txn.transaction_obligated_amount
    return {
        "transaction_obligation_signed": amount,
        "transaction_obligation_absolute": abs(amount),
        "obligation_direction": obligation_direction(amount),
    }


def compute_cumulative_award_obligation(transactions: list[CleanTransaction]) -> dict[str, float]:
    """Running signed total per Award ID, ordered by action_date then
    modification_number. Returns {transaction_id: cumulative_total}.
    """
    def mod_sort_key(t: CleanTransaction):
        # Real award modification numbers mix purely numeric ("0", "67") and
        # alphanumeric ("P00032") schemes, sometimes within the same dataset
        # once multiple sources are combined -- a bare (date, int|str) tuple
        # raises TypeError when Python must compare an int to a str because
        # two rows share the same action_date. Always return a uniformly
        # comparable, same-shaped tuple instead.
        mod = t.modification_number or "0"
        try:
            return (t.action_date, 0, int(mod), "")
        except ValueError:
            return (t.action_date, 1, 0, mod)

    by_award: dict[str, list[CleanTransaction]] = {}
    for t in transactions:
        by_award.setdefault(t.award_id_piid, []).append(t)

    result: dict[str, float] = {}
    for award_id, txns in by_award.items():
        ordered = sorted(txns, key=mod_sort_key)
        running = 0.0
        for t in ordered:
            running += t.transaction_obligated_amount
            result[t.transaction_id] = running
    return result


def flag_negative_obligation_anomalies(
    txn: CleanTransaction,
    cumulative_award_obligation: float,
    preceding_positive_total: float,
) -> list[str]:
    """Flags for a negative (deobligation) transaction. Never auto-deletes."""
    flags: list[str] = []
    amount = txn.transaction_obligated_amount
    if amount >= 0:
        return flags

    if not txn.award_id_piid:
        flags.append("negative_missing_award_id")

    if cumulative_award_obligation < -1e-6:
        flags.append("cumulative_award_obligation_negative")

    if abs(amount) > preceding_positive_total + 1e-6:
        flags.append("deobligation_exceeds_known_prior_obligations")

    if not txn.action_type_code and not txn.action_type_description:
        flags.append("missing_action_type")

    desc = (txn.transaction_description or "").lower()
    if any(kw in desc for kw in CANCELLATION_KEYWORDS):
        flags.append("description_suggests_cancellation_or_correction")

    if txn.fiscal_year <= 2020 and txn.action_date.year <= 2020:
        # Award may have originated before the FY2020 extraction window,
        # meaning earlier obligation history is not visible to this dataset.
        flags.append("award_history_may_predate_extraction_window")

    return flags


def detect_reversal_pairs(transactions: list[CleanTransaction]) -> set[str]:
    """Return transaction_ids involved in an exact or near-exact same-day
    positive/negative reversal within the same award (evidence, not proof,
    of a correction -- flagged for review, never removed)."""
    by_award: dict[str, list[CleanTransaction]] = {}
    for t in transactions:
        by_award.setdefault(t.award_id_piid, []).append(t)

    flagged: set[str] = set()
    for award_id, txns in by_award.items():
        by_date: dict[str, list[CleanTransaction]] = {}
        for t in txns:
            by_date.setdefault(t.action_date.isoformat(), []).append(t)
        for date_key, day_txns in by_date.items():
            if len(day_txns) < 2:
                continue
            for i, a in enumerate(day_txns):
                for b in day_txns[i + 1:]:
                    if abs(a.transaction_obligated_amount + b.transaction_obligated_amount) < 0.01 and (
                        a.transaction_obligated_amount != 0
                    ):
                        flagged.add(a.transaction_id)
                        flagged.add(b.transaction_id)
    return flagged


def net_obligations(transactions: list[CleanTransaction]) -> float:
    return sum(t.transaction_obligated_amount for t in transactions)


def gross_positive_obligations(transactions: list[CleanTransaction]) -> float:
    return sum(t.transaction_obligated_amount for t in transactions if t.transaction_obligated_amount > 0)


def gross_deobligations(transactions: list[CleanTransaction]) -> float:
    """Absolute magnitude of negative (deobligation) transactions."""
    return sum(-t.transaction_obligated_amount for t in transactions if t.transaction_obligated_amount < 0)


def deobligation_rate(transactions: list[CleanTransaction]) -> float:
    gross = gross_positive_obligations(transactions)
    if gross <= 0:
        return 0.0
    return gross_deobligations(transactions) / gross


def transaction_activity(transactions: list[CleanTransaction]) -> float:
    return sum(abs(t.transaction_obligated_amount) for t in transactions)
