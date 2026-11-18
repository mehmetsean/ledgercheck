"""Read CSV tables into a Ledger. Only the listed columns are read."""

import csv
import re
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from .models import (
    ColumnMap,
    Invoice,
    JournalLine,
    Ledger,
    Payment,
    Vendor,
)

MAX_ROWS_PER_FILE = 3_000_000
MAX_TOTAL_ROWS = 5_000_000
MAX_FIELD_CHARS = 1_000

TEXT = "text"
DATE = "date"
MONEY = "money"
MONEY_OR_BLANK = "money_or_blank"

SPECS: dict[str, tuple[tuple[str, str], ...]] = {
    "journal_lines": (
        ("line_id", TEXT),
        ("je_id", TEXT),
        ("posting_date", DATE),
        ("period", TEXT),
        ("account_id", TEXT),
        ("debit_cents", MONEY_OR_BLANK),
        ("credit_cents", MONEY_OR_BLANK),
        ("source_type", TEXT),
        ("created_by", TEXT),
        ("approved_by", TEXT),
    ),
    "ap_invoices": (
        ("invoice_id", TEXT),
        ("vendor_id", TEXT),
        ("invoice_number", TEXT),
        ("invoice_date", DATE),
        ("amount_cents", MONEY),
    ),
    "ap_payments": (
        ("payment_id", TEXT),
        ("vendor_id", TEXT),
        ("invoice_id", TEXT),
        ("payment_date", DATE),
        ("amount_cents", MONEY),
    ),
    "vendors": (
        ("vendor_id", TEXT),
        ("vendor_name", TEXT),
    ),
}

INT_RE = re.compile(r"-?[0-9]{1,18}")
DOLLAR_RE = re.compile(r"-?[0-9]{1,16}(\.[0-9]{1,2})?")
ISO_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


class _Budget:
    def __init__(self) -> None:
        self.total = 0

    def add(self, name: str) -> None:
        self.total += 1
        if self.total > MAX_TOTAL_ROWS:
            raise ValueError(f"{name}: folder has more than {MAX_TOTAL_ROWS} rows")


def _show(value: str) -> str:
    return ascii(value[:40])


def _fail(name: str, line: int, column: str, message: str) -> ValueError:
    return ValueError(f"{name}: line {line}: column {column}: {message}")


def _parse_date(value: str, fmt: str, name: str, line: int, column: str) -> date:
    try:
        if fmt == "%Y-%m-%d":
            if not ISO_RE.fullmatch(value):
                raise ValueError(value)
            return date.fromisoformat(value)
        if len(value) > 40:
            raise ValueError(value)
        return datetime.strptime(value, fmt).date()
    except ValueError:
        raise _fail(
            name, line, column, f"not a date in the form {fmt}: {_show(value)}"
        ) from None


def _parse_money(
    value: str, amounts: str, name: str, line: int, column: str, blank_ok: bool
) -> int:
    if value == "" and blank_ok:
        return 0
    if amounts == "dollars":
        if not DOLLAR_RE.fullmatch(value):
            raise _fail(name, line, column, f"not an amount in dollars: {_show(value)}")
        return int(Decimal(value) * 100)
    if not INT_RE.fullmatch(value):
        raise _fail(name, line, column, f"not an integer in cents: {_show(value)}")
    return int(value)


def _convert(
    kind: str, value: str, cmap: ColumnMap, name: str, line: int, column: str
) -> Any:
    if kind == TEXT:
        if len(value) > MAX_FIELD_CHARS:
            raise _fail(name, line, column, f"text longer than {MAX_FIELD_CHARS}")
        return value
    if kind == DATE:
        return _parse_date(value, cmap.date_format, name, line, column)
    return _parse_money(value, cmap.amounts, name, line, column, kind == MONEY_OR_BLANK)


def _header_positions(
    name: str, header: list[str], table: str, cmap: ColumnMap
) -> list[int]:
    names = cmap.columns.get(table, {})
    positions: list[int] = []
    for field, _ in SPECS[table]:
        wanted = names.get(field, field)
        if header.count(wanted) > 1:
            raise ValueError(f"{name}: column {ascii(wanted)} appears twice")
        if wanted not in header:
            raise ValueError(f"{name}: missing required column {ascii(wanted)}")
        positions.append(header.index(wanted))
    return positions


def _read_rows(
    path: Path, table: str, cmap: ColumnMap, budget: _Budget
) -> list[list[Any]]:
    name = path.name
    spec = SPECS[table]
    rows: list[list[Any]] = []
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f, strict=True)
            header = next(reader, None)
            if header is None:
                raise ValueError(f"{name}: file is empty")
            positions = _header_positions(name, header, table, cmap)
            for row in reader:
                if not row:
                    continue
                line = reader.line_num
                if len(rows) >= MAX_ROWS_PER_FILE:
                    raise ValueError(f"{name}: more than {MAX_ROWS_PER_FILE} rows")
                budget.add(name)
                if len(row) != len(header):
                    raise ValueError(
                        f"{name}: line {line}: has {len(row)} fields, "
                        f"expected {len(header)}"
                    )
                values = []
                for (field, kind), pos in zip(spec, positions, strict=True):
                    column = cmap.columns.get(table, {}).get(field, field)
                    values.append(_convert(kind, row[pos], cmap, name, line, column))
                rows.append(values)
    except UnicodeDecodeError:
        raise ValueError(f"{name}: not valid UTF-8") from None
    except csv.Error as e:
        raise ValueError(f"{name}: not valid CSV, {e}") from None
    except OSError as e:
        raise ValueError(f"{name}: could not read the file ({e.strerror})") from None
    return rows


def _load(
    folder: Path,
    table: str,
    cmap: ColumnMap,
    budget: _Budget,
    build: Callable[..., Any],
) -> tuple[Any, ...] | None:
    path = folder / cmap.files.get(table, f"{table}.csv")
    if path.parent != folder:
        raise ValueError(f"{table}: file name must not contain a folder")
    if not path.is_file():
        return None
    return tuple(build(*row) for row in _read_rows(path, table, cmap, budget))


def read_folder(path: Path, column_map: ColumnMap | None = None) -> Ledger:
    """Read the four tables. A table with no file is left as None."""
    if not path.is_dir():
        raise ValueError(f"folder not found: {path}")
    cmap = column_map or ColumnMap()
    budget = _Budget()
    ledger = Ledger(
        journal_lines=_load(path, "journal_lines", cmap, budget, JournalLine),
        invoices=_load(path, "ap_invoices", cmap, budget, Invoice),
        payments=_load(path, "ap_payments", cmap, budget, Payment),
        vendors=_load(path, "vendors", cmap, budget, Vendor),
    )
    if all(t is None for t in (ledger.journal_lines, ledger.invoices, ledger.payments)):
        raise ValueError(f"no table files found in {path}")
    return ledger
