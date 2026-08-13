"""Thin, resilient client for the public USAspending.gov API.

Two endpoints are used:

- ``/api/v2/search/spending_by_transaction/`` -- paginated transaction-level
  search. Fast and reliable, but has a narrower field set.
- ``/api/v2/awards/<generated_id>/`` -- full award-level detail (PIID,
  parent award, recipient UEI/DUNS, period of performance, extent competed,
  pricing type, set-aside, offers received, etc). One unique award can cover
  many transactions, so results are cached on disk and only fetched once per
  award per run.

The bulk async download endpoint (``/api/v2/download/transactions/``) was
evaluated and is documented in README.md as a known-flaky alternative in
this environment (jobs intermittently fail with a generic "An error
occurred" after ~40s); the paginated search + award-detail join above is
used as the primary, reliable ingestion path instead.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Iterator

import httpx

from src.config import USASPENDING_BASE_URL

logger = logging.getLogger("usaspending_client")

MAX_RETRIES = 5
BACKOFF_BASE_SECONDS = 1.5
TIMEOUT_SECONDS = 30.0
PAGE_LIMIT = 100


class USASpendingError(RuntimeError):
    pass


def _request_with_retries(client: httpx.Client, method: str, url: str, **kwargs: Any) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.request(method, url, **kwargs)
            if resp.status_code == 429:
                wait = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                logger.warning("Rate limited (429), backing off %.1fs (attempt %d/%d)", wait, attempt, MAX_RETRIES)
                time.sleep(wait)
                continue
            if resp.status_code >= 500:
                wait = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                logger.warning("Server error %d, backing off %.1fs (attempt %d/%d)", resp.status_code, wait, attempt, MAX_RETRIES)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            wait = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
            logger.warning("Transient error %s, backing off %.1fs (attempt %d/%d)", exc, wait, attempt, MAX_RETRIES)
            time.sleep(wait)
    raise USASpendingError(f"Request to {url} failed after {MAX_RETRIES} attempts: {last_exc}")


TRANSACTION_FIELDS = [
    "Action Date", "Action Type", "Award ID", "Award Type", "Awarding Agency",
    "Awarding Sub Agency", "Funding Agency", "Funding Sub Agency",
    "Issued Date", "Mod", "naics_code", "naics_description",
    "pop_city_name", "pop_country_name", "pop_state_code",
    "product_or_service_code", "product_or_service_description",
    "recipient_id", "recipient_location_city_name",
    "recipient_location_country_name", "recipient_location_state_code",
    "Recipient Name", "Recipient UEI", "Transaction Amount",
    "Transaction Description", "generated_internal_id", "internal_id",
]


def iter_nasa_transactions(
    start_date: str,
    end_date: str,
    award_type_codes: list[str],
    agency_name: str,
    page_limit: int = PAGE_LIMIT,
    max_records: int | None = None,
) -> Iterator[dict]:
    """Yield raw transaction dicts from spending_by_transaction, paginated.

    Handles pagination, bounded retries with backoff, empty/malformed
    responses, and an optional hard record cap (sample mode only -- pass
    ``max_records=None`` for a real full refresh).
    """
    url = f"{USASPENDING_BASE_URL}/api/v2/search/spending_by_transaction/"
    page = 1
    yielded = 0
    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        while True:
            body = {
                "filters": {
                    "award_type_codes": award_type_codes,
                    "time_period": [
                        {"start_date": start_date, "end_date": end_date, "date_type": "action_date"}
                    ],
                    "agencies": [{"type": "awarding", "tier": "toptier", "name": agency_name}],
                },
                "fields": TRANSACTION_FIELDS,
                "sort": "Action Date",
                "order": "desc",
                "page": page,
                "limit": page_limit,
            }
            resp = _request_with_retries(client, "POST", url, json=body)
            try:
                data = resp.json()
            except ValueError as exc:
                raise USASpendingError(f"Malformed JSON response on page {page}: {exc}") from exc

            results = data.get("results")
            if results is None:
                raise USASpendingError(f"Malformed response on page {page}: missing 'results' key")
            if not results:
                break

            for row in results:
                yield row
                yielded += 1
                if max_records is not None and yielded >= max_records:
                    return

            meta = data.get("page_metadata", {})
            if not meta.get("hasNext"):
                break
            page += 1


def fetch_award_detail(generated_internal_id: str) -> dict | None:
    """Fetch full award-level detail for one award. Returns None on 404."""
    url = f"{USASPENDING_BASE_URL}/api/v2/awards/{generated_internal_id}/"
    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        try:
            resp = _request_with_retries(client, "GET", url)
        except USASpendingError:
            raise
        if resp.status_code == 404:
            return None
        try:
            return resp.json()
        except ValueError:
            return None
