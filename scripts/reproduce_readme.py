"""Rebuild the numbers block in README.md from files and fresh runs.

python scripts/reproduce_readme.py          rewrites the block
python scripts/reproduce_readme.py --check  exits 1 if the block is out of date
"""

import argparse
import csv
import json
import re
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from synthbiz.cli import main as synthbiz_main

from ledgercheck.cli import main as ledgercheck_main

START = "<!-- numbers:start -->"
END = "<!-- numbers:end -->"
ROOT = Path(__file__).resolve().parent.parent
MEASURED = ROOT / "src/ledgercheck/measured.json"
BENCHMARK = ROOT / "docs/benchmark.md"
EXAMPLE_DATA = ROOT / "examples/synthbiz-seed42-12m"
EXAMPLE_OUT = ROOT / "examples/ledgercheck-seed42-12m"
SHOWN = ("pair compares", "time s", "near P", "near R")


@dataclass
class Section:
    title: str
    rows: dict[str, dict[str, str]]
    left_out: str
    different_amount: str


def parse_benchmark(text: str) -> list[Section]:
    sections = []
    for part in re.split(r"^## ", text, flags=re.M)[1:]:
        lines = part.splitlines()
        if "payments" not in lines[0]:
            continue
        table = [line for line in lines if line.startswith("|")]
        head = [c.strip() for c in table[0].strip("|").split("|")]
        rows = {}
        for line in table[2:]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            rows[cells[0]] = dict(zip(head, cells, strict=True))
        found = re.search(r"leaves out (\d+): (\d+) with a different amount", part)
        if found is None:
            raise ValueError(f"{lines[0]}: no left-out line")
        sections.append(Section(lines[0], rows, found.group(1), found.group(2)))
    return sections


def rate_table(rows: dict[str, Any]) -> list[str]:
    lines = ["| Rule | Flags | Precision | Recall |", "| --- | --- | --- | --- |"]
    for name in sorted(rows):
        r = rows[name]
        lines.append(
            f"| {name} | {r['flags']} | {r['precision']:.4f} | {r['recall']:.4f} |"
        )
    return lines


def count_note(data: dict[str, Any]) -> str:
    seeds = len(data["report_seeds"])
    r = data["rules"]["split_under_limit"]
    total = r["true_positives"] + r["false_positives"]
    return (
        f"Flags and counts are summed over the {seeds} report seeds. Precision is "
        "true positives over true plus false positives. True positives are counted "
        "per labeled unit and false positives per flag, so Flags can be lower than "
        "that sum when one flag covers several units. "
        f"split_under_limit is the example: {r['flags']} flags, "
        f"{r['true_positives']} true positives plus {r['false_positives']} false "
        f"positives is {total}."
    )


def measured_lines() -> list[str]:
    data = json.loads(MEASURED.read_text("utf-8"))
    p = data["params"]
    s = data["settings"]
    seeds = f"{data['tune_seeds'][0]}-{data['tune_seeds'][-1]}"
    rep = f"{data['report_seeds'][0]}-{data['report_seeds'][-1]}"
    lines = [
        "### Measured rates, synthetic data",
        "",
        f"Command: `{data['command']}`. Size {p['size']}, {p['months']} months, "
        f"planted rate {data['planted']['anomaly_rate']}, tuning seeds {seeds}, "
        f"report seeds {rep}. Run defaults: {s['defaults']['rare_share']} "
        f"rare_share, {s['defaults']['name_threshold']} name_threshold, "
        f"{s['defaults']['invoice_threshold']} invoice_threshold.",
        "",
        *rate_table(data["rules"]),
        "",
        count_note(data),
        "",
        "Tuned rows (settings picked on the tuning seeds):",
        "",
        *rate_table(data["tuned_rules"]),
        "",
    ]
    old = data["rules"]["rare_poster"]["recall"]
    new = data["tuned_rules"]["rare_poster"]["recall"]
    share = s["defaults"]["rare_share"]
    if s["tuned"]["rare_share"] == share:
        lines.append(
            f"rare_poster has recall {old:.4f} at rare_share {share}. "
            f"Tuning kept rare_share {share}, so its tuned row equals its default row."
        )
    else:
        lines.append(
            f"rare_poster at rare_share {share} has recall {old:.4f}. "
            f"At rare_share {s['tuned']['rare_share']} it has recall {new:.4f}."
        )
    lines.append("")
    lines.append(
        f"duplicate_fuzzy at invoice_threshold {s['defaults']['invoice_threshold']} "
        f"has recall {data['rules']['duplicate_fuzzy']['recall']:.4f}. "
        f"At invoice_threshold {s['tuned']['invoice_threshold']} it has recall "
        f"{data['tuned_rules']['duplicate_fuzzy']['recall']:.4f}."
    )
    lines.append("")
    typo = data["any_rule"]["typo_duplicate_payment"]
    low, high = typo["recall_ci"]
    lines.append(
        f"typo_duplicate_payment: {typo['caught']} of {typo['labeled']} labeled "
        f"payments are flagged by a scored rule at the run defaults, recall "
        f"{typo['recall']:.4f} (95 percent interval {low:.4f} to {high:.4f}). "
        "Only duplicate_exact and duplicate_fuzzy flag payments."
    )
    return lines


def run_clean() -> Counter[str]:
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "clean"
        out = Path(tmp) / "out"
        code = synthbiz_main(["generate", "--anomaly-rate", "0", "--out", str(data)])
        if code not in (0, None):
            raise SystemExit(code)
        code = ledgercheck_main(["run", str(data), "--out", str(out)])
        if code != 0:
            raise SystemExit(code)
        return count_rules(out / "items_to_check.csv")


def count_rules(path: Path) -> Counter[str]:
    with path.open(newline="", encoding="utf-8") as f:
        return Counter(row["rule"] for row in csv.DictReader(f))


def count_lines(counts: Counter[str]) -> list[str]:
    return [f"- {rule}: {counts[rule]}" for rule in sorted(counts)]


def count_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))


def clean_lines() -> list[str]:
    counts = run_clean()
    return [
        "### Clean ledger",
        "",
        "synthbiz with anomaly rate 0 and the default seed, then `ledgercheck run`. "
        f"Items to check: {sum(counts.values())}. Rules with items:",
        "",
        *count_lines(counts),
    ]


def benchmark_lines() -> list[str]:
    lines = ["### Duplicate search benchmark", ""]
    lines.append(
        "Rows are copied from docs/benchmark.md and this script does not rerun "
        "them. Times are from one machine, see that file for the machine. A test "
        "reruns the exact key and blocked methods on 12 months and checks their "
        "near duplicate counts and recall against that file. It also checks the "
        "blocked compare count."
    )
    for sec in parse_benchmark(BENCHMARK.read_text("utf-8")):
        lines += ["", f"{sec.title}:", ""]
        lines += ["| Method | Pair compares | Time s | Near P | Near R |"]
        lines += ["| --- | --- | --- | --- | --- |"]
        for method, row in sec.rows.items():
            cells = " | ".join(row[k] for k in SHOWN)
            lines.append(f"| {method} | {cells} |")
        lines += [
            "",
            f"All-pairs matches that blocking leaves out: {sec.left_out}, of which "
            f"{sec.different_amount} have a different amount.",
        ]
    return lines


def example_lines() -> list[str]:
    counts = count_rules(EXAMPLE_OUT / "items_to_check.csv")
    labels = count_rows(EXAMPLE_DATA / "labels.csv")
    return [
        "### Example folders",
        "",
        "examples/ holds synthbiz seed 42, size small, 12 months, and the "
        f"analysis of it. The synthetic data has {labels} planted anomalies. "
        f"The analysis lists {sum(counts.values())} items to check:",
        "",
        *count_lines(counts),
    ]


def build_block() -> str:
    parts = [measured_lines(), clean_lines(), benchmark_lines(), example_lines()]
    return "\n\n".join("\n".join(p) for p in parts)


def replace_block(text: str, block: str) -> str:
    if START not in text or END not in text:
        raise ValueError("README.md needs the numbers start and end markers")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{block}\n{END}{tail}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--readme", type=Path, default=ROOT / "README.md")
    args = parser.parse_args(argv)
    try:
        old = args.readme.read_text(encoding="utf-8")
        new = replace_block(old, build_block())
    except (OSError, ValueError) as e:
        print(f"error: {e}")
        return 2
    if args.check:
        if new != old:
            print("README numbers are out of date, run scripts/reproduce_readme.py")
            return 1
        print("README numbers match")
        return 0
    args.readme.write_text(new, encoding="utf-8")
    print("README numbers updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
