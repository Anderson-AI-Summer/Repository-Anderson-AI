"""Federal fiscal year helpers.

The U.S. federal fiscal year runs October 1 (previous calendar year) through
September 30. FY2020 = 2019-10-01 .. 2020-09-30.
"""
from __future__ import annotations

import datetime as dt


def federal_fiscal_year(date: dt.date | dt.datetime | str) -> int:
    """Return the federal fiscal year for a calendar date.

    Oct/Nov/Dec belong to the *next* calendar year's fiscal year.
    """
    if isinstance(date, str):
        date = dt.date.fromisoformat(date[:10])
    if isinstance(date, dt.datetime):
        date = date.date()
    return date.year + 1 if date.month >= 10 else date.year


def fiscal_year_bounds(fy: int) -> tuple[dt.date, dt.date]:
    """Return (start, end) calendar dates for a given federal fiscal year."""
    return dt.date(fy - 1, 10, 1), dt.date(fy, 9, 30)


def current_fiscal_year(today: dt.date | None = None) -> int:
    today = today or dt.date.today()
    return federal_fiscal_year(today)


def is_partial_fiscal_year(fy: int, today: dt.date | None = None) -> bool:
    """True if `fy` is still in progress as of `today` (i.e. the current FY)."""
    today = today or dt.date.today()
    return fy == current_fiscal_year(today)


def fiscal_year_to_date_bounds(fy: int, today: dt.date | None = None) -> tuple[dt.date, dt.date]:
    """Return (start, min(end, today)) -- useful for comparable YTD views."""
    today = today or dt.date.today()
    start, end = fiscal_year_bounds(fy)
    if end > today:
        end = today
    return start, end
