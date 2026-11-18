"""First digit test with Nigrini's cutoffs and a chi-square check."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

WEAK_SAMPLE_BELOW = 5_000
ID_WORDS = frozenset({"id", "check", "cheque", "number", "num", "no", "seq"})
MIN_RUN = 10
CUTOFFS = (
    (0.006, "close conformity"),
    (0.012, "acceptable conformity"),
    (0.015, "marginally acceptable conformity"),
)
NONCONFORMITY = "nonconformity"
CHI_SQUARE_NOTE = (
    "Chi-square rejects almost any large sample, even a tiny gap from the "
    "Benford shares. Read the mean absolute deviation first."
)
EXPECTED = tuple(math.log10(1 + 1 / d) for d in range(1, 10))


@dataclass(frozen=True)
class BenfordResult:
    field: str
    status: str
    reason: str
    n: int
    counts: tuple[int, ...]
    expected_shares: tuple[float, ...]
    mad: float
    mad_label: str
    chi_square: float
    p_value: float
    note: str = CHI_SQUARE_NOTE


def looks_sequential(values: Sequence[int]) -> bool:
    """True when most distinct values form one run of consecutive integers."""
    ordered = sorted(set(values))
    best = run = 1 if ordered else 0
    for before, after in zip(ordered, ordered[1:], strict=False):
        run = run + 1 if after == before + 1 else 1
        best = max(best, run)
    return best >= MIN_RUN and best * 2 >= len(ordered)


def looks_like_id(field: str) -> bool:
    return any(word in ID_WORDS for word in field.lower().split("_"))


def chi_square_p_value(x: float) -> float:
    """Upper tail for 8 degrees of freedom, closed form for even degrees."""
    half = x / 2
    return math.exp(-half) * sum(half**k / math.factorial(k) for k in range(4))


def mad_label(mad: float) -> str:
    for cutoff, label in CUTOFFS:
        if mad <= cutoff:
            return label
    return NONCONFORMITY


def _status(values: Sequence[int], field: str, n: int) -> tuple[str, str]:
    if looks_like_id(field):
        return "not_applicable", f"{field} looks like an id or a number series"
    if looks_sequential(values):
        return "not_applicable", f"{field} holds a run of consecutive integers"
    if n < WEAK_SAMPLE_BELOW:
        return "weak_sample", f"{n} non-zero values, fewer than {WEAK_SAMPLE_BELOW}"
    return "ok", f"{n} non-zero values"


def benford_first_digit(values: Sequence[int], field: str) -> BenfordResult:
    counts = [0] * 9
    for v in values:
        if v != 0:
            counts[int(str(abs(v))[0]) - 1] += 1
    n = sum(counts)
    status, reason = _status(values, field, n)
    if n == 0:
        return BenfordResult(field, status, reason, 0, tuple(counts), EXPECTED,
                             0.0, "none", 0.0, 1.0)  # fmt: skip
    mad = sum(abs(c / n - e) for c, e in zip(counts, EXPECTED, strict=True)) / 9
    chi = sum((c - n * e) ** 2 / (n * e) for c, e in zip(counts, EXPECTED, strict=True))
    return BenfordResult(field, status, reason, n, tuple(counts), EXPECTED,
                         mad, mad_label(mad), chi, chi_square_p_value(chi))  # fmt: skip
