import re
import sys
import tomllib
from pathlib import Path

from ledgercheck import benford, config, duplicates, evaluate, io, models

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text("utf-8")
ADR = ROOT / "docs/adr"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "benchmarks"))

import bench  # noqa: E402
import reproduce_readme  # noqa: E402


def adr(name: str) -> str:
    return (ADR / name).read_text("utf-8")


def limits_text() -> str:
    return README.split("## Limits", 1)[1].split("## Demo", 1)[0]


def benchmark_sections() -> list[reproduce_readme.Section]:
    text = (ROOT / "docs/benchmark.md").read_text("utf-8")
    return reproduce_readme.parse_benchmark(text)


def test_input_caps_match_the_code() -> None:
    phrases = [
        f"{io.MAX_ROWS_PER_FILE:,} rows per file",
        f"{io.MAX_TOTAL_ROWS:,} rows in the folder",
        f"{io.MAX_FILE_BYTES:,} bytes per file",
        f"{io.MAX_TOTAL_BYTES:,} bytes in the folder",
        f"{io.FIELD_CAP} characters in a field",
        f"{io.NAME_CAP} characters in a vendor name",
        f"max_cell_steps ({models.DuplicateSettings().max_cell_steps:,}",
    ]
    for phrase in phrases:
        assert phrase in limits_text(), phrase
    for phrase in phrases[:-1]:
        assert phrase in adr("0005-work-budget-and-input-caps.md"), phrase


def test_adr_budget_facts_match_the_code() -> None:
    text = adr("0005-work-budget-and-input-caps.md")
    steps = models.DuplicateSettings().max_cell_steps
    assert f"{steps:,} by default" in text
    assert f"{duplicates.COMPARE_COST} steps per compare" in text
    assert f"capped at {config.MAX_JSON_BYTES:,} bytes" in text


def test_name_cap_in_adr_matches_the_code() -> None:
    text = adr("0004-fuzzy-duplicates-are-blocked.md")
    assert f"capped at {duplicates.NAME_CAP} characters" in text


def test_benford_threshold_in_adr_matches_the_code() -> None:
    text = adr("0009-benford-is-a-status-line.md")
    assert f"under {benford.WEAK_SAMPLE_BELOW:,} values" in text


def test_evaluate_facts_match_the_code() -> None:
    expected = (
        f"{evaluate.MAX_TUNE_SEEDS} tuning seeds, "
        f"{evaluate.MAX_REPORT_SEEDS} report seeds"
    )
    assert expected in README
    assert f"at most {evaluate.MAX_WORK:,}" in README
    assert f"({evaluate.DRAWS:,} draws" in README


def test_nine_scored_rules() -> None:
    assert len(evaluate.SCORED_RULES) == 9
    assert "nine scored rules" in README
    assert "scores nine rules" in README


def test_python_version_matches_pyproject() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    assert data["project"]["requires-python"] == ">=3.11"
    assert "Python 3.11 or newer" in README


def test_pinned_commit_matches_pyproject() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    pins = data["project"]["optional-dependencies"]["eval"]
    sha = re.search(r"@([0-9a-f]{40})", pins[0])
    assert sha is not None
    assert sha.group(1) in README
    assert sha.group(1) in adr("0008-synthbiz-pinned-by-commit.md")


def test_different_amount_figure_matches_the_benchmark() -> None:
    long_run = [s for s in benchmark_sections() if "36" in s.title][0]
    assert f"found {long_run.different_amount} different-amount pairs" in limits_text()
    all_pairs = long_run.rows["all-pairs fuzzy"]["near TP/FP/miss"]
    false_positives = all_pairs.split("/")[1]
    assert f"{false_positives} near duplicate false positives" in limits_text()
    assert f"shows {false_positives} near duplicate false positives" in adr(
        "0004-fuzzy-duplicates-are-blocked.md"
    )


def test_adr_compare_counts_appear_in_the_benchmark() -> None:
    long_run = [s for s in benchmark_sections() if "36" in s.title][0]
    text = adr("0004-fuzzy-duplicates-are-blocked.md")
    all_pairs = long_run.rows["all-pairs fuzzy"]
    blocked = long_run.rows["blocked fuzzy"]
    for row in (all_pairs, blocked):
        assert row["pair compares"] in text
        assert row["time s"] in text


def test_fast_benchmark_methods_match_the_file() -> None:
    from synthbiz.generate import Params, generate

    from ledgercheck.evaluate import labels_from_dataset, ledger_from_dataset

    ds = generate(
        Params(seed=bench.SEED, size="large", months=12, anomaly_rate=bench.RATE)
    )
    led = ledger_from_dataset(ds.tables)
    labels = labels_from_dataset(ds.labels)
    cfg = models.DuplicateSettings()
    section = [s for s in benchmark_sections() if "12 months" in s.title][0]
    blocked = section.rows["blocked fuzzy"]
    exact = section.rows["exact key only"]
    assert (
        str(duplicates.find_duplicates(led, cfg).compares) == blocked["pair compares"]
    )
    for method, flags in (
        ("blocked fuzzy", bench.blocked(led, cfg)),
        ("exact key only", bench.exact_only(led)),
    ):
        tp, fp, miss, _p, recall = bench.accuracy(flags, labels, led)["duplicate_fuzzy"]
        row = section.rows[method]
        assert row["near TP/FP/miss"] == f"{tp}/{fp}/{miss}"
        assert row["near R"] == f"{recall:.3f}"
    assert exact["pair compares"] == "0"


def test_no_network_imports_in_the_package() -> None:
    banned = re.compile(
        r"^\s*(import|from)\s+(socket|urllib|http|requests|ssl|ftplib|smtplib)\b",
        re.M,
    )
    for path in (ROOT / "src/ledgercheck").glob("*.py"):
        assert banned.search(path.read_text("utf-8")) is None, path.name


def test_examples_have_no_tax_id_pattern() -> None:
    pattern = re.compile(r"\b[0-9]{2}-[0-9]{7}\b")
    for path in (ROOT / "examples").rglob("*"):
        if path.is_file():
            assert pattern.search(path.read_text("utf-8")) is None, path.name


def test_quick_run_text_matches_the_readme() -> None:
    assert "3 months" in bench.QUICK_LINE
    assert "3 month" in README


def test_typo_recall_in_the_block_matches_measured_json() -> None:
    import json

    data = json.loads((ROOT / "src/ledgercheck/measured.json").read_text("utf-8"))
    typo = data["any_rule"]["typo_duplicate_payment"]
    assert f"recall {typo['recall']:.4f}" in README
    assert typo["recall"] < 1.0


def test_only_exact_duplicates_keep_a_precision_of_one() -> None:
    import json

    data = json.loads((ROOT / "src/ledgercheck/measured.json").read_text("utf-8"))
    perfect = [k for k, r in data["rules"].items() if r["precision"] == 1.0]
    assert perfect == ["duplicate_exact"]
