"""Rebuild the examples folders, or check that they are current.

python scripts/make_examples.py          writes examples/
python scripts/make_examples.py --check  exits 1 if any file differs
"""

import argparse
import sys
import tempfile
from pathlib import Path

from synthbiz.cli import main as synthbiz_main

from ledgercheck.cli import main as ledgercheck_main

ROOT = Path(__file__).resolve().parent.parent / "examples"
DATA = "synthbiz-seed42-12m"
OUT = "ledgercheck-seed42-12m"


def build(folder: Path) -> None:
    code = synthbiz_main(
        [
            "generate",
            "--seed", "42",
            "--size", "small",
            "--months", "12",
            "--out", str(folder / DATA),
        ]
    )  # fmt: skip
    if code not in (0, None):
        raise SystemExit(code)
    code = ledgercheck_main(
        ["run", str(folder / DATA), "--out", str(folder / OUT)]
    )
    if code != 0:
        raise SystemExit(code)


def read_all(folder: Path) -> dict[str, bytes]:
    files = {}
    for name in (DATA, OUT):
        for path in sorted((folder / name).glob("*")):
            files[f"{name}/{path.name}"] = path.read_bytes()
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp)
        build(fresh)
        new = read_all(fresh)
        if args.check:
            old = read_all(args.root) if args.root.exists() else {}
            bad = sorted(k for k in new.keys() | old.keys() if new.get(k) != old.get(k))
            for name in bad:
                print(f"{name} differs, run scripts/make_examples.py")
            if bad:
                return 1
            print("examples are current")
            return 0
        for key, data in new.items():
            path = args.root / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(f"wrote {len(new)} files to {args.root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
