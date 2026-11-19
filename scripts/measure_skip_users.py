"""Score rare_poster with and without the system user allowlist.

python scripts/measure_skip_users.py
python scripts/measure_skip_users.py --seeds 42 --shares 0.05,0.1
"""

import argparse
import sys

from ledgercheck import evaluate as ev
from ledgercheck.models import Settings

SYSTEM_USERS = ("SYSTEM_BATCH", "SYSTEM_RECURRING")


def seed_list(text: str) -> list[int]:
    if "-" in text:
        low, high = text.split("-")
        return list(range(int(low), int(high) + 1))
    return [int(x) for x in text.split(",")]


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
    params = ev.EvalParams(size="large", months=12, rate=0.1)
    seeds = seed_list(args.seeds)
    print(f"seeds {args.seeds}, large, 12 months, rate 0.1")
    print("| rare_share | allowlist | flags | precision | recall |")
    print("| --- | --- | --- | --- | --- |")
    for share in (float(x) for x in args.shares.split(",")):
        for skip in ((), SYSTEM_USERS):
            flags, tp, fp, misses = measure(seeds, share, skip, params)
            p, r = ev.precision(tp, fp), ev.recall(tp, misses)
            label = "system users" if skip else "none"
            print(f"| {share} | {label} | {flags} | {p:.4f} | {r:.4f} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
