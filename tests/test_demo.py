import csv
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from ledgercheck import demo
from ledgercheck.cli import main
from ledgercheck.evaluate import DEFAULT_COSTS, evaluate_folder
from ledgercheck.models import Settings

ROOT = Path(__file__).parent.parent
EXAMPLE_DATA = ROOT / "examples" / "synthbiz-seed42-12m"
EXAMPLE_OUT = ROOT / "examples" / "ledgercheck-seed42-12m"
SEED, MONTHS, SIZE, RATE = 7, 3, "small", 0.1


@pytest.fixture(scope="module")
def synthetic() -> dict[str, Any]:
    return demo.run_synthetic(SEED, MONTHS, SIZE, RATE)


@pytest.fixture(scope="module")
def cli_folder(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("cli")
    from synthbiz.cli import main as synthbiz_main

    args = ["generate", "--seed", str(SEED), "--months", str(MONTHS)]
    args += ["--size", SIZE, "--anomaly-rate", str(RATE), "--out", str(base / "d")]
    assert synthbiz_main(args) in (0, None)
    assert main(["run", str(base / "d"), "--out", str(base / "o")]) == 0
    return base


def test_result_is_json_friendly(synthetic: dict[str, Any]) -> None:
    assert json.loads(json.dumps(synthetic)) == synthetic


def test_items_csv_equals_the_cli_output(
    synthetic: dict[str, Any], cli_folder: Path
) -> None:
    text = (cli_folder / "o" / "items_to_check.csv").read_text("utf-8")
    assert synthetic["items_csv"] == text


def test_rule_scores_equal_the_cli_scores(
    synthetic: dict[str, Any], cli_folder: Path
) -> None:
    scores, labels = evaluate_folder(cli_folder / "d", Settings(), DEFAULT_COSTS)
    assert synthetic["info"]["labels"] == labels
    rows = {r["rule"]: r for r in synthetic["rules"]}
    assert list(rows) == list(scores.rules)
    for rule, s in scores.rules.items():
        r = rows[rule]
        assert (r["labeled"], r["flags"], r["tp"], r["fp"]) == (
            s.labeled,
            s.flags,
            s.tp,
            s.fp,
        )
        assert (r["other_label"], r["misses"]) == (s.other_label, s.misses)


def test_marks_add_up_to_the_scores(synthetic: dict[str, Any]) -> None:
    for r in synthetic["rules"]:
        mine = [i for i in synthetic["items"] if i["rule"] == r["rule"]]
        marks = [i["mark"] for i in mine]
        assert marks.count("false_alarm") == r["fp"]
        assert marks.count("other_label") == r["other_label"]
        assert marks.count("miss") == r["misses"]
        assert marks.count("hit") >= 1 or r["tp"] == 0
        assert marks.count("hit") + marks.count("miss") >= r["labeled"]


def test_rates_are_between_zero_and_one(synthetic: dict[str, Any]) -> None:
    for r in synthetic["rules"]:
        for key in ("precision", "recall", "f1"):
            assert r[key] is None or 0.0 <= r[key] <= 1.0


def test_benford_lines_and_text(synthetic: dict[str, Any]) -> None:
    assert synthetic["benford"]
    for b in synthetic["benford"]:
        assert b["line"].startswith(b["field"] + ": status " + b["status"])
        assert len(b["counts"]) == len(b["expected"]) == 9
    assert "Decision support only" in synthetic["disclaimer"]
    assert synthetic["notice"].startswith("All rights reserved.")


def test_same_inputs_give_the_same_result(synthetic: dict[str, Any]) -> None:
    assert demo.run_synthetic(SEED, MONTHS, SIZE, RATE) == synthetic


@pytest.mark.parametrize(
    "args,text",
    [
        ((-1, 3, "small", 0.1), "seed"),
        ((1.5, 3, "small", 0.1), "seed"),
        ((True, 3, "small", 0.1), "seed"),
        ((1, 0, "small", 0.1), "months"),
        ((1, 25, "small", 0.1), "months"),
        ((1, 3, "huge", 0.1), "size"),
        ((1, 3, "small", 0.3), "rate"),
        ((1, 3, "small", -0.1), "rate"),
        ((1, 3, "small", "x"), "rate"),
    ],
)
def test_bad_synthetic_inputs_say_what_to_do(args: Any, text: str) -> None:
    with pytest.raises(ValueError, match=text):
        demo.run_synthetic(*args)


def identity(folder: Path) -> dict[str, dict[str, Any]]:
    return {
        t: {"file": f"{t}.csv", "columns": {}}
        for t in ("journal_lines", "ap_invoices", "ap_payments", "vendors")
    }


def test_files_mode_equals_the_shipped_example(tmp_path: Path) -> None:
    folder = tmp_path / "in"
    shutil.copytree(EXAMPLE_DATA, folder)
    result = demo.run_files(str(folder), identity(folder))
    want = (EXAMPLE_OUT / "items_to_check.csv").read_text("utf-8")
    assert result["items_csv"] == want
    assert result["mode"] == "files"
    assert result["rules"] == []
    assert {i["mark"] for i in result["items"]} == {"to_check"}
    assert len(result["items"]) == want.count("\n") - 1


def write(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def test_files_mode_with_renamed_columns_and_dollars(tmp_path: Path) -> None:
    folder = tmp_path / "in"
    folder.mkdir()
    write(
        folder / "bills.csv",
        ["Bill", "Supplier", "Number", "Date", "Total"],
        [["I1", "V1", "A-1", "2025-03-03", "4,000.00".replace(",", "")]],
    )
    tables = {
        "ap_invoices": {
            "file": "bills.csv",
            "columns": {
                "invoice_id": "Bill",
                "vendor_id": "Supplier",
                "invoice_number": "Number",
                "invoice_date": "Date",
                "amount_cents": "Total",
            },
        }
    }
    result = demo.run_files(str(folder), tables, amounts="dollars")
    assert result["tables"]["ap_invoices"] == 1
    assert result["tables"]["ap_payments"] is None
    assert result["items"] == []


def test_files_mode_does_not_read_a_table_the_user_left_out(tmp_path: Path) -> None:
    folder = tmp_path / "in"
    shutil.copytree(EXAMPLE_DATA, folder)
    only = {"ap_invoices": identity(folder)["ap_invoices"]}
    result = demo.run_files(str(folder), only)
    assert result["tables"] == {
        "journal_lines": None,
        "ap_invoices": result["tables"]["ap_invoices"],
        "ap_payments": None,
        "vendors": None,
    }


def test_files_mode_errors_say_what_to_do(tmp_path: Path) -> None:
    folder = tmp_path / "in"
    folder.mkdir()
    with pytest.raises(ValueError, match="Choose a file"):
        demo.run_files(str(folder), {})
    write(folder / "a.csv", ["x"], [["1"]])
    with pytest.raises(ValueError, match="missing required column"):
        demo.run_files(str(folder), {"vendors": {"file": "a.csv", "columns": {}}})
    with pytest.raises(ValueError, match="table"):
        demo.run_files(str(folder), {"nope": {"file": "a.csv", "columns": {}}})
    with pytest.raises(ValueError, match="amounts"):
        demo.run_files(str(folder), identity(folder), amounts="euros")
    with pytest.raises(ValueError, match="file"):
        demo.run_files(str(folder), {"vendors": {"columns": {}}})


def test_read_header(tmp_path: Path) -> None:
    folder = tmp_path / "in"
    folder.mkdir()
    write(folder / "a.csv", ["id", "name"], [["1", "x"]])
    assert demo.read_header(str(folder), "a.csv") == ["id", "name"]
    (folder / "empty.csv").write_text("", "utf-8")
    with pytest.raises(ValueError, match="empty"):
        demo.read_header(str(folder), "empty.csv")
    with pytest.raises(ValueError, match="could not read"):
        demo.read_header(str(folder), "missing.csv")
    (folder / "bad.csv").write_bytes(b"\xff\xfe\x00")
    with pytest.raises(ValueError, match="UTF-8"):
        demo.read_header(str(folder), "bad.csv")


def test_prepare_folder_empties_it(tmp_path: Path) -> None:
    folder = tmp_path / "work"
    folder.mkdir()
    (folder / "old.csv").write_text("x", "utf-8")
    demo.prepare_folder(str(folder))
    assert folder.is_dir() and list(folder.iterdir()) == []
    demo.prepare_folder(str(tmp_path / "new"))
    assert (tmp_path / "new").is_dir()
