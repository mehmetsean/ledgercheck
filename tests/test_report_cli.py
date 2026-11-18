import ast
import csv
import shutil
from pathlib import Path

import pytest
from synthbiz.generate import Params, generate
from synthbiz.io import write_dataset

from ledgercheck import report
from ledgercheck.analyze import AnalysisResult, analyze
from ledgercheck.benford import benford_first_digit
from ledgercheck.cli import main
from ledgercheck.io import read_folder
from ledgercheck.models import Flag, Settings
from ledgercheck.rules import RULES

SRC = Path(__file__).parent.parent / "src" / "ledgercheck"


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("synthetic")
    ds = generate(Params(seed=42, size="small", months=12))
    write_dataset(ds, folder)
    return folder


def small_result(flags: list[Flag]) -> AnalysisResult:
    return AnalysisResult(
        flags=flags,
        counts={r: 0 for r in RULES},
        skips={"no_approver": "needs journal_lines, which is not in the input"},
        benford=[benford_first_digit([1, 2, 3], "amount_cents")],
        table_rows={"journal_lines": 3, "vendors": None},
        dup_k=0,
        dup_compares=0,
    )


def test_end_to_end_on_synthetic_data(
    synthetic: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    assert main(["run", str(synthetic), "--out", str(out)]) == 0
    assert "items to check" in capsys.readouterr().out
    names = sorted(p.name for p in out.iterdir())
    assert names == sorted(report.FILES)
    for name in ("README.txt", "analysis.md", "analysis.html"):
        text = (out / name).read_text("utf-8")
        assert report.NOTICE in text
        assert report.DISCLAIMER in text
    with (out / "items_to_check.csv").open(newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == report.CSV_HEADER
    assert len(rows) > 1
    md = (out / "analysis.md").read_text("utf-8")
    assert md.index("status") < md.index("| Digit |")


def test_output_never_uses_banned_report_words(synthetic: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    main(["run", str(synthetic), "--out", str(out)])
    for name in ("README.txt", "analysis.md", "analysis.html"):
        text = (out / name).read_text("utf-8").lower()
        assert "audit report" not in text
        assert "review report" not in text
        assert "compilation report" not in text


def test_output_refuses_non_empty_folder_unless_forced(
    synthetic: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep.txt").write_text("mine")
    assert main(["run", str(synthetic), "--out", str(out)]) == 2
    assert not (out / "analysis.md").exists()
    assert main(["run", str(synthetic), "--out", str(out), "--force"]) == 0
    assert (out / "keep.txt").read_text() == "mine"
    assert (out / "analysis.md").exists()


def test_output_path_is_a_file(synthetic: Path, tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("x")
    assert main(["run", str(synthetic), "--out", str(target)]) == 2


def test_input_error_is_one_plain_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "vendors.csv").write_text("vendor_id\nV1\n")
    (data / "ap_payments.csv").write_text("x\n")
    code = main(["run", str(data), "--out", str(tmp_path / "o")])
    err = capsys.readouterr().err
    assert code == 2
    assert err.startswith("error: ")
    assert len(err.strip().splitlines()) == 1
    assert "Traceback" not in err


def test_cli_with_map_and_settings(
    synthetic: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "map.json").write_text('{"amounts": "cents"}')
    (tmp_path / "s.json").write_text('{"approval_limit_cents": 400000}')
    args = ["run", str(synthetic), "--out", str(tmp_path / "o")]
    args += ["--column-map", str(tmp_path / "map.json")]
    args += ["--settings", str(tmp_path / "s.json")]
    assert main(args) == 0
    assert main(args[:4] + ["--settings", str(tmp_path / "none.json")]) == 2


def test_csv_cells_are_escaped(tmp_path: Path) -> None:
    flags = [Flag("weekend_posting", "journal_lines", "=1+1", ("@a",), "-x")]
    report.write_report(tmp_path / "o", small_result(flags))
    with (tmp_path / "o" / "items_to_check.csv").open(newline="") as f:
        rows = list(csv.reader(f))
    assert rows[1][2:] == ["'=1+1", "'@a", "'-x"]
    assert rows[0] == report.CSV_HEADER


def test_html_escapes_values_and_makes_no_requests() -> None:
    reason = "<script>alert(1)</script>"
    page = report.page(small_result([Flag("a", "t", "u", ("r",), reason)]))
    assert "<script" not in page
    for word in ("src=", "href=", "<link", "<iframe", "@import", "url("):
        assert word not in page
    odd = small_result([])
    odd.skips["no_approver"] = "<b>bold</b>"
    assert "&lt;b&gt;bold&lt;/b&gt;" in report.page(odd)


def test_report_shows_skip_and_benford_status_first() -> None:
    text = report.markdown(small_result([]))
    assert "| no_approver | SKIP |" in text
    assert "vendors: not in the input" in text
    assert text.index("status weak_sample") < text.index("| Digit |")


def test_blanking_memo_changes_no_flag(synthetic: Path, tmp_path: Path) -> None:
    copy = tmp_path / "copy"
    shutil.copytree(synthetic, copy)
    path = copy / "journal_lines.csv"
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    memo = rows[0].index("memo")
    for row in rows[1:]:
        row[memo] = ""
    with path.open("w", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    a = analyze(read_folder(synthetic), Settings()).flags
    b = analyze(read_folder(copy), Settings()).flags
    assert a == b


def test_labels_and_manifest_are_not_needed(synthetic: Path, tmp_path: Path) -> None:
    copy = tmp_path / "copy"
    shutil.copytree(synthetic, copy)
    (copy / "labels.csv").unlink()
    (copy / "manifest.json").unlink()
    a = analyze(read_folder(synthetic), Settings()).flags
    b = analyze(read_folder(copy), Settings()).flags
    assert a == b


@pytest.mark.parametrize("name", ["rules.py", "duplicates.py", "benford.py"])
def test_core_modules_do_not_import_evaluate(name: str) -> None:
    tree = ast.parse((SRC / name).read_text("utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""] + [a.name for a in node.names]
        else:
            continue
        assert not any("evaluate" in n for n in names)


def test_only_io_and_report_touch_files() -> None:
    for name in ("rules.py", "duplicates.py", "benford.py", "analyze.py"):
        text = (SRC / name).read_text("utf-8")
        for word in ("open(", "labels", "memo", "socket", "urllib", "requests"):
            assert word not in text


def test_python_dash_m_runs(tmp_path: Path) -> None:
    import subprocess
    import sys

    done = subprocess.run(
        [sys.executable, "-m", "ledgercheck", "run", str(tmp_path / "x"), "--out", "o"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert done.returncode == 2
    assert done.stderr.startswith("error: folder not found")
