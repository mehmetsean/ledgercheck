import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from helpers import invoice, ledger, payment
from ledgercheck.config import load_settings
from ledgercheck.duplicates import find_duplicates, fuzzy_pairs_all, is_sequence
from ledgercheck.models import DuplicateSettings, Ledger, Vendor

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import measure_sequence  # noqa: E402

DAY = date(2025, 3, 3)


def two(first: str, second: str, gap: int = 5) -> Ledger:
    later = DAY + timedelta(days=gap)
    return ledger(
        invoices=[
            invoice("I1", "V1", first, DAY, 5000),
            invoice("I2", "V1", second, later, 5000),
        ],
        payments=[
            payment("P1", "V1", "I1", DAY, 5000),
            payment("P2", "V1", "I2", later, 5000),
        ],
        vendors=[Vendor("V1", "Cedar Plastics")],
    )


def fuzzy(data: Ledger, step: int) -> set[str]:
    got = find_duplicates(data, DuplicateSettings(sequence_max_step=step))
    return {f.unit_id for f in got.flags if f.rule == "duplicate_fuzzy"}


def test_default_is_off() -> None:
    assert DuplicateSettings().sequence_max_step == 0
    assert fuzzy(two("INV-1001", "INV-1002"), 0) == {"P2"}


def test_next_number_is_skipped() -> None:
    assert fuzzy(two("INV-1001", "INV-1002"), 1) == set()


def test_step_larger_than_setting_is_kept() -> None:
    assert fuzzy(two("INV-1001", "INV-1003"), 1) == {"P2"}
    assert fuzzy(two("INV-1001", "INV-1003"), 2) == set()


def test_order_does_not_matter() -> None:
    assert fuzzy(two("INV-1002", "INV-1001"), 1) == set()


def test_different_prefix_is_kept() -> None:
    assert fuzzy(two("INVOICE-1001", "INVOICF-1002"), 5) == {"P2"}


def test_adjacent_swap_typo_is_kept_at_a_small_step() -> None:
    assert fuzzy(two("INVOICE-1012", "INVOICE-1021"), 2) == {"P2"}


def test_same_number_is_not_a_sequence() -> None:
    assert is_sequence("inv1001", "inv1001", 5) is False


def test_no_digits_is_not_a_sequence() -> None:
    assert is_sequence("abc", "abd", 5) is False
    assert is_sequence("abc1", "abc", 5) is False


def test_digit_width_change() -> None:
    assert is_sequence("inv999", "inv1000", 1) is True


def test_superscript_digits_do_not_raise() -> None:
    assert is_sequence("inv1\u00b2", "inv1\u00b3", 2) is False
    assert fuzzy(two("INVOICE-1\u00b2", "INVOICE-1\u00b3"), 2) == {"P2"}


def test_very_long_digit_run_does_not_raise() -> None:
    long = "inv" + "9" * 5000
    assert is_sequence(long, long[:-1] + "8", 2) is False


def test_zero_turns_it_off() -> None:
    assert is_sequence("inv1", "inv2", 0) is False


@given(st.text("abc12", max_size=6), st.text("abc12", max_size=6), st.integers(0, 5))
def test_is_sequence_is_symmetric(x: str, y: str, step: int) -> None:
    assert is_sequence(x, y, step) == is_sequence(y, x, step)


@given(st.integers(1, 5000), st.integers(1, 9), st.integers(1, 9))
def test_property_step_inside_limit(n: int, step: int, limit: int) -> None:
    x, y = f"inv{n}", f"inv{n + step}"
    assert is_sequence(x, y, limit) == (step <= limit)


@given(st.integers(1, 5000), st.integers(1, 9), st.integers(0, 6))
def test_setting_never_adds_flags(n: int, step: int, limit: int) -> None:
    data = two(f"INV-{n}", f"INV-{n + step}")
    assert fuzzy(data, limit) <= fuzzy(data, 0)


def test_reference_agrees_with_blocked_search() -> None:
    data = two("INV-1001", "INV-1002")
    s = DuplicateSettings(sequence_max_step=1)
    assert fuzzy_pairs_all(data, s) == []
    assert fuzzy_pairs_all(data, DuplicateSettings()) != []


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "s.json"
    path.write_text(text)
    return path


def test_setting_file(tmp_path: Path) -> None:
    assert load_settings(write(tmp_path, "{}")).duplicates.sequence_max_step == 0
    text = '{"duplicates": {"sequence_max_step": 2}}'
    assert load_settings(write(tmp_path, text)).duplicates.sequence_max_step == 2


@pytest.mark.parametrize("bad", ["-1", "1.5", '"2"', "true", "null"])
def test_setting_file_rejects(tmp_path: Path, bad: str) -> None:
    text = f'{{"duplicates": {{"sequence_max_step": {bad}}}}}'
    with pytest.raises(ValueError, match="sequence_max_step"):
        load_settings(write(tmp_path, text))


def test_measure_script_table(capsys: pytest.CaptureFixture[str]) -> None:
    assert measure_sequence.main(["--seeds", "42", "--steps", "0,2"]) == 0
    out = capsys.readouterr().out
    assert "| 0 | 87 | 46 | 41 | 0.5287 | 0.8679 |" in out
    assert "| 2 | 46 | 46 | 0 | 1.0000 | 0.8679 |" in out


def test_measure_script_rejects_bad_steps() -> None:
    with pytest.raises(SystemExit):
        measure_sequence.main(["--steps", "-1"])
