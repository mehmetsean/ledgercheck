"""Time and score three duplicate payment methods on synthetic data (synthbiz).

Run from the repo root after pip install -e ".[eval]":
python benchmarks/bench.py [--quick] [--repeat N] [--out docs/benchmark.md]
"""

import argparse
import gc
import os
import platform
import statistics
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

try:
    from synthbiz.generate import Params, generate
except ImportError:
    sys.exit('synthbiz is missing. Run: pip install -e ".[eval]"')

from ledgercheck import duplicates as dup  # noqa: E402
from ledgercheck.duplicates import (  # noqa: E402
    DuplicatePair,
    find_duplicates,
    fuzzy_pairs_all,
    levenshtein,
)
from ledgercheck.evaluate import (  # noqa: E402
    DEFAULT_COSTS,
    labels_from_dataset,
    ledger_from_dataset,
    score,
)
from ledgercheck.models import DuplicateSettings, Flag, Ledger  # noqa: E402

SEED = 42
RATE = 0.1
SLOW_SECONDS = 60.0
TYPES = [
    ("duplicate_exact", "exact_duplicate_payment"),
    ("duplicate_fuzzy", "near_duplicate_payment"),
]
OUT_DEFAULT = ROOT / "docs" / "benchmark.md"


def one_run(fn: Callable[[], Any]) -> tuple[float, Any]:
    gc.collect()
    gc.disable()
    try:
        start = time.perf_counter()
        result = fn()
        end = time.perf_counter()
    finally:
        gc.enable()
    return end - start, result


def median_time(
    fn: Callable[[], Any], repeat: int, slow: bool = False
) -> tuple[float, int, Any]:
    """Median of repeat runs. With slow, stop after the first run over SLOW_SECONDS."""
    times: list[float] = []
    result = None
    for _ in range(repeat):
        result = None
        seconds, result = one_run(fn)
        times.append(seconds)
        if slow and seconds > SLOW_SECONDS:
            break
    return statistics.median(times), len(times), result


def exact_only(ledger: Ledger) -> list[Flag]:
    pairs = dup._exact_pairs(dup._records(ledger))
    return dup._flags(pairs)


def all_pairs(ledger: Ledger, s: DuplicateSettings) -> list[Flag]:
    pairs = dup._exact_pairs(dup._records(ledger)) + fuzzy_pairs_all(ledger, s)
    return dup._flags(pairs)


def blocked(ledger: Ledger, s: DuplicateSettings) -> list[Flag]:
    return list(find_duplicates(ledger, s).flags)


class _Counter(dup._Meter):
    # no limit
    total = 0

    def __init__(self, limit: int | None, window_days: int) -> None:
        super().__init__(None, window_days)
        _Counter.total = 0

    def add(self, cost: int) -> None:
        _Counter.total += cost


def count_steps(fn: Callable[[], Any]) -> tuple[int, Any]:
    original = dup._Meter
    dup._Meter = _Counter  # type: ignore[misc]
    try:
        result = fn()
    finally:
        dup._Meter = original  # type: ignore[misc]
    return _Counter.total, result


@dataclass
class Row:
    method: str
    seconds: float
    runs: int
    compares: int
    steps: int
    flags: int
    types: dict[str, tuple[int, int, int, float | None, float | None]] = field(
        default_factory=dict
    )


def pr(tp: int, fp: int, misses: int) -> tuple[float | None, float | None]:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + misses) if tp + misses else None
    return p, r


def accuracy(
    flags: list[Flag], labels: Any, ledger: Ledger
) -> dict[str, tuple[int, int, int, float | None, float | None]]:
    scores = score(flags, labels, ledger, DEFAULT_COSTS)
    out = {}
    for rule, _kind in TYPES:
        s = scores.rules[rule]
        p, r = pr(s.tp, s.fp, s.misses)
        out[rule] = (s.tp, s.fp, s.misses, p, r)
    return out


def check_blocking(
    ledger: Ledger, s: DuplicateSettings, everything: list[DuplicatePair]
) -> tuple[int, int, int, int, list[DuplicatePair]]:
    """Returns total all-pairs matches, left out, different amount, outside window,
    and the matches that blocking must have found but did not."""
    found = {
        (p.earlier_id, p.later_id)
        for p in find_duplicates(ledger, s).pairs
        if p.kind == "fuzzy"
    }
    missing = [
        p
        for p in everything
        if p.same_amount
        and p.days_apart <= s.window_days
        and (p.earlier_id, p.later_id) not in found
    ]
    other_amount = sum(1 for p in everything if not p.same_amount)
    late = sum(1 for p in everything if p.same_amount and p.days_apart > s.window_days)
    return len(everything), other_amount + late, other_amount, late, missing


def run_case(size: str, months: int, repeat: int) -> dict[str, Any]:
    ds = generate(Params(seed=SEED, size=size, months=months, anomaly_rate=RATE))
    ledger = ledger_from_dataset(ds.tables)
    labels = labels_from_dataset(ds.labels)
    s = DuplicateSettings()
    n = len(ledger.payments or ())
    rows: list[Row] = []

    sec, runs, flags = median_time(lambda: exact_only(ledger), repeat)
    rows.append(Row("exact key only", sec, runs, 0, 0, len(flags)))
    rows[-1].types = accuracy(flags, labels, ledger)

    sec, runs, flags = median_time(lambda: blocked(ledger, s), repeat)
    result = find_duplicates(ledger, s)
    steps, _ = count_steps(lambda: find_duplicates(ledger, s))
    row = Row("blocked fuzzy", sec, runs, result.compares, steps, len(flags))
    row.types = accuracy(flags, labels, ledger)
    blocked_row = row

    sec, runs, flags = median_time(lambda: all_pairs(ledger, s), repeat, True)
    steps, everything = count_steps(lambda: fuzzy_pairs_all(ledger, s))
    row = Row("all-pairs fuzzy", sec, runs, n * (n - 1) // 2, steps, len(flags))
    row.types = accuracy(flags, labels, ledger)
    rows.insert(1, row)
    rows.append(blocked_row)

    total, left_out, other, late, missing = check_blocking(ledger, s, everything)
    return {
        "size": size,
        "months": months,
        "payments": n,
        "rows": rows,
        "all_matches": total,
        "left_out": left_out,
        "other_amount": other,
        "late": late,
        "missing": missing,
    }


def step_rate() -> list[tuple[str, int, float]]:
    cases = [
        (
            "vendor name",
            "acme industrial supply",
            "acme industrial suply",
        ),
        (
            "vendor name",
            "northern harbor logistics and freight x",
            "northern harbour logistics and frieght y",
        ),
        ("long name", "a" * 100, "b" * 100),
    ]
    out = []
    for name, a, b in cases:
        label = f"{name}, {len(a)} and {len(b)} characters"
        steps = len(a) * len(b)
        loops = max(1, 2_000_000 // steps)
        gc.collect()
        gc.disable()
        try:
            start = time.perf_counter()
            for _ in range(loops):
                levenshtein(a, b)
            end = time.perf_counter()
        finally:
            gc.enable()
        out.append((label, steps, steps * loops / (end - start)))
    return out


def fmt(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def table(case: dict[str, Any]) -> str:
    head = (
        "| method | time s | runs | pair compares | cell steps | flags "
        "| exact TP/FP/miss | exact P | exact R "
        "| near TP/FP/miss | near P | near R |"
    )
    lines = [head, "|" + "---|" * 12]
    for r in case["rows"]:
        e = r.types["duplicate_exact"]
        f = r.types["duplicate_fuzzy"]
        steps = f"{r.steps:,}" if r.steps else "n/a"
        lines.append(
            f"| {r.method} | {r.seconds:.3f} | {r.runs} | {r.compares:,} "
            f"| {steps} | {r.flags} "
            f"| {e[0]}/{e[1]}/{e[2]} | {fmt(e[3])} | {fmt(e[4])} "
            f"| {f[0]}/{f[1]}/{f[2]} | {fmt(f[3])} | {fmt(f[4])} |"
        )
    return "\n".join(lines)


def report(cases: list[dict[str, Any]], rates: list[tuple[str, int, float]]) -> str:
    out = [
        f"Python {platform.python_version()}, {platform.platform()}, "
        f"{os.cpu_count()} CPUs. Seed {SEED}, anomaly rate {RATE}, default settings.",
        "",
    ]
    for c in cases:
        out += [
            f"## {c['size']}, {c['months']} months, {c['payments']:,} payments",
            "",
            table(c),
            "",
            f"All-pairs fuzzy pairs: {c['all_matches']}. Blocking leaves out "
            f"{c['left_out']}: {c['other_amount']} with a different amount and "
            f"{c['late']} outside the window. Matches that share an amount and fall "
            f"in the window but are missing from blocked fuzzy: {len(c['missing'])}.",
            "",
        ]
    out += ["## Levenshtein cell steps per second", "", RATE_LINE, ""]
    out += ["| input | cell steps per compare | steps per second |", "|---|---|---|"]
    for label, steps, rate in rates:
        out.append(f"| {label} | {steps:,} | {rate:,.0f} |")
    return "\n".join(out)


NOTES = """\
## What the numbers mean

Exact-key matching is fast and finds every planted exact duplicate. All-pairs
fuzzy compares every pair of payments, so its compare count grows with the
square of the payment count. Blocked fuzzy compares only payments with the same
amount inside the date window, so it does far fewer compares and runs in
milliseconds. All-pairs also matches pairs with a different amount, which are
extra flags and count as false positives here. The assertion in the script
checks that blocking never loses a match that shares an amount and falls in the
window. The matches it leaves out have a different amount or are outside the
window, by design. A run count of 1 means one run took more than 60 seconds, so
it was not repeated.

Precision and recall are counted the way `ledgercheck evaluate` counts them,
per planted duplicate type. Treat them as a check that the code works on
synthetic data. synthbiz plants no typo near-duplicates yet (its near duplicates
keep the amount and the invoice number and differ in vendor suffix or
punctuation), so fuzzy recall on this data says nothing about typos. See the
README. Times are from one machine and will differ on yours. The cell steps
columns in the tables above are counted by the same meter the shipped search
uses, 16 per compare plus the edit distance cells.
"""


RATE_LINE = (
    "This table times the edit distance alone, len(a) x len(b) cells per call. "
    "The meter in the search also adds 16 steps per compare for call overhead, "
    "which is not timed here."
)

QUICK_LINE = (
    "This is a quick run (size small, 3 months, 1 run), not the full benchmark.\n\n"
)


def build_doc(body: str, quick: bool = False) -> str:
    return (
        "# Benchmark\n\n"
        "Generated by benchmarks/bench.py. To rerun it from the repo root after "
        '`pip install -e ".[eval]"`: '
        "`python benchmarks/bench.py --out docs/benchmark.md`. Data is synthetic "
        "(synthbiz).\n\n" + (QUICK_LINE if quick else "") + body + "\n\n" + NOTES
    )


def positive(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a whole number of 1 or more")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="small, 3 months, 1 run")
    parser.add_argument("--repeat", type=positive, default=5)
    parser.add_argument(
        "--out", type=Path, default=None, help="markdown file, overwritten if it exists"
    )
    args = parser.parse_args()
    if args.out is not None and args.out.is_symlink():
        parser.error("--out must not be a symbolic link")
    if args.quick:
        plan = [("small", 3)]
        repeat = 1
        out = args.out
    else:
        plan = [("large", 12), ("large", 36)]
        repeat = args.repeat
        out = args.out
    cases = [run_case(size, m, repeat) for size, m in plan]
    body = report(cases, step_rate())
    print(body)
    if out is not None:
        out.write_text(build_doc(body, args.quick), encoding="utf-8")
        print(f"\nWrote {out}")
    bad = [c for c in cases if c["missing"]]
    for c in bad:
        print(f"FAIL: blocking missed {len(c['missing'])} matches", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
