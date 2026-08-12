"""Raw USAspending records -> CleanTransaction.

Two raw sources are merged per transaction:
  1. the transaction-search row (per-transaction: date, amount, mod, recipient...)
  2. the award-detail row (per-award, broadcast onto every transaction that
     belongs to that award: parent award, DUNS, period of performance,
     extent competed, pricing type, set-aside, offers received...)

Award-detail reflects the award's *latest* known state, not necessarily its
state at the time of each individual transaction -- this is documented
because USAspending does not expose point-in-time award snapshots per
transaction through this API.
"""
from __future__ import annotations

import datetime as dt
import logging

from src.fiscal import federal_fiscal_year
from src.schema import CleanTransaction

logger = logging.getLogger("clean")


def _parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


def _clean_str(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s and s.upper() not in {"NONE", "NULL", "N/A", ""} else None


def _to_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def clean_transaction(raw_txn: dict, award_detail: dict | None) -> tuple[CleanTransaction | None, list[str]]:
    """Map one raw transaction (+ optional award detail) to a CleanTransaction.

    Returns (clean_transaction_or_None, data_quality_flags). Returns None
    only if the record is unusable (missing action date or award id) --
    these are logged and excluded, never silently dropped without a flag.
    """
    flags: list[str] = []

    action_date = _parse_date(raw_txn.get("Action Date"))
    award_id = _clean_str(raw_txn.get("Award ID"))
    if action_date is None or award_id is None:
        return None, ["missing_required_field:action_date_or_award_id"]

    amount = _to_float(raw_txn.get("Transaction Amount"))
    if amount is None:
        flags.append("missing_transaction_amount")
        amount = 0.0

    recipient_name = _clean_str(raw_txn.get("Recipient Name")) or "UNKNOWN RECIPIENT"
    if recipient_name == "UNKNOWN RECIPIENT":
        flags.append("missing_recipient_name")

    transaction_id = _clean_str(raw_txn.get("internal_id")) or (
        f"{award_id}|{raw_txn.get('Mod')}|{raw_txn.get('Action Date')}|{amount}"
    )

    ad = award_detail or {}
    parent_award = (ad.get("parent_award") or {}) if ad else {}
    recipient_detail = (ad.get("recipient") or {}) if ad else {}
    recipient_loc = (recipient_detail.get("location") or {}) if recipient_detail else {}
    pop_detail = (ad.get("period_of_performance") or {}) if ad else {}
    contract_data = (ad.get("latest_transaction_contract_data") or {}) if ad else {}
    awarding_agency_detail = (ad.get("awarding_agency") or {}) if ad else {}
    funding_agency_detail = (ad.get("funding_agency") or {}) if ad else {}

    if award_detail is None:
        flags.append("award_detail_unavailable")

    pop_state = raw_txn.get("Primary Place of Performance") or {}
    recip_loc_field = raw_txn.get("Recipient Location") or {}

    clean = CleanTransaction(
        transaction_id=transaction_id,
        award_id_piid=award_id,
        parent_award_id=_clean_str(parent_award.get("piid")),
        generated_award_id=_clean_str(raw_txn.get("generated_internal_id")),
        modification_number=_clean_str(raw_txn.get("Mod")),
        action_date=action_date,
        fiscal_year=federal_fiscal_year(action_date),
        action_type_code=_clean_str(raw_txn.get("Action Type")),
        action_type_description=_clean_str(raw_txn.get("Action Type")),
        transaction_description=_clean_str(raw_txn.get("Transaction Description")),
        transaction_obligated_amount=amount,
        recipient_name_raw=recipient_name,
        recipient_uei=_clean_str(raw_txn.get("Recipient UEI")) or _clean_str(recipient_detail.get("recipient_uei")),
        recipient_duns=_clean_str(recipient_detail.get("recipient_unique_id")),
        parent_recipient_name=_clean_str(recipient_detail.get("parent_recipient_name")),
        parent_recipient_uei=_clean_str(recipient_detail.get("parent_recipient_uei")),
        parent_recipient_duns=_clean_str(recipient_detail.get("parent_recipient_unique_id")),
        recipient_location_city=_clean_str(recipient_loc.get("city_name")) or _clean_str(recip_loc_field.get("city_name") if isinstance(recip_loc_field, dict) else None),
        recipient_location_state=_clean_str(recipient_loc.get("state_code")) or _clean_str(recip_loc_field.get("state_code") if isinstance(recip_loc_field, dict) else None),
        recipient_location_country=_clean_str(recipient_loc.get("country_name")),
        awarding_agency=_clean_str(raw_txn.get("Awarding Agency")) or _clean_str((awarding_agency_detail.get("toptier_agency") or {}).get("name")),
        awarding_subagency=_clean_str(raw_txn.get("Awarding Sub Agency")) or _clean_str((awarding_agency_detail.get("subtier_agency") or {}).get("name")),
        awarding_office=_clean_str(awarding_agency_detail.get("office_agency_name")),
        funding_agency=_clean_str(raw_txn.get("Funding Agency")) or _clean_str((funding_agency_detail.get("toptier_agency") or {}).get("name")),
        funding_subagency=_clean_str(raw_txn.get("Funding Sub Agency")) or _clean_str((funding_agency_detail.get("subtier_agency") or {}).get("name")),
        award_type_code=_clean_str(ad.get("type")),
        award_type_description=_clean_str(raw_txn.get("Award Type")) or _clean_str(ad.get("type_description")),
        psc_code=_clean_str(raw_txn.get("product_or_service_code")) or _clean_str(contract_data.get("product_or_service_code")),
        psc_description=_clean_str(raw_txn.get("product_or_service_description")) or _clean_str(contract_data.get("product_or_service_description")),
        naics_code=_clean_str(raw_txn.get("naics_code")) or _clean_str(contract_data.get("naics")),
        naics_description=_clean_str(raw_txn.get("naics_description")) or _clean_str(contract_data.get("naics_description")),
        period_of_performance_start=_parse_date(pop_detail.get("start_date")),
        period_of_performance_current_end=_parse_date(pop_detail.get("end_date")),
        place_of_performance_city=_clean_str(raw_txn.get("pop_city_name")),
        place_of_performance_state=_clean_str(raw_txn.get("pop_state_code")),
        place_of_performance_country=_clean_str(raw_txn.get("pop_country_name")),
        current_award_amount=_to_float(ad.get("total_obligation")),
        potential_award_amount=_to_float(ad.get("base_and_all_options")),
        extent_competed=_clean_str(contract_data.get("extent_competed")),
        extent_competed_description=_clean_str(contract_data.get("extent_competed_description")),
        contract_pricing_type=_clean_str(contract_data.get("type_of_contract_pricing")),
        contract_pricing_type_description=_clean_str(contract_data.get("type_of_contract_pricing_description")),
        set_aside_type=_clean_str(contract_data.get("type_set_aside")),
        set_aside_type_description=_clean_str(contract_data.get("type_set_aside_description")),
        number_of_offers_received=_to_int(contract_data.get("number_of_offers_received")),
        award_detail_available=award_detail is not None,
    )
    return clean, flags


def deduplicate(transactions: list[CleanTransaction]) -> tuple[list[CleanTransaction], int]:
    """Drop exact-duplicate transaction_id rows, keeping the first occurrence."""
    seen: set[str] = set()
    out: list[CleanTransaction] = []
    duplicates = 0
    for t in transactions:
        if t.transaction_id in seen:
            duplicates += 1
            continue
        seen.add(t.transaction_id)
        out.append(t)
    return out, duplicates
