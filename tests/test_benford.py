import math

from hypothesis import given
from hypothesis import strategies as st

from ledgercheck.benford import (
    EXPECTED,
    benford_first_digit,
    chi_square_p_value,
    looks_sequential,
    mad_label,
)


def benford_sample(n: int) -> list[int]:
    out: list[int] = []
    for d in range(1, 10):
        out += [d * 1000 + i for i in range(round(n * EXPECTED[d - 1]))]
    return out


def test_expected_shares_sum_to_one() -> None:
    assert math.isclose(sum(EXPECTED), 1.0)
    assert math.isclose(EXPECTED[0], 0.30103, rel_tol=1e-4)


def test_counts_use_absolute_values_and_skip_zero() -> None:
    result = benford_first_digit([-123, 0, 456, 1999, 9], "amount_cents")
    assert result.counts == (2, 0, 0, 1, 0, 0, 0, 0, 1)
    assert result.n == 4


def test_conforming_sample_is_ok() -> None:
    result = benford_first_digit(benford_sample(6000), "amount_cents")
    assert result.status == "ok"
    assert result.mad < 0.006
    assert result.mad_label == "close conformity"
    assert result.p_value > 0.05
    assert "Chi-square rejects" in result.note


def test_uniform_digits_do_not_conform() -> None:
    values = [d * 1000 + i for d in range(1, 10) for i in range(700)]
    result = benford_first_digit(values, "amount_cents")
    assert result.status == "ok"
    assert result.mad_label == "nonconformity"
    assert result.p_value < 0.001


def test_id_like_field_name_is_not_applicable() -> None:
    result = benford_first_digit(benford_sample(6000), "check_number")
    assert result.status == "not_applicable"
    assert "id or a number series" in result.reason


def test_empty_sample() -> None:
    result = benford_first_digit([], "amount_cents")
    assert (result.status, result.n, result.p_value) == ("weak_sample", 0, 1.0)
    assert result.mad_label == "none"


def test_p_value_known_points() -> None:
    assert chi_square_p_value(0.0) == 1.0
    assert math.isclose(chi_square_p_value(15.507), 0.05, abs_tol=1e-3)
    assert math.isclose(chi_square_p_value(20.090), 0.01, abs_tol=1e-3)


def test_mad_cutoffs() -> None:
    assert mad_label(0.006) == "close conformity"
    assert mad_label(0.0061) == "acceptable conformity"
    assert mad_label(0.0121) == "marginally acceptable conformity"
    assert mad_label(0.0151) == "nonconformity"


@given(st.lists(st.integers(-(10**9), 10**9), max_size=300))
def test_small_samples_are_weak_or_not_applicable(values: list[int]) -> None:
    status = benford_first_digit(values, "amount_cents").status
    if looks_sequential(values):
        assert status == "not_applicable"
    else:
        assert status == "weak_sample"


@given(
    st.lists(st.integers(1, 10**9), max_size=300).filter(
        lambda v: not looks_sequential(v)
    )
)
def test_every_sample_under_5000_is_weak_sample(values: list[int]) -> None:
    assert benford_first_digit(values, "amount_cents").status == "weak_sample"


@given(st.integers(0, 10**9), st.integers(10, 6000))
def test_consecutive_runs_are_not_applicable(start: int, length: int) -> None:
    values = list(range(start, start + length))
    assert benford_first_digit(values, "amount_cents").status == "not_applicable"


@given(st.lists(st.integers(1, 10**6), min_size=1, max_size=200))
def test_result_numbers_are_sane(values: list[int]) -> None:
    result = benford_first_digit(values, "amount_cents")
    assert sum(result.counts) == len(values)
    assert 0.0 <= result.mad <= 1.0
    assert 0.0 <= result.p_value <= 1.0
