import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from helpers import ledger, line
from ledgercheck.config import load_settings
from ledgercheck.models import Settings
from ledgercheck.rules import run_rules

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import measure_close_window  # noqa: E402


def mismatch(day: date, period: str, window: int) -> set[str]:
    found = run_rules(
        ledger(lines=[line(je="JE-1", day=day, period=period)]),
        Settings(close_window_days=window),
    )
    return {f.unit_id for f in found if f.rule == "period_mismatch"}


def test_default_is_zero() -> None:
    assert Settings().close_window_days == 0
    assert mismatch(date(2025, 3, 1), "2025-02", 0) == {"JE-1"}


def test_boundary_day() -> None:
    assert mismatch(date(2025, 3, 3), "2025-02", 3) == set()
    assert mismatch(date(2025, 3, 4), "2025-02", 3) == {"JE-1"}


def test_only_previous_period() -> None:
    assert mismatch(date(2025, 3, 2), "2025-01", 5) == {"JE-1"}
    assert mismatch(date(2025, 3, 2), "2025-04", 5) == {"JE-1"}
    assert mismatch(date(2025, 3, 2), "2024-02", 5) == {"JE-1"}


def test_january_uses_december() -> None:
    assert mismatch(date(2025, 1, 2), "2024-12", 2) == set()
    assert mismatch(date(2025, 1, 2), "2025-12", 2) == {"JE-1"}


def test_window_of_one_covers_first_only() -> None:
    assert mismatch(date(2025, 3, 1), "2025-02", 1) == set()
    assert mismatch(date(2025, 3, 2), "2025-02", 1) == {"JE-1"}


@given(
    st.dates(min_value=date(2001, 1, 1), max_value=date(2040, 12, 31)),
    st.integers(min_value=0, max_value=31),
)
def test_window_never_adds_flags(day: date, window: int) -> None:
    first = day.replace(day=1)
    prev = (first - timedelta(days=1)).strftime("%Y-%m")
    for period in (prev, day.strftime("%Y-%m")):
        wide = mismatch(day, period, window)
        assert wide <= mismatch(day, period, 0)
    expect = set() if day.day <= window else {"JE-1"}
    assert mismatch(day, prev, window) == expect


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "s.json"
    path.write_text(text)
    return path


def test_setting_file(tmp_path: Path) -> None:
    assert load_settings(write(tmp_path, "{}")).close_window_days == 0
    got = load_settings(write(tmp_path, '{"close_window_days": 5}'))
    assert got.close_window_days == 5
    assert load_settings(write(tmp_path, '{"close_window_days": 31}'))


@pytest.mark.parametrize("bad", ["-1", "32", "1.5", '"3"', "true", "null"])
def test_setting_file_rejects(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError, match="close_window_days"):
        load_settings(write(tmp_path, f'{{"close_window_days": {bad}}}'))


def test_measure_script_table(capsys: pytest.CaptureFixture[str]) -> None:
    assert measure_close_window.main(["--seeds", "42", "--windows", "0,5"]) == 0
    out = capsys.readouterr().out
    assert "| 0 | 48 | 26 | 22 | 0.5417 | 1.0000 |" in out
    assert "| 5 | 26 | 26 | 0 | 1.0000 | 1.0000 |" in out


@pytest.mark.parametrize("windows", ["32", "-1", "x", "1,,2", ""])
def test_measure_script_bad_windows(windows: str) -> None:
    with pytest.raises(SystemExit) as e:
        measure_close_window.main(["--windows", windows])
    assert e.value.code == 2


def test_measure_script_show() -> None:
    assert measure_close_window.show(None) == "n/a"
    assert measure_close_window.show(0.5) == "0.5000"
