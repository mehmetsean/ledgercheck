"""Score duplicate_fuzzy on synthbiz synthetic data for sequence steps.

python scripts/measure_sequence.py
python scripts/measure_sequence.py --seeds 42 --steps 0,1,2
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from measure_skip_users import seed_list  # noqa: E402

from ledgercheck import evaluate as ev  # noqa: E402
from ledgercheck.models import DuplicateSettings, Settings  # noqa: E402


def step_list(text: str) -> list[int]:
    try:
        values = [int(x) for x in text.split(",")]
    except ValueError:
        raise ValueError("--steps: use numbers such as 0,1,5") from None
    if not values or any(not 0 <= x <= 1000 for x in values):
        raise ValueError("--steps: each value must be from 0 to 1000")
    return values


def show(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def measure(
    seeds: list[int], step: int, params: ev.EvalParams
) -> tuple[int, int, int, int]:
    flags = tp = fp = misses = 0
    for seed in seeds:
        data = ev.make_seed(seed, params)
        dup = DuplicateSettings(sequence_max_step=step)
        found = ev.all_flags(data.ledger, Settings(duplicates=dup))
        got = ev.score(found, data.labels, data.ledger, ev.DEFAULT_COSTS)
        rule = got.rules["duplicate_fuzzy"]
        flags += rule.flags
        tp += rule.tp
        fp += rule.fp
        misses += rule.misses
    return flags, tp, fp, misses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="42")
    parser.add_argument("--steps", default="0,1,2,3")
    args = parser.parse_args(argv)
    try:
        seeds = seed_list(args.seeds)
        steps = step_list(args.steps)
    except ValueError as e:
        parser.error(str(e))
    params = ev.EvalParams(size="large", months=12, rate=0.1)
    rows = []
    for step in steps:
        flags, tp, fp, misses = measure(seeds, step, params)
        p, r = ev.precision(tp, fp), ev.recall(tp, misses)
        rows.append(f"| {step} | {flags} | {tp} | {fp} | {show(p)} | {show(r)} |")
    print(f"seeds {args.seeds}, large, 12 months, rate 0.1")
    print("| sequence_max_step | flags | tp | fp | precision | recall |")
    print("| --- | --- | --- | --- | --- | --- |")
    print("\n".join(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
