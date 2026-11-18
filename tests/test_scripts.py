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


def test_readme_check_reports_missing_markers(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("no markers here\n")
    assert reproduce_readme.main(["--check", "--readme", str(readme)]) == 2


def test_readme_check_reports_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "README.md"
    assert reproduce_readme.main(["--check", "--readme", str(missing)]) == 2


def test_examples_check_fails_when_root_is_missing(tmp_path: Path) -> None:
    assert make_examples.main(["--check", "--root", str(tmp_path / "nope")]) == 1


def test_read_all_skips_folders(tmp_path: Path) -> None:
    for name in (make_examples.DATA, make_examples.OUT):
        (tmp_path / name / "sub").mkdir(parents=True)
        (tmp_path / name / "a.txt").write_text("x")
    files = make_examples.read_all(tmp_path)
    expected = [f"{make_examples.DATA}/a.txt", f"{make_examples.OUT}/a.txt"]
    assert sorted(files) == sorted(expected)


def test_count_note_explains_flags_and_units() -> None:
    data = {
        "report_seeds": [1, 2, 3],
        "rules": {
            "split_under_limit": {
                "flags": 10,
                "true_positives": 6,
                "false_positives": 5,
            }
        },
    }
    note = reproduce_readme.count_note(data)
    assert "summed over the 3 report seeds" in note
    assert "10 flags, 6 true positives plus 5 false positives is 11" in note
