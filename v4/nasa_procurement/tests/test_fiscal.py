import datetime as dt

from src.fiscal import (
    current_fiscal_year,
    federal_fiscal_year,
    fiscal_year_bounds,
    fiscal_year_to_date_bounds,
    is_partial_fiscal_year,
)


def test_october_starts_next_fiscal_year():
    assert federal_fiscal_year(dt.date(2019, 10, 1)) == 2020


def test_september_ends_current_fiscal_year():
    assert federal_fiscal_year(dt.date(2020, 9, 30)) == 2020


def test_mid_calendar_year():
    assert federal_fiscal_year(dt.date(2020, 3, 15)) == 2020


def test_accepts_iso_string():
    assert federal_fiscal_year("2019-10-01") == 2020


def test_fiscal_year_bounds():
    start, end = fiscal_year_bounds(2020)
    assert start == dt.date(2019, 10, 1)
    assert end == dt.date(2020, 9, 30)


def test_partial_year_labeling_current_fy_is_partial():
    today = dt.date(2020, 3, 1)
    assert is_partial_fiscal_year(2020, today) is True
    assert is_partial_fiscal_year(2019, today) is False


def test_fiscal_year_to_date_bounds_caps_at_today():
    today = dt.date(2020, 3, 1)
    start, end = fiscal_year_to_date_bounds(2020, today)
    assert start == dt.date(2019, 10, 1)
    assert end == today


def test_current_fiscal_year():
    assert current_fiscal_year(dt.date(2019, 10, 1)) == 2020
