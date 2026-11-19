import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from helpers import ledger, line
from ledgercheck.config import load_settings
from ledgercheck.models import JournalLine, Settings
from ledgercheck.rules import run_rules

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import measure_round_series  # noqa: E402


def entry(je: str, month: int, debit: int, account: str = "6200") -> JournalLine:
    return replace(
        line(je=je, day=date(2025, month, 10), debit=debit), account_id=account
    )


def flagged(lines: list[JournalLine], minimum: int) -> set[str]:
    settings = Settings(round_recurring_min_months=minimum)
    found = run_rules(ledger(lines=lines), settings)
    return {f.unit_id for f in found if f.rule == "round_amount"}


def rent(months: int) -> list[JournalLine]:
    return [entry(f"R{m}", m, 400_000) for m in range(1, months + 1)]


def test_default_is_zero() -> None:
    assert Settings().round_recurring_min_months == 0
    assert flagged(rent(4), 0) == {"R1", "R2", "R3", "R4"}


def test_series_is_skipped_at_the_minimum() -> None:
    assert flagged(rent(3), 3) == set()
    assert flagged(rent(2), 3) == {"R1", "R2"}


def test_other_total_or_account_is_still_flagged() -> None:
    lines = rent(4) + [entry("X1", 5, 700_000), entry("X2", 6, 400_000, "6900")]
    assert flagged(lines, 3) == {"X1", "X2"}


def test_same_month_twice_is_not_a_series() -> None:
    lines = [entry("A", 3, 400_000), entry("B", 3, 400_000), entry("C", 3, 400_000)]
    assert flagged(lines, 2) == {"A", "B", "C"}


def test_same_month_of_two_years_is_two_months() -> None:
    a = line(je="A", day=date(2024, 3, 5), debit=400_000)
    b = line(je="B", day=date(2025, 3, 5), debit=400_000)
    assert flagged([a, b], 2) == set()


def test_non_round_entries_are_untouched() -> None:
    lines = [entry(f"N{m}", m, 123_456) for m in range(1, 5)]
    assert flagged(lines, 2) == set()


def test_non_ascii_and_odd_accounts() -> None:
    for account in ("6200é", "財務", "", " 6200 ", "a" * 500):
        lines = [entry(f"E{m}", m, 400_000, account) for m in range(1, 4)]
        assert flagged(lines, 3) == set()
        assert flagged(lines, 0) == {"E1", "E2", "E3"}


def test_empty_and_huge() -> None:
    assert flagged([], 2) == set()
    big = [entry(f"H{m}", m, 10**15) for m in range(1, 4)]
    assert flagged(big, 3) == set()


def test_multi_line_entry_key_uses_debit_accounts() -> None:
    def pair(je: str, month: int, account: str) -> list[JournalLine]:
        d = replace(entry(je, month, 400_000), line_id=f"{je}-1")
        c = replace(
            entry(je, month, 0, account), credit_cents=400_000, line_id=f"{je}-2"
        )
        return [d, c]

    lines = pair("A", 1, "2000") + pair("B", 2, "2100") + pair("C", 3, "2000")
    assert flagged(lines, 3) == set()


@given(
    st.lists(
        st.tuples(
            st.integers(min_value=1, max_value=12),
            st.integers(min_value=0, max_value=20),
            st.sampled_from(["6200", "6900", "ü"]),
        ),
        max_size=30,
    ),
    st.integers(min_value=2, max_value=12),
)
def test_setting_never_adds_flags(
    rows: list[tuple[int, int, str]], minimum: int
) -> None:
    lines = [entry(f"J{i}", m, k * 100_000, a) for i, (m, k, a) in enumerate(rows)]
    assert flagged(lines, minimum) <= flagged(lines, 0)


@given(
    st.lists(st.integers(min_value=1, max_value=12), min_size=1, max_size=12),
    st.integers(min_value=2, max_value=12),
)
def test_series_rule_matches_month_count(months: list[int], minimum: int) -> None:
    lines = [entry(f"J{i}", m, 400_000) for i, m in enumerate(months)]
    expect = set() if len(set(months)) >= minimum else {x.je_id for x in lines}
    assert flagged(lines, minimum) == expect


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "s.json"
    path.write_text(text)
    return path


def test_setting_file(tmp_path: Path) -> None:
    assert load_settings(write(tmp_path, "{}")).round_recurring_min_months == 0
    got = load_settings(write(tmp_path, '{"round_recurring_min_months": 4}'))
    assert got.round_recurring_min_months == 4


@pytest.mark.parametrize("bad", ["-1", "1", "1.5", '"3"', "true", "null", 10**16])
def test_setting_file_rejects(tmp_path: Path, bad: object) -> None:
    with pytest.raises(ValueError, match="round_recurring_min_months"):
        load_settings(write(tmp_path, f'{{"round_recurring_min_months": {bad}}}'))


def test_measure_script_table(capsys: pytest.CaptureFixture[str]) -> None:
    assert measure_round_series.main(["--seeds", "42", "--minimums", "0,4"]) == 0
    out = capsys.readouterr().out
    assert "| 0 | 62 | 26 | 36 | 0.4194 | 1.0000 |" in out
    assert "| 4 | 25 | 24 | 1 | 0.9600 | 0.9231 |" in out


@pytest.mark.parametrize("minimums", ["1", "-1", "x", "1,,2", "", "1001"])
def test_measure_script_bad_minimums(minimums: str) -> None:
    with pytest.raises(SystemExit) as e:
        measure_round_series.main(["--minimums", minimums])
    assert e.value.code == 2


def test_measure_script_show() -> None:
    assert measure_round_series.show(None) == "n/a"
    assert measure_round_series.show(0.5) == "0.5000"


def test_two_lines_on_one_account_match_across_months() -> None:
    def pair(je: str, month: int) -> list[JournalLine]:
        return [entry(je, month, 200_000), entry(je, month, 200_000)]

    assert flagged(pair("A", 1) + pair("B", 2), 2) == set()


def test_entry_month_comes_from_the_first_line() -> None:
    first = entry("A", 1, 400_000)
    second = replace(entry("A", 1, 0), posting_date=date(2025, 2, 10))
    other = entry("B", 2, 400_000)
    assert flagged([first, second, other], 2) == set()
