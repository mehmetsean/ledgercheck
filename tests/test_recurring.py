import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from helpers import invoice, ledger, payment
from ledgercheck.config import load_settings
from ledgercheck.duplicates import find_duplicates
from ledgercheck.models import DuplicateSettings, Ledger, Vendor

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import measure_recurring  # noqa: E402

START = date(2025, 3, 3)


def weekly(count: int, gap: int = 7, extra: list[int] | None = None) -> Ledger:
    inv, pay = [], []
    days = [i * gap for i in range(count)] + (extra or [])
    for i, off in enumerate(days):
        day = START + timedelta(days=off)
        inv.append(invoice(f"I{i}", "V1", f"FR-{100 + i}", day, 5000))
        pay.append(payment(f"P{i}", "V1", f"I{i}", day, 5000))
    return ledger(invoices=inv, payments=pay, vendors=[Vendor("V1", "Cedar Plastics")])


def fuzzy(data: Ledger, minimum: int) -> set[str]:
    got = find_duplicates(data, DuplicateSettings(recurring_min_count=minimum))
    return {f.unit_id for f in got.flags if f.rule == "duplicate_fuzzy"}


def test_default_is_off() -> None:
    assert DuplicateSettings().recurring_min_count == 0
    assert len(fuzzy(weekly(5), 0)) == 4


def test_weekly_series_is_skipped() -> None:
    assert fuzzy(weekly(5), 3) == set()


def test_series_shorter_than_minimum_is_kept() -> None:
    assert len(fuzzy(weekly(2), 3)) == 1


def test_copy_inside_a_series_is_still_flagged() -> None:
    data = weekly(5, extra=[2])
    assert "P5" in fuzzy(data, 3)


def test_other_amount_is_not_part_of_the_series() -> None:
    data = weekly(4)
    pay = list(data.payments or ())
    pay.append(payment("P9", "V1", "I0", START + timedelta(days=3), 7000))
    assert (
        fuzzy(
            ledger(
                invoices=list(data.invoices or ()),
                payments=pay,
                vendors=list(data.vendors or ()),
            ),
            3,
        )
        == set()
    )


def test_series_of_exactly_the_minimum_is_skipped() -> None:
    assert fuzzy(weekly(3), 3) == set()
    assert fuzzy(weekly(3), 4) != set()


def test_extra_payment_on_a_series_day_is_flagged() -> None:
    assert fuzzy(weekly(5, extra=[7]), 3) != set()


def test_same_day_payments_do_not_raise() -> None:
    assert fuzzy(weekly(3, gap=0), 3) != set()


def test_other_vendor_on_cadence_is_flagged() -> None:
    data = weekly(4)
    inv = list(data.invoices or ())
    pay = list(data.payments or ())
    day = START + timedelta(days=28)
    inv.append(invoice("I9", "V2", "FR-109", day, 5000))
    pay.append(payment("P9", "V2", "I9", day, 5000))
    vendors = [*(data.vendors or ()), Vendor("V2", "Cedar Plastics")]
    other = ledger(invoices=inv, payments=pay, vendors=vendors)
    assert "P9" in fuzzy(other, 3)


@given(st.integers(2, 8), st.integers(1, 14), st.integers(0, 6))
def test_setting_never_adds_flags(count: int, gap: int, extra: int) -> None:
    data = weekly(count, gap, [extra])
    assert fuzzy(data, 3) <= fuzzy(data, 0)
    assert fuzzy(data, 2) <= fuzzy(data, 0)


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "s.json"
    path.write_text(text)
    return path


def test_setting_file(tmp_path: Path) -> None:
    assert load_settings(write(tmp_path, "{}")).duplicates.recurring_min_count == 0
    text = '{"duplicates": {"recurring_min_count": 3}}'
    assert load_settings(write(tmp_path, text)).duplicates.recurring_min_count == 3


@pytest.mark.parametrize("bad", ["-1", "1", "1.5", '"3"', "true", "null"])
def test_setting_file_rejects(tmp_path: Path, bad: str) -> None:
    text = f'{{"duplicates": {{"recurring_min_count": {bad}}}}}'
    with pytest.raises(ValueError, match="recurring_min_count"):
        load_settings(write(tmp_path, text))


def test_measure_script_table(capsys: pytest.CaptureFixture[str]) -> None:
    assert measure_recurring.main(["--seeds", "42", "--minimums", "0,3"]) == 0
    out = capsys.readouterr().out
    assert "| 0 | 87 | 46 | 41 | 0.5287 | 0.8679 |" in out
    assert "| 3 | 50 | 46 | 4 | 0.9200 | 0.8679 |" in out


@pytest.mark.parametrize("minimums", ["1", "-1", "x", "1,,2", ""])
def test_measure_script_bad_minimums(minimums: str) -> None:
    with pytest.raises(SystemExit) as e:
        measure_recurring.main(["--minimums", minimums])
    assert e.value.code == 2
