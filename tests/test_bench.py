import sys
from datetime import date
from pathlib import Path

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
