import csv
import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from ledgercheck import demo
from ledgercheck.cli import main
from ledgercheck.evaluate import DEFAULT_COSTS, Label, evaluate_folder
from ledgercheck.models import Flag, Ledger, Payment, Settings

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
    with pytest.raises(ValueError, match="not used"):
        demo.run_files(str(folder), {"vendors": {"columns": {}}})
    with pytest.raises(ValueError, match="file not found"):
        demo.run_files(str(folder), {"vendors": {"file": "gone.csv", "columns": {}}})
    with pytest.raises(ValueError, match="no table files"):
        demo.run_files(str(folder), {"vendors": {"file": "a.csv", "columns": {}}})
    with pytest.raises(ValueError, match="date_format"):
        demo.run_files(str(folder), identity(folder), date_format="nope")


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


def test_table_fields_match_the_reader() -> None:
    from ledgercheck.io import SPECS

    fields = demo.table_fields()
    assert list(fields) == list(SPECS)
    assert fields["vendors"] == ["vendor_id", "vendor_name"]
    assert "amount_cents" in fields["ap_payments"]


def test_missed_units_equal_what_score_reports(
    synthetic: dict[str, Any], cli_folder: Path
) -> None:
    scores, _ = evaluate_folder(cli_folder / "d", Settings(), DEFAULT_COSTS)
    for rule, s in scores.rules.items():
        misses = [
            i["reason"]
            for i in synthetic["items"]
            if i["rule"] == rule and i["mark"] == "miss"
        ]
        assert len(misses) == s.misses
        assert tuple(misses[:5]) == s.missed_details


def hand_built() -> tuple[Ledger, list[Label], list[Flag]]:
    day = date(2025, 3, 3)
    pays = tuple(Payment(f"P{i}", "V1", f"I{i}", day, 100 * i) for i in (1, 2, 3, 4))
    ledger = Ledger(payments=pays)
    labels = [
        Label("ap_payments", "P1", "exact_duplicate_payment", "first"),
        Label("ap_payments", "P2", "near_duplicate_payment", "second"),
        Label("ap_payments", "P4", "near_duplicate_payment", "fourth"),
    ]
    flags = [
        Flag("duplicate_exact", "ap_payments", "P1", ("P1",), "r"),
        Flag("duplicate_exact", "ap_payments", "P2", ("P2",), "r"),
        Flag("duplicate_exact", "ap_payments", "P3", ("P3",), "r"),
        Flag("entry_number_gap", "journal_lines", "JE-9", ("L9",), "r"),
        Flag("benford_first_digit", "ap_payments", "x", (), "r"),
    ]
    return ledger, labels, flags


def test_marks_on_a_hand_built_ledger() -> None:
    ledger, labels, flags = hand_built()
    items = demo._marks(flags, labels, ledger, set())
    marks = [(i["rule"], i["unit_id"], i["mark"]) for i in items]
    assert marks == [
        ("duplicate_exact", "P1", "hit"),
        ("duplicate_exact", "P2", "other_label"),
        ("duplicate_exact", "P3", "false_alarm"),
        ("entry_number_gap", "JE-9", "not_scored"),
        ("benford_first_digit", "x", "not_scored"),
        ("duplicate_fuzzy", "P2", "miss"),
        ("duplicate_fuzzy", "P4", "miss"),
    ]
    assert [i["reason"] for i in items[-2:]] == ["second", "fourth"]


def test_a_skipped_rule_has_no_miss_rows() -> None:
    ledger, labels, flags = hand_built()
    items = demo._marks(flags, labels, ledger, {"duplicate_fuzzy"})
    assert [i for i in items if i["mark"] == "miss"] == []


def test_unscored_label_types_are_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    real = demo.read_labels

    def with_extra(folder: Path) -> list[Label]:
        labels = real(folder)
        pay = next(x for x in labels if x.table == "ap_payments")
        return labels + [Label("ap_payments", pay.row_id, "mystery_type", "x")]

    monkeypatch.setattr(demo, "read_labels", with_extra)
    assert demo.run_synthetic(SEED, MONTHS, SIZE, RATE)["unscored"] == {
        "mystery_type": 1
    }
