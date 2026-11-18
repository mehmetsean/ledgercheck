# ruff: noqa: E501
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import make_examples  # noqa: E402
import reproduce_readme  # noqa: E402

BENCH = """# Benchmark

## large, 12 months, 1,288 payments

| method | time s | runs | pair compares | cell steps | flags | exact TP/FP/miss | exact P | exact R | near TP/FP/miss | near P | near R |
|---|---|---|---|---|---|---|---|---|---|---|---|
| exact key only | 0.002 | 5 | 0 | n/a | 30 | 30/0/0 | 1.000 | 1.000 | 0/0/29 | n/a | 0.000 |
| blocked fuzzy | 0.003 | 5 | 59 | 10,270 | 59 | 30/0/0 | 1.000 | 1.000 | 29/0/0 | 1.000 | 1.000 |

All-pairs fuzzy pairs: 36. Blocking leaves out 7: 7 with a different amount and 0 outside the window.
"""


def test_replace_block_swaps_only_the_block() -> None:
    text = "head\n<!-- numbers:start -->\nold\n<!-- numbers:end -->\ntail\n"
    new = reproduce_readme.replace_block(text, "new")
    assert new == "head\n<!-- numbers:start -->\nnew\n<!-- numbers:end -->\ntail\n"
    assert reproduce_readme.replace_block(new, "new") == new


def test_replace_block_needs_markers() -> None:
    with pytest.raises(ValueError):
        reproduce_readme.replace_block("no markers", "x")


def test_parse_benchmark_reads_rows_and_leftovers() -> None:
    sections = reproduce_readme.parse_benchmark(BENCH)
    assert len(sections) == 1
    s = sections[0]
    assert s.title == "large, 12 months, 1,288 payments"
    assert s.rows["blocked fuzzy"]["pair compares"] == "59"
    assert s.rows["exact key only"]["near R"] == "0.000"
    assert s.left_out == "7"
    assert s.different_amount == "7"


def test_readme_check_fails_on_stale_block(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("<!-- numbers:start -->\nstale\n<!-- numbers:end -->\n")
    assert reproduce_readme.main(["--check", "--readme", str(readme)]) == 1
    assert reproduce_readme.main(["--readme", str(readme)]) == 0
    assert reproduce_readme.main(["--check", "--readme", str(readme)]) == 0


def test_examples_check_detects_changes(tmp_path: Path) -> None:
    assert make_examples.main(["--root", str(tmp_path)]) == 0
    assert make_examples.main(["--check", "--root", str(tmp_path)]) == 0
    target = tmp_path / "ledgercheck-seed42-12m" / "items_to_check.csv"
    target.write_text(target.read_text() + "x\n")
    assert make_examples.main(["--check", "--root", str(tmp_path)]) == 1
    extra = tmp_path / "synthbiz-seed42-12m" / "extra.txt"
    extra.write_text("x")
    assert make_examples.main(["--check", "--root", str(tmp_path)]) == 1


def test_shipped_examples_are_current() -> None:
    assert make_examples.main(["--check"]) == 0


def test_readme_numbers_are_current() -> None:
    assert reproduce_readme.main(["--check"]) == 0
