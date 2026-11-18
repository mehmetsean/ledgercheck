"""Make src/ledgercheck/measured.json, or check that it is current.

python scripts/make_measured.py          writes the file
python scripts/make_measured.py --check  exits 1 if the file differs
"""

import argparse
import sys
import tempfile
from pathlib import Path

from ledgercheck.cli import main as ledgercheck_main

TARGET = Path(__file__).resolve().parent.parent / "src/ledgercheck/measured.json"


def build(args: argparse.Namespace) -> str:
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder) / "out"
        code = ledgercheck_main(
            [
                "evaluate",
                "--size", args.size,
                "--months", args.months,
                "--tune-seeds", args.tune_seeds,
                "--seeds", args.seeds,
                "--rate", args.rate,
                "--out", str(out),
            ]
        )  # fmt: skip
        if code != 0:
            raise SystemExit(code)
        return (out / "metrics.json").read_text("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--path", type=Path, default=TARGET)
    parser.add_argument("--size", default="large")
    parser.add_argument("--months", default="12")
    parser.add_argument("--tune-seeds", default="1-10")
    parser.add_argument("--seeds", default="101-130")
    parser.add_argument("--rate", default="0.1")
    args = parser.parse_args(argv)
    text = build(args)
    if not args.check:
        args.path.write_text(text, encoding="utf-8")
        print(f"wrote {args.path}")
        return 0
    if args.path.read_text("utf-8") != text:
        print(f"{args.path} is out of date, run scripts/make_measured.py")
        return 1
    print(f"{args.path} is current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
