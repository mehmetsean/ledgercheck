"""Command line: ledgercheck run DATA --out OUT."""

import argparse
import sys
from pathlib import Path

from .analyze import analyze
from .config import load_column_map, load_settings
from .eval_report import (
    EVAL_FILES,
    folder_text,
    metrics_dict,
    write_eval_report,
)
from .evaluate import (
    DEFAULT_COSTS,
    DEFAULT_RATE,
    CostTable,
    EvalParams,
    EvalReport,
    evaluate_folder,
    evaluate_seeds,
    load_costs,
    max_months,
    parse_seeds,
    read_manifest_info,
)
from .io import plain, read_folder
from .models import Settings
from .report import check_existing, check_out_folder, write_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ledgercheck")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the rules and write the analysis")
    run.add_argument("data", type=Path, help="folder with the CSV tables")
    run.add_argument("--out", type=Path, required=True, help="output folder")
    run.add_argument("--column-map", type=Path, help="JSON column map")
    run.add_argument("--settings", type=Path, help="JSON settings")
    run.add_argument("--force", action="store_true", help="replace output files")
    ev = sub.add_parser("evaluate", help="score the rules against synthbiz labels")
    ev.add_argument("data", type=Path, nargs="?", help="one labeled folder")
    ev.add_argument("--costs", type=Path, help="JSON costs")
    ev.add_argument("--settings", type=Path, help="JSON settings, folder mode")
    ev.add_argument("--size", help="small, medium or large")
    ev.add_argument("--months", help="months of data per seed")
    ev.add_argument("--tune-seeds", help="seeds to tune on, for example 1-10")
    ev.add_argument("--seeds", help="seeds to report on, for example 101-130")
    ev.add_argument("--rate", help="planted anomaly rate, 0 to 1")
    ev.add_argument("--out", type=Path, help="output folder, seed mode")
    ev.add_argument("--force", action="store_true", help="replace output files")
    return parser


def _run(args: argparse.Namespace) -> None:
    check_out_folder(args.out, args.data, args.force)
    cmap = load_column_map(args.column_map) if args.column_map else None
    settings = load_settings(args.settings) if args.settings else Settings()
    ledger = read_folder(args.data, cmap)
    result = analyze(ledger, settings)
    write_report(args.out, result, args.force)
    where = plain(str(args.out))
    print(f"Wrote the analysis to {where}, {len(result.flags)} items to check")


SEED_ONLY = ("size", "months", "tune_seeds", "seeds", "rate", "out")


def _whole(text: str, name: str, high: int) -> int:
    if not text.isdigit() or not 1 <= int(text) <= high:
        raise ValueError(f"{name}: use a whole number from 1 to {high}")
    return int(text)


def _rate(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        value = -1.0
    if not 0.0 <= value <= 1.0:
        raise ValueError("--rate: use a number from 0 to 1")
    return value


def _evaluate_folder(args: argparse.Namespace, costs: CostTable) -> None:
    used = [name for name in SEED_ONLY if getattr(args, name) is not None]
    if used or args.force:
        raise ValueError("a DATA folder cannot be combined with the seed run options")
    settings = load_settings(args.settings) if args.settings else Settings()
    scores, count = evaluate_folder(args.data, settings, costs)
    print(folder_text(scores, count, read_manifest_info(args.data), costs))


def _evaluate_seeds(args: argparse.Namespace, costs: CostTable) -> None:
    if args.out is None:
        raise ValueError("give a DATA folder, or --out for a seed run")
    if args.settings:
        raise ValueError("--settings is for one folder, a seed run tunes its own")
    size = args.size or "small"
    if size not in ("small", "medium", "large"):
        raise ValueError("--size: use small, medium or large")
    tune_text = args.tune_seeds or "1-10"
    seeds_text = args.seeds or "101-130"
    tune = parse_seeds(tune_text, "--tune-seeds")
    seeds = parse_seeds(seeds_text, "--seeds")
    if set(tune) & set(seeds):
        raise ValueError("--tune-seeds and --seeds must not share a seed")
    rate = _rate(args.rate) if args.rate is not None else DEFAULT_RATE
    months = _whole(args.months or "12", "--months", max_months())
    check_existing(args.out, args.force, EVAL_FILES)
    params = EvalParams(size, months, rate)
    report = evaluate_seeds(tune, seeds, params, costs)
    command = (
        f"ledgercheck evaluate --size {size} --months {months} "
        f"--tune-seeds {tune_text} --seeds {seeds_text} --rate {rate:g}"
    )
    write_eval_report(args.out, metrics_dict(report, command), args.force)
    print(f"Wrote the evaluation to {plain(str(args.out))}, {len(report.rules)} rules")
    print(f"Settings chosen on the tuning seeds: {_chosen(report)}")


def _chosen(report: EvalReport) -> str:
    s = report.settings
    return (
        f"name_threshold {s.duplicates.name_threshold}, "
        f"invoice_threshold {s.duplicates.invoice_threshold}, "
        f"rare_share {s.rare_share}"
    )


def _evaluate(args: argparse.Namespace) -> None:
    costs = load_costs(args.costs) if args.costs else DEFAULT_COSTS
    if args.data is not None:
        _evaluate_folder(args, costs)
    else:
        _evaluate_seeds(args, costs)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "run":
            _run(args)
        else:
            _evaluate(args)
    except (ValueError, OSError) as e:
        print(f"error: {plain(str(e))}", file=sys.stderr)
        return 2
    except (MemoryError, OverflowError, RecursionError):
        print("ledgercheck: out of memory or numbers too large", file=sys.stderr)
        return 1
    return 0
