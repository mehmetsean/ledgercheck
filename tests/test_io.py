import json
from datetime import date
from pathlib import Path

import pytest

from helpers import JOURNAL_HEADER, journal_row, write_csv
from ledgercheck import io
from ledgercheck.config import load_column_map, load_settings
from ledgercheck.models import ColumnMap


def folder_with_journal(tmp_path: Path, rows: list[list[str]]) -> Path:
    write_csv(tmp_path / "journal_lines.csv", JOURNAL_HEADER, rows)
    return tmp_path


def test_reads_journal_lines(tmp_path: Path) -> None:
    folder = folder_with_journal(tmp_path, [journal_row(debit="500", credit="")])
    ledger = io.read_folder(folder)
    assert ledger.invoices is None
    assert ledger.journal_lines is not None
    first = ledger.journal_lines[0]
    assert first.posting_date == date(2025, 3, 5)
    assert first.debit_cents == 500
    assert first.credit_cents == 0
    assert first.created_by == "U1"


def test_bom_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "vendors.csv"
    path.write_bytes(b"\xef\xbb\xbfvendor_id,vendor_name\nV1,Acme Inc\n")
    write_csv(tmp_path / "journal_lines.csv", JOURNAL_HEADER, [journal_row()])
    ledger = io.read_folder(tmp_path)
    assert ledger.vendors is not None
    assert ledger.vendors[0].vendor_name == "Acme Inc"


def test_memo_is_never_parsed(tmp_path: Path) -> None:
    long_memo = "x" * 50_000
    folder = folder_with_journal(tmp_path, [journal_row(memo=long_memo)])
    assert io.read_folder(folder).journal_lines is not None


def test_missing_folder() -> None:
    with pytest.raises(ValueError, match="folder not found"):
        io.read_folder(Path("/no/such/folder"))


def test_no_tables(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no table files"):
        io.read_folder(tmp_path)


def test_missing_column(tmp_path: Path) -> None:
    header = [h for h in JOURNAL_HEADER if h != "period"]
    write_csv(tmp_path / "journal_lines.csv", header, [])
    with pytest.raises(ValueError, match="journal_lines.csv: missing required column"):
        io.read_folder(tmp_path)


def test_duplicate_column(tmp_path: Path) -> None:
    write_csv(tmp_path / "journal_lines.csv", JOURNAL_HEADER + ["period"], [])
    with pytest.raises(ValueError, match="appears twice"):
        io.read_folder(tmp_path)


def test_empty_file(tmp_path: Path) -> None:
    (tmp_path / "journal_lines.csv").write_text("")
    with pytest.raises(ValueError, match="file is empty"):
        io.read_folder(tmp_path)


@pytest.mark.parametrize(
    ("changes", "column"),
    [
        ({"day": "2025-3-5"}, "posting_date"),
        ({"day": "2025-02-30"}, "posting_date"),
        ({"debit": "12.5"}, "debit_cents"),
        ({"debit": "1" * 19}, "debit_cents"),
        ({"credit": "abc"}, "credit_cents"),
    ],
)
def test_bad_values_name_file_line_and_column(
    tmp_path: Path, changes: dict[str, str], column: str
) -> None:
    rows = [journal_row(), journal_row(line="L2", **changes)]
    folder = folder_with_journal(tmp_path, rows)
    with pytest.raises(ValueError) as err:
        io.read_folder(folder)
    text = str(err.value)
    assert text.startswith(f"journal_lines.csv: line 3: column {column}:")
    assert "\n" not in text


def test_bad_value_is_not_echoed_raw(tmp_path: Path) -> None:
    folder = folder_with_journal(tmp_path, [journal_row(debit="\x07\x1b[31mred")])
    with pytest.raises(ValueError) as err:
        io.read_folder(folder)
    assert "\x1b" not in str(err.value)
    assert "\x07" not in str(err.value)


def test_wrong_field_count(tmp_path: Path) -> None:
    folder = folder_with_journal(tmp_path, [journal_row()[:-1]])
    with pytest.raises(ValueError, match="line 2: has 12 fields"):
        io.read_folder(folder)


def test_malformed_csv(tmp_path: Path) -> None:
    text = ",".join(JOURNAL_HEADER) + '\nL1,"bad"x,1\n'
    (tmp_path / "journal_lines.csv").write_text(text)
    with pytest.raises(ValueError, match="not valid CSV"):
        io.read_folder(tmp_path)


def test_not_utf8(tmp_path: Path) -> None:
    (tmp_path / "vendors.csv").write_bytes(b"vendor_id,vendor_name\nV1,\xff\xfe\n")
    write_csv(tmp_path / "journal_lines.csv", JOURNAL_HEADER, [])
    with pytest.raises(ValueError, match="not valid UTF-8"):
        io.read_folder(tmp_path)


def test_huge_field_in_csv_module(tmp_path: Path) -> None:
    folder = folder_with_journal(tmp_path, [journal_row(user="u" * 200_000)])
    with pytest.raises(ValueError, match="not valid CSV"):
        io.read_folder(folder)


def test_long_text_field(tmp_path: Path) -> None:
    folder = folder_with_journal(tmp_path, [journal_row(user="u" * 5_000)])
    with pytest.raises(ValueError, match="column created_by: text longer than"):
        io.read_folder(folder)


def test_row_cap_per_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(io, "MAX_ROWS_PER_FILE", 2)
    rows = [journal_row(line=f"L{i}") for i in range(3)]
    with pytest.raises(ValueError, match="more than 2 rows"):
        io.read_folder(folder_with_journal(tmp_path, rows))


def test_row_cap_per_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(io, "MAX_TOTAL_ROWS", 2)
    write_csv(tmp_path / "vendors.csv", ["vendor_id", "vendor_name"], [["V1", "A"]])
    rows = [journal_row(line=f"L{i}") for i in range(2)]
    with pytest.raises(ValueError, match="folder has more than 2 rows"):
        io.read_folder(folder_with_journal(tmp_path, rows))


def test_unreadable_file(tmp_path: Path) -> None:
    (tmp_path / "journal_lines.csv").mkdir()
    with pytest.raises(ValueError, match="no table files"):
        io.read_folder(tmp_path)


def write_map(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "map.json"
    path.write_text(json.dumps(data))
    return path


def test_column_map_with_dollars(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    write_csv(
        data / "gl.csv",
        ["Line", "Entry", "Date", "Per", "Acct", "Dr", "Cr", "Src", "By", "OK"],
        [["1", "E1", "03/08/2025", "2025-03", "1000", "12.50", "", "MANUAL", "u", ""]],
    )
    cmap = load_column_map(
        write_map(
            tmp_path,
            {
                "files": {"journal_lines": "gl.csv"},
                "columns": {
                    "journal_lines": {
                        "line_id": "Line",
                        "je_id": "Entry",
                        "posting_date": "Date",
                        "period": "Per",
                        "account_id": "Acct",
                        "debit_cents": "Dr",
                        "credit_cents": "Cr",
                        "source_type": "Src",
                        "created_by": "By",
                        "approved_by": "OK",
                    }
                },
                "date_format": "%m/%d/%Y",
                "amounts": "dollars",
            },
        )
    )
    ledger = io.read_folder(data, cmap)
    assert ledger.journal_lines is not None
    first = ledger.journal_lines[0]
    assert first.debit_cents == 1250
    assert first.posting_date == date(2025, 3, 8)


def test_dollars_allow_two_decimals_only(tmp_path: Path) -> None:
    folder = folder_with_journal(tmp_path, [journal_row(debit="1.234")])
    with pytest.raises(ValueError, match="not an amount in dollars"):
        io.read_folder(folder, ColumnMap(amounts="dollars"))


def test_custom_date_format_error(tmp_path: Path) -> None:
    folder = folder_with_journal(tmp_path, [journal_row(day="2025-03-05")])
    with pytest.raises(ValueError, match="column posting_date"):
        io.read_folder(folder, ColumnMap(date_format="%m/%d/%Y"))


def test_file_name_with_folder_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must not contain a folder"):
        io.read_folder(tmp_path, ColumnMap(files={"vendors": "../x.csv"}))


@pytest.mark.parametrize(
    "data",
    [
        [],
        {"files": {"nope": "a.csv"}},
        {"files": {"vendors": 5}},
        {"columns": {"vendors": {"vendor_id": ""}}},
        {"columns": {"vendors": {"memo": "m"}}},
        {"columns": []},
        {"amounts": "euros"},
        {"date_format": "%Q"},
        {"date_format": 5},
        {"other": 1},
    ],
)
def test_bad_column_map(tmp_path: Path, data: object) -> None:
    with pytest.raises(ValueError, match="map.json"):
        load_column_map(write_map(tmp_path, data))


def test_column_map_not_json(tmp_path: Path) -> None:
    path = tmp_path / "map.json"
    path.write_text("{")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_column_map(path)
    with pytest.raises(ValueError, match="could not read"):
        load_column_map(tmp_path / "missing.json")


def test_settings_file(tmp_path: Path) -> None:
    path = write_map(
        tmp_path,
        {
            "approval_limit_cents": 100,
            "rare_share": 1,
            "extra_holidays": ["2025-03-07"],
            "duplicates": {"window_days": 3},
        },
    )
    s = load_settings(path)
    assert s.approval_limit_cents == 100
    assert s.rare_share == 1.0
    assert s.extra_holidays == (date(2025, 3, 7),)
    assert s.duplicates.window_days == 3


@pytest.mark.parametrize(
    "data",
    [
        {"approval_limit_cents": "5"},
        {"approval_limit_cents": True},
        {"approval_limit_cents": 0},
        {"unknown": 1},
        {"rare_share": 2},
        {"extra_holidays": "2025-01-01"},
        {"extra_holidays": ["soon"]},
        {"duplicates": 5},
        {"duplicates": {"name_threshold": 3}},
        {"us_holidays": 1},
    ],
)
def test_bad_settings(tmp_path: Path, data: object) -> None:
    with pytest.raises(ValueError, match="map.json"):
        load_settings(write_map(tmp_path, data))
