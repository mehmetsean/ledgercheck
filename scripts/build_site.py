"""Build _site/ for the demo: the page, two wheels and the Pyodide core files.

python scripts/build_site.py [--out _site] [--cache .cache]

The Pyodide download is checked against a pinned sha256 before use. Nothing from
the download is run. Files are only hashed, read from the archive and copied.
"""

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYODIDE_VERSION = "314.0.8"
TARBALL = f"pyodide-core-{PYODIDE_VERSION}.tar.bz2"
PYODIDE_URL = (
    f"https://github.com/pyodide/pyodide/releases/download/{PYODIDE_VERSION}/{TARBALL}"
)
TARBALL_SHA256 = "ff3e5f9d9bc8e98ff30b99515535fc24d375994f47a978c61975d653e162ca37"
PYODIDE_JS_SRI = "0Tw0jFeRF+UzB1HbzjzDi5ZNMyMclQPHmYkEquv9V+lAj/rZBHxu1c35Uq28kDPo"
CORE_FILES = (
    "pyodide.js",
    "pyodide.asm.mjs",
    "pyodide.asm.wasm",
    "python_stdlib.zip",
    "pyodide-lock.json",
)
PIN = re.compile(r'"(synthbiz @ git\+https://github\.com/[^"@]+@[0-9a-f]{40})"')


def check_sha256(path: Path, expected: str) -> None:
    found = hashlib.sha256(path.read_bytes()).hexdigest()
    if found != expected:
        raise SystemExit(f"sha256 mismatch for {path.name}: {found}, wanted {expected}")


def check_sri(path: Path, expected: str) -> None:
    found = base64.b64encode(hashlib.sha384(path.read_bytes()).digest()).decode()
    if found != expected:
        raise SystemExit(f"sha384 mismatch for {path.name}: {found}")


def download(url: str, dest: Path) -> None:
    if not url.startswith("https://"):
        raise SystemExit("only https downloads are allowed")
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(url, timeout=120) as r, temp.open("wb") as f:
        shutil.copyfileobj(r, f)
    temp.replace(dest)


def fetch_tarball(cache: Path) -> Path:
    path = cache / TARBALL
    if not path.is_file():
        print(f"downloading {PYODIDE_URL}")
        download(PYODIDE_URL, path)
    try:
        check_sha256(path, TARBALL_SHA256)
    except SystemExit:
        path.unlink()
        raise
    return path


def extract_core(tarball: Path, out: Path) -> None:
    """Copy only CORE_FILES out of the archive, by name, as plain bytes."""
    found: dict[str, bytes] = {}
    with tarfile.open(tarball, "r:bz2") as tar:
        for member in tar.getmembers():
            name = Path(member.name).name
            if name in CORE_FILES and member.isfile() and name not in found:
                data = tar.extractfile(member)
                if data is not None:
                    found[name] = data.read()
    missing = [n for n in CORE_FILES if n not in found]
    if missing:
        raise SystemExit(f"the Pyodide archive is missing {missing}")
    out.mkdir(parents=True, exist_ok=True)
    for name in CORE_FILES:
        (out / name).write_bytes(found[name])


def pinned_synthbiz(pyproject: Path) -> str:
    match = PIN.search(pyproject.read_text("utf-8"))
    if match is None:
        raise SystemExit("no pinned synthbiz commit found in pyproject.toml")
    return match.group(1)


def build_wheel(target: str, out: Path) -> str:
    before = {p.name for p in out.glob("*.whl")}
    cmd = [sys.executable, "-m", "pip", "wheel", target, "--no-deps", "-w", str(out)]
    subprocess.run(cmd, check=True, cwd=ROOT)
    new = sorted({p.name for p in out.glob("*.whl")} - before)
    if len(new) != 1:
        raise SystemExit(f"expected one new wheel for {target}, found {new}")
    return new[0]


def write_manifest(out: Path, wheels: list[str]) -> None:
    data = {"pyodide": PYODIDE_VERSION, "wheels": sorted(wheels)}
    (out / "manifest.json").write_text(json.dumps(data, indent=2) + "\n", "utf-8")


def clear(out: Path) -> None:
    if out.exists():
        if out.name != "_site":
            raise SystemExit(f"{out} exists, remove it first")
        shutil.rmtree(out)
    out.mkdir(parents=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "_site")
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache")
    args = parser.parse_args(argv)
    tarball = fetch_tarball(args.cache)
    clear(args.out)
    shutil.copytree(ROOT / "site", args.out, dirs_exist_ok=True)
    extract_core(tarball, args.out / "pyodide")
    check_sri(args.out / "pyodide" / "pyodide.js", PYODIDE_JS_SRI)
    wheels = args.out / "wheels"
    wheels.mkdir()
    names = [build_wheel(".", wheels)]
    names.append(build_wheel(pinned_synthbiz(ROOT / "pyproject.toml"), wheels))
    write_manifest(args.out, names)
    size = sum(p.stat().st_size for p in args.out.rglob("*") if p.is_file())
    print(f"built {args.out}, {size:,} bytes, wheels {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
