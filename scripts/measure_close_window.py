"""Score period_mismatch on synthbiz synthetic data for several close windows.

python scripts/measure_close_window.py
python scripts/measure_close_window.py --seeds 42 --windows 0,3,5
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from measure_skip_users import seed_list  # noqa: E402

from ledgercheck import evaluate as ev  # noqa: E402
from ledgercheck.models import Settings  # noqa: E402


def window_list(text: str) -> list[int]:
    try:
        windows = [int(x) for x in text.split(",")]
    except ValueError:
        raise ValueError("--windows: use numbers such as 0,3,5") from None
    if not windows or any(not 0 <= x <= 31 for x in windows):
        raise ValueError("--windows: each window must be from 0 to 31")
    return windows


def show(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def measure(
    seeds: list[int], window: int, params: ev.EvalParams
) -> tuple[int, int, int, int]:
    flags = tp = fp = misses = 0
    for seed in seeds:
        data = ev.make_seed(seed, params)
        settings = Settings(close_window_days=window)
        found = ev.all_flags(data.ledger, settings)
        got = ev.score(found, data.labels, data.ledger, ev.DEFAULT_COSTS)
        rule = got.rules["period_mismatch"]
        flags += rule.flags
        tp += rule.tp
        fp += rule.fp
        misses += rule.misses
    return flags, tp, fp, misses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="42")
    parser.add_argument("--windows", default="0,3,4,5,6")
    args = parser.parse_args(argv)
    try:
        seeds = seed_list(args.seeds)
        windows = window_list(args.windows)
    except ValueError as e:
        parser.error(str(e))
    params = ev.EvalParams(size="large", months=12, rate=0.1)
    rows = []
    for window in windows:
        flags, tp, fp, misses = measure(seeds, window, params)
        p, r = ev.precision(tp, fp), ev.recall(tp, misses)
        rows.append(f"| {window} | {flags} | {tp} | {fp} | {show(p)} | {show(r)} |")
    print(f"seeds {args.seeds}, large, 12 months, rate 0.1")
    print("| close_window_days | flags | tp | fp | precision | recall |")
    print("| --- | --- | --- | --- | --- | --- |")
    print("\n".join(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
