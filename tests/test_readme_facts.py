import re
import sys
import tomllib
from pathlib import Path

from ledgercheck import duplicates, evaluate, io, models

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text("utf-8")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "benchmarks"))

import bench  # noqa: E402
import reproduce_readme  # noqa: E402


def limits_text() -> str:
    return README.split("## Limits", 1)[1].split("## Demo", 1)[0]


def test_input_caps_in_limits_match_the_code() -> None:
    text = limits_text()
    for value in (
        io.MAX_ROWS_PER_FILE,
        io.MAX_TOTAL_ROWS,
        io.MAX_FILE_BYTES,
        io.MAX_TOTAL_BYTES,
        io.FIELD_CAP,
        io.NAME_CAP,
        models.DuplicateSettings().max_cell_steps,
    ):
        assert f"{value:,}" in text or f"{value} " in text


def test_evaluate_limits_match_the_code() -> None:
    expected = (
        f"{evaluate.MAX_TUNE_SEEDS} tuning seeds, "
        f"{evaluate.MAX_REPORT_SEEDS} report seeds"
    )
    assert expected in README
    assert f"at most {evaluate.MAX_WORK:,}" in README


def test_pinned_commit_matches_pyproject() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    pins = data["project"]["optional-dependencies"]["eval"]
    sha = re.search(r"@([0-9a-f]{40})", pins[0])
    assert sha is not None
    assert sha.group(1) in README


def test_different_amount_figure_matches_the_benchmark() -> None:
    text = (ROOT / "docs/benchmark.md").read_text("utf-8")
    long_run = [s for s in reproduce_readme.parse_benchmark(text) if "36" in s.title]
    assert f"found {long_run[0].different_amount} vendor-name" in limits_text()


def test_bootstrap_and_quick_facts() -> None:
    assert "2,000 draws" in README
    assert "3 months" in bench.QUICK_LINE
    assert "3 month" in README
    assert duplicates.NAME_CAP == 100
