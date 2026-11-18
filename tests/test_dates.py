from datetime import date

import pytest
from synthbiz import dates as synth_dates

from ledgercheck import dates


@pytest.mark.parametrize("year", range(2021, 2101))
def test_matches_synthbiz(year: int) -> None:
    assert dates.holidays(year) == synth_dates.holidays(year)


def test_saturday_holiday_is_observed_on_friday() -> None:
    assert date(2021, 7, 4).weekday() == 6
    assert date(2021, 7, 5) in dates.holidays(2021)
    assert date(2020, 7, 4).weekday() == 5
    assert date(2020, 7, 3) in dates.holidays(2020)


def test_new_year_on_saturday_is_observed_in_previous_year() -> None:
    assert date(2022, 1, 1).weekday() == 5
    assert date(2021, 12, 31) in dates.holidays(2021)
    assert date(2022, 1, 1) not in dates.holidays(2022)


def test_juneteenth_starts_in_2021() -> None:
    names_2020 = dates.holidays(2020).values()
    assert "Juneteenth" not in names_2020
    assert "Juneteenth" in dates.holidays(2021).values()


def test_holiday_name() -> None:
    assert dates.holiday_name(date(2025, 12, 25)) == "Christmas Day"
    assert dates.holiday_name(date(2025, 12, 26)) is None
    assert dates.holiday_name(date(2025, 12, 26), [date(2025, 12, 26)]) is not None
    assert dates.holiday_name(date(2025, 12, 25), us_holidays=False) is None
