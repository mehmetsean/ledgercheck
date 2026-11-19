"""Score rare_poster on synthbiz synthetic data, with and without the system user skip list.

python scripts/measure_skip_users.py
python scripts/measure_skip_users.py --seeds 42 --shares 0.05,0.1
"""

# ruff: noqa: E501
import argparse
import sys

from ledgercheck import evaluate as ev
from ledgercheck.models import Settings

SYSTEM_USERS = ("SYSTEM_BATCH", "SYSTEM_RECURRING")


MAX_SEEDS = 200


def seed_list(text: str) -> list[int]:
    if text.startswith("-"):
        raise ValueError("--seeds: seeds cannot be negative")
    try:
        if "-" in text:
            low, high = (int(x) for x in text.split("-"))
            if high < low:
                raise ValueError("the end is below the start")
            if high - low + 1 > MAX_SEEDS:
                raise ValueError(f"at most {MAX_SEEDS} seeds")
            seeds = list(range(low, high + 1))
        else:
            seeds = [int(x) for x in text.split(",")]
    except ValueError as e:
        if "at most" in str(e):
            raise ValueError(f"--seeds: {e}") from None
        raise ValueError(f"--seeds: use 42, 1,9 or 101-130 ({e})") from None
    if any(x < 0 for x in seeds):
        raise ValueError("--seeds: seeds cannot be negative")
    if not seeds or len(seeds) > MAX_SEEDS:
        raise ValueError(f"--seeds: 1 to {MAX_SEEDS} seeds")
    return seeds


def share_list(text: str) -> list[float]:
    try:
        shares = [float(x) for x in text.split(",")]
    except ValueError:
        raise ValueError("--shares: use numbers such as 0.05,0.1") from None
    if not shares or any(not 0 <= x <= 1 for x in shares):
        raise ValueError("--shares: each share must be from 0 to 1")
    return shares


def show(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def measure(
    seeds: list[int], share: float, skip: tuple[str, ...], params: ev.EvalParams
) -> tuple[int, int, int, int]:
    flags = tp = fp = misses = 0
    for seed in seeds:
        data = ev.make_seed(seed, params)
        settings = Settings(rare_share=share, rare_skip_users=skip)
        found = ev.all_flags(data.ledger, settings)
        got = ev.score(found, data.labels, data.ledger, ev.DEFAULT_COSTS)
        rule = got.rules["rare_poster"]
        flags += rule.flags
        tp += rule.tp
        fp += rule.fp
        misses += rule.misses
    return flags, tp, fp, misses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="42")
    parser.add_argument("--shares", default="0.05,0.1")
    args = parser.parse_args(argv)
    try:
        seeds = seed_list(args.seeds)
        shares = share_list(args.shares)
    except ValueError as e:
        parser.error(str(e))
    params = ev.EvalParams(size="large", months=12, rate=0.1)
    rows = []
    try:
        for share in shares:
            for skip in ((), SYSTEM_USERS):
                flags, tp, fp, misses = measure(seeds, share, skip, params)
                p, r = ev.precision(tp, fp), ev.recall(tp, misses)
                label = "system users" if skip else "none"
                rows.append(f"| {share} | {label} | {flags} | {show(p)} | {show(r)} |")
    except ValueError as e:
        parser.error(str(e))
    print(f"seeds {args.seeds}, large, 12 months, rate 0.1")
    print("| rare_share | skip list | flags | precision | recall |")
    print("| --- | --- | --- | --- | --- |")
    print("\n".join(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
