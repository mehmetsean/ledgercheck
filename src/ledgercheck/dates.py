"""US federal holidays by rule, no outside list."""

from collections.abc import Iterable
from datetime import date, timedelta

WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        last = date(year, 12, 31)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(d: date) -> date:
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def _rules(year: int) -> list[tuple[date, str]]:
    return [
        (_observed(date(year, 1, 1)), "New Year's Day"),
        (_nth_weekday(year, 1, 0, 3), "Martin Luther King Jr. Day"),
        (_nth_weekday(year, 2, 0, 3), "Washington's Birthday"),
        (_last_weekday(year, 5, 0), "Memorial Day"),
        (_observed(date(year, 6, 19)), "Juneteenth"),
        (_observed(date(year, 7, 4)), "Independence Day"),
        (_nth_weekday(year, 9, 0, 1), "Labor Day"),
        (_nth_weekday(year, 10, 0, 2), "Columbus Day"),
        (_observed(date(year, 11, 11)), "Veterans Day"),
        (_nth_weekday(year, 11, 3, 4), "Thanksgiving Day"),
        (_observed(date(year, 12, 25)), "Christmas Day"),
    ]


def holidays(year: int) -> dict[date, str]:
    """Observed US federal holidays that fall in the given year."""
    out: dict[date, str] = {}
    for y in (year - 1, year, year + 1):
        if y < 1 or y > 9998:
            continue
        for d, name in _rules(y):
            if d.year == year:
                out[d] = name
    return dict(sorted(out.items()))


def holiday_name(
    d: date, extra: Iterable[date] = (), us_holidays: bool = True
) -> str | None:
    """Name of the holiday on d, or None."""
    if us_holidays:
        name = holidays(d.year).get(d)
        if name:
            return name
    if d in set(extra):
        return "a listed holiday"
    return None
