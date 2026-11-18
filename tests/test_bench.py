import sys
from datetime import date
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from helpers import invoice, ledger, payment
from ledgercheck.duplicates import DuplicatePair, find_duplicates, fuzzy_pairs_all
from ledgercheck.models import DuplicateSettings, Ledger, Vendor
from test_duplicates import payment_ledgers

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "benchmarks"))

import bench  # noqa: E402


def _two_payments() -> Ledger:
    return ledger(
        invoices=[
            invoice("I1", "V1", "A1", date(2025, 3, 3), 500),
            invoice("I2", "V2", "A1", date(2025, 3, 4), 500),
        ],
        payments=[
            payment("P1", "V1", "I1", date(2025, 3, 3), 500),
            payment("P2", "V2", "I2", date(2025, 3, 4), 500),
        ],
        vendors=[Vendor("V1", "Cedar Plastics Co"), Vendor("V2", "Cedar Plastic")],
    )


@settings(max_examples=150)
@given(
    payment_ledgers(),
    st.integers(0, 20),
    st.sampled_from([0.0, 0.5, 0.8]),
    st.sampled_from([0.0, 0.8]),
)
def test_blocked_pairs_equal_filtered_all_pairs_in_full(
    led: Ledger, window: int, name_cut: float, number_cut: float
) -> None:
    cfg = DuplicateSettings(
        window_days=window, name_threshold=name_cut, invoice_threshold=number_cut
    )
    blocked = [p for p in find_duplicates(led, cfg).pairs if p.kind == "fuzzy"]
    inside = [
        p for p in fuzzy_pairs_all(led, cfg) if p.same_amount and p.days_apart <= window
    ]
    assert sorted(blocked, key=lambda p: (p.later_id, p.earlier_id)) == sorted(
        inside, key=lambda p: (p.later_id, p.earlier_id)
    )


@settings(max_examples=60)
@given(payment_ledgers(), st.integers(0, 20))
def test_check_blocking_finds_nothing_missing(led: Ledger, window: int) -> None:
    cfg = DuplicateSettings(window_days=window, name_threshold=0.5)
    everything = fuzzy_pairs_all(led, cfg)
    total, left_out, other, late, missing = bench.check_blocking(led, cfg, everything)
    assert missing == []
    assert total == len(everything)
    assert left_out == other + late


def test_check_blocking_reports_a_pair_blocking_did_not_find() -> None:
    fake = DuplicatePair("fuzzy", "PX", "PY", 1.0, 1.0, 2, True, "made up")
    far = DuplicatePair("fuzzy", "PX", "PZ", 1.0, 1.0, 30, True, "made up")
    other = DuplicatePair("fuzzy", "PX", "PW", 1.0, 1.0, 1, False, "made up")
    led = _two_payments()
    cfg = DuplicateSettings()
    total, left_out, other_amount, late, missing = bench.check_blocking(
        led, cfg, [fake, far, other]
    )
    assert (total, left_out, other_amount, late) == (3, 2, 1, 1)
    assert missing == [fake]


def test_precision_and_recall_helper() -> None:
    assert bench.pr(3, 1, 1) == (0.75, 0.75)
    assert bench.pr(0, 0, 0) == (None, None)


def test_step_counter_counts_and_restores_the_meter() -> None:
    cfg = DuplicateSettings()
    original = bench.dup._Meter
    steps, result = bench.count_steps(lambda: find_duplicates(_two_payments(), cfg))
    assert steps > 0
    assert len(result.pairs) == 1
    assert bench.dup._Meter is original


class _Recorder(bench.dup._Meter):
    total = 0

    def add(self, cost: int) -> None:
        _Recorder.total += cost
        super().add(cost)


def test_count_steps_matches_the_real_meter_and_result() -> None:
    cfg = DuplicateSettings()
    led = _two_payments()
    original = bench.dup._Meter
    bench.dup._Meter = _Recorder  # type: ignore[misc]
    try:
        direct = find_duplicates(led, cfg)
    finally:
        bench.dup._Meter = original  # type: ignore[misc]
    steps, result = bench.count_steps(lambda: find_duplicates(led, cfg))
    assert result == direct
    assert steps == _Recorder.total


def test_count_steps_restores_the_meter_when_fn_raises() -> None:
    original = bench.dup._Meter

    def boom() -> None:
        raise RuntimeError("stop")

    with pytest.raises(RuntimeError):
        bench.count_steps(boom)
    assert bench.dup._Meter is original


def test_main_quick_writes_the_doc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "x.md"
    monkeypatch.setattr(sys, "argv", ["bench.py", "--quick", "--out", str(out)])
    assert bench.main() == 0
    text = out.read_text(encoding="utf-8")
    assert "missing from blocked fuzzy: 0." in text
    assert "This is a quick run (size small, 3 months, 1 run)" in text
    assert "## small, 3 months" in text


def test_main_returns_one_when_blocking_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = DuplicatePair("fuzzy", "PX", "PY", 1.0, 1.0, 2, True, "made up")
    monkeypatch.setattr(sys, "argv", ["bench.py", "--quick"])
    monkeypatch.setattr(bench, "check_blocking", lambda *a: (1, 0, 0, 0, [fake]))
    assert bench.main() == 1


def _scripted(monkeypatch: pytest.MonkeyPatch, times: list[float]) -> list[int]:
    calls: list[int] = []
    queue = iter(times)

    def fake(fn):  # type: ignore[no-untyped-def]
        calls.append(1)
        return next(queue), "r"

    monkeypatch.setattr(bench, "one_run", fake)
    return calls


def test_median_time_is_the_median(monkeypatch: pytest.MonkeyPatch) -> None:
    _scripted(monkeypatch, [3.0, 1.0, 2.0])
    seconds, runs, result = bench.median_time(lambda: None, 3)
    assert (seconds, runs, result) == (2.0, 3, "r")


def test_slow_mode_stops_after_the_first_run_over_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _scripted(monkeypatch, [bench.SLOW_SECONDS + 1, 1.0, 1.0])
    seconds, runs, _ = bench.median_time(lambda: None, 3, slow=True)
    assert (runs, len(calls)) == (1, 1)
    assert seconds == bench.SLOW_SECONDS + 1


def test_slow_mode_keeps_repeating_fast_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _scripted(monkeypatch, [1.0, 2.0, 3.0])
    assert bench.median_time(lambda: None, 3, slow=True)[1] == 3
    assert len(calls) == 3


@pytest.mark.parametrize("value", ["0", "-2"])
def test_repeat_must_be_positive(
    value: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["bench.py", "--repeat", value])
    with pytest.raises(SystemExit) as info:
        bench.main()
    assert info.value.code == 2
    assert "1 or more" in capsys.readouterr().err


def test_symlink_out_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "real.md"
    target.write_text("keep", encoding="utf-8")
    link = tmp_path / "link.md"
    link.symlink_to(target)
    monkeypatch.setattr(sys, "argv", ["bench.py", "--quick", "--out", str(link)])
    with pytest.raises(SystemExit) as info:
        bench.main()
    assert info.value.code == 2
    assert target.read_text(encoding="utf-8") == "keep"
    assert "symbolic link" in capsys.readouterr().err


def test_table_header_columns() -> None:
    case = {"rows": []}
    header = bench.table(case).splitlines()[0]
    assert header.split(" | ")[0] == "| method"
    assert [c.strip() for c in header.strip("|").split("|")] == [
        "method",
        "time s",
        "runs",
        "pair compares",
        "cell steps",
        "flags",
        "exact TP/FP/miss",
        "exact P",
        "exact R",
        "near TP/FP/miss",
        "near P",
        "near R",
    ]


def test_table_row_cells() -> None:
    full = bench.Row("m", 1.5, 3, 10, 2000, 7)
    full.types = {
        "duplicate_exact": (3, 1, 2, 0.75, 0.6),
        "duplicate_fuzzy": (4, 0, 1, 1.0, 0.8),
    }
    empty = bench.Row("e", 0.25, 1, 0, 0, 0)
    empty.types = {
        "duplicate_exact": (0, 0, 0, None, None),
        "duplicate_fuzzy": (0, 0, 5, None, 0.0),
    }
    lines = bench.table({"rows": [full, empty]}).splitlines()
    assert lines[2] == (
        "| m | 1.500 | 3 | 10 | 2,000 | 7 | 3/1/2 | 0.750 | 0.600 "
        "| 4/0/1 | 1.000 | 0.800 |"
    )
    assert lines[3] == (
        "| e | 0.250 | 1 | 0 | n/a | 0 | 0/0/0 | n/a | n/a | 0/0/5 | n/a | 0.000 |"
    )


def test_step_rate_labels_use_real_lengths() -> None:
    labels = [label for label, _, _ in bench.step_rate()]
    assert labels == [
        "vendor name, 22 and 21 characters",
        "vendor name, 39 and 40 characters",
        "long name, 100 and 100 characters",
    ]
