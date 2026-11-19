"""Score round_amount on synthbiz synthetic data for recurring series minimums.

python scripts/measure_round_series.py
python scripts/measure_round_series.py --seeds 42 --minimums 0,2,3
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from measure_skip_users import seed_list  # noqa: E402

from ledgercheck import evaluate as ev  # noqa: E402
from ledgercheck.models import Settings  # noqa: E402


def minimum_list(text: str) -> list[int]:
    try:
        values = [int(x) for x in text.split(",")]
    except ValueError:
        raise ValueError("--minimums: use numbers such as 0,2,3") from None
    if not values or any(x != 0 and not 2 <= x <= 1000 for x in values):
        raise ValueError("--minimums: each value must be 0 or from 2 to 1000")
    return values


def show(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def measure(
    seeds: list[int], minimum: int, params: ev.EvalParams
) -> tuple[int, int, int, int]:
    flags = tp = fp = misses = 0
    for seed in seeds:
        data = ev.make_seed(seed, params)
        settings = Settings(round_recurring_min_months=minimum)
        found = ev.all_flags(data.ledger, settings)
        got = ev.score(found, data.labels, data.ledger, ev.DEFAULT_COSTS)
        rule = got.rules["round_amount"]
        flags += rule.flags
        tp += rule.tp
        fp += rule.fp
        misses += rule.misses
    return flags, tp, fp, misses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="42")
    parser.add_argument("--minimums", default="0,2,3,6,12")
    args = parser.parse_args(argv)
    try:
        seeds = seed_list(args.seeds)
        minimums = minimum_list(args.minimums)
    except ValueError as e:
        parser.error(str(e))
    params = ev.EvalParams(size="large", months=12, rate=0.1)
    rows = []
    for minimum in minimums:
        flags, tp, fp, misses = measure(seeds, minimum, params)
        p, r = ev.precision(tp, fp), ev.recall(tp, misses)
        rows.append(f"| {minimum} | {flags} | {tp} | {fp} | {show(p)} | {show(r)} |")
    print(f"seeds {args.seeds}, large, 12 months, rate 0.1")
    print("| round_recurring_min_months | flags | tp | fp | precision | recall |")
    print("| --- | --- | --- | --- | --- | --- |")
    print("\n".join(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
