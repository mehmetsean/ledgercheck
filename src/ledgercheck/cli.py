"""Command line: ledgercheck run DATA --out OUT."""

import argparse
import sys
from pathlib import Path

from .analyze import analyze
from .config import load_column_map, load_settings
from .io import plain, read_folder
from .models import Settings
from .report import check_out_folder, write_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ledgercheck")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run the rules and write the analysis")
    run.add_argument("data", type=Path, help="folder with the CSV tables")
    run.add_argument("--out", type=Path, required=True, help="output folder")
    run.add_argument("--column-map", type=Path, help="JSON column map")
    run.add_argument("--settings", type=Path, help="JSON settings")
    run.add_argument("--force", action="store_true", help="replace output files")
    return parser


def _run(args: argparse.Namespace) -> None:
    check_out_folder(args.out, args.data)
    cmap = load_column_map(args.column_map) if args.column_map else None
    settings = load_settings(args.settings) if args.settings else Settings()
    ledger = read_folder(args.data, cmap)
    result = analyze(ledger, settings)
    write_report(args.out, result, args.force)
    where = plain(str(args.out))
    print(f"Wrote the analysis to {where}, {len(result.flags)} items to check")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _run(args)
    except (ValueError, OSError) as e:
        print(f"error: {plain(str(e))}", file=sys.stderr)
        return 2
    except (MemoryError, OverflowError, RecursionError):
        print("ledgercheck: out of memory or numbers too large", file=sys.stderr)
        return 1
    return 0
