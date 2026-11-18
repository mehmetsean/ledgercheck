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
    assert main(["run", str(synthetic), "--out", str(out), "--force"]) == 2
    assert (out / "keep.txt").read_text() == "mine"
    assert not (out / "analysis.md").exists()
    (out / "keep.txt").unlink()
    assert main(["run", str(synthetic), "--out", str(out)]) == 0
    assert main(["run", str(synthetic), "--out", str(out)]) == 2
    assert main(["run", str(synthetic), "--out", str(out), "--force"]) == 0


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


def test_cells_with_control_characters_and_leading_spaces() -> None:
    assert report.safe_cell("\x1b[31mred") == "\\x1b[31mred"
    assert report.safe_cell("a\x7fb") == "a\\x7fb"
    assert report.safe_cell("  =SUM(A1)") == "'  =SUM(A1)"
    assert report.safe_cell("\tcmd") == "'\\x09cmd"
    assert report.safe_cell("\ncmd") == "'\\x0acmd"
    assert report.safe_cell("\rcmd") == "'\\x0dcmd"
    assert report.safe_cell("+1") == "'+1"
    assert report.safe_cell("@x") == "'@x"
    assert report.safe_cell("plain text") == "plain text"


def test_csv_file_has_no_control_characters(tmp_path: Path) -> None:
    flags = [Flag("weekend_posting", "journal_lines", "a\x1bb", ("r",), "line\nbreak")]
    report.write_report(tmp_path / "o", small_result(flags))
    text = (tmp_path / "o" / "items_to_check.csv").read_text("utf-8")
    assert "\x1b" not in text
    assert "a\\x1bb" in text
    assert len(text.splitlines()) == 2


def test_out_inside_or_equal_to_data_is_refused(
    synthetic: Path, tmp_path: Path
) -> None:
    assert main(["run", str(synthetic), "--out", str(synthetic)]) == 2
    assert main(["run", str(synthetic), "--out", str(synthetic / "results")]) == 2
    assert not (synthetic / "results").exists()


def test_force_never_deletes_other_files(synthetic: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "README.txt").write_text("old")
    (out / "notes.txt").write_text("mine")
    assert main(["run", str(synthetic), "--out", str(out), "--force"]) == 2
    assert (out / "README.txt").read_text() == "old"
    assert (out / "notes.txt").read_text() == "mine"


def test_files_are_replaced_in_one_step(
    synthetic: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    assert main(["run", str(synthetic), "--out", str(out)]) == 0
    before = (out / "analysis.md").read_text("utf-8")
    calls: list[str] = []
    real = report.os.replace

    def spy(src: Path, dst: Path) -> None:
        calls.append(Path(dst).name)
        real(src, dst)

    monkeypatch.setattr(report.os, "replace", spy)
    assert main(["run", str(synthetic), "--out", str(out), "--force"]) == 0
    assert sorted(calls) == sorted(report.FILES)
    assert (out / "analysis.md").read_text("utf-8") == before
    assert sorted(p.name for p in out.iterdir()) == sorted(report.FILES)


def test_temp_file_is_removed_when_a_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(src: Path, dst: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(report.os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        report.write_report(tmp_path / "o", small_result([]))
    assert list((tmp_path / "o").iterdir()) == []


def test_empty_benford_section_is_written(tmp_path: Path) -> None:
    result = small_result([])
    empty = AnalysisResult(
        result.flags, result.counts, result.skips, [], result.table_rows, 0, 0
    )
    assert "SKIP: no amount field in the input." in report.markdown(empty)
    assert "SKIP: no amount field in the input." in report.page(empty)


def test_report_lists_skipped_entry_ids() -> None:
    result = analyze(read_folder_from_lines(), Settings())
    assert result.unnumbered_ids == 1
    assert "skipped by entry_number_gap: 1" in report.markdown(result)


def read_folder_from_lines():  # type: ignore[no-untyped-def]
    from helpers import ledger, line

    return ledger(lines=[line(je="alpha"), line(je="JE-1")])


def test_settings_with_a_400_digit_limit_gives_one_plain_line(
    synthetic: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "s.json"
    path.write_text('{"approval_limit_cents": ' + "9" * 400 + "}")
    code = main(
        ["run", str(synthetic), "--out", str(tmp_path / "o"), "--settings", str(path)]
    )
    err = capsys.readouterr().err
    assert code == 2
    assert len(err.strip().splitlines()) == 1
    assert "Traceback" not in err


@pytest.mark.parametrize("exc", [MemoryError, OverflowError, RecursionError])
def test_resource_errors_print_one_line(
    exc: type[Exception],
    synthetic: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ledgercheck import cli

    def boom(*args: object) -> None:
        raise exc

    monkeypatch.setattr(cli, "analyze", boom)
    code = main(["run", str(synthetic), "--out", str(tmp_path / "o")])
    assert code == 1
    assert (
        capsys.readouterr().err == "ledgercheck: out of memory or numbers too large\n"
    )


def test_odd_path_is_printed_as_ascii(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["run", str(tmp_path / "no\x1bfolder"), "--out", str(tmp_path / "o")])
    err = capsys.readouterr().err
    assert code == 2
    assert "\x1b" not in err
