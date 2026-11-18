import csv
from datetime import date
from pathlib import Path

from ledgercheck.models import Invoice, JournalLine, Ledger, Payment, Vendor

JOURNAL_HEADER = [
    "line_id",
    "je_id",
    "line_no",
    "posting_date",
    "period",
    "account_id",
    "debit_cents",
    "credit_cents",
    "memo",
    "source_type",
    "source_id",
    "created_by",
    "approved_by",
]


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def journal_row(
    line: str = "L1",
    je: str = "JE-1",
    day: str = "2025-03-05",
    period: str = "2025-03",
    debit: str = "1234",
    credit: str = "0",
    source: str = "MANUAL",
    user: str = "U1",
    approver: str = "A1",
    memo: str = "text",
) -> list[str]:
    return [
        line, je, "1", day, period, "1000", debit, credit, memo, source, "",
        user, approver,
    ]  # fmt: skip


def line(
    je: str = "JE-1",
    day: date = date(2025, 3, 5),
    debit: int = 1234,
    credit: int = 0,
    period: str | None = None,
    source: str = "MANUAL",
    user: str = "U1",
    approver: str = "A1",
    line_id: str | None = None,
) -> JournalLine:
    return JournalLine(
        line_id=line_id or f"{je}-L",
        je_id=je,
        posting_date=day,
        period=period or day.strftime("%Y-%m"),
        account_id="1000",
        debit_cents=debit,
        credit_cents=credit,
        source_type=source,
        created_by=user,
        approved_by=approver,
    )


def invoice(inv: str, vendor: str, number: str, day: date, amount: int) -> Invoice:
    return Invoice(inv, vendor, number, day, amount)


def payment(pay: str, vendor: str, inv: str, day: date, amount: int) -> Payment:
    return Payment(pay, vendor, inv, day, amount)


def ledger(
    lines: list[JournalLine] | None = None,
    invoices: list[Invoice] | None = None,
    payments: list[Payment] | None = None,
    vendors: list[Vendor] | None = None,
) -> Ledger:
    def tup(items: list | None) -> tuple | None:  # type: ignore[type-arg]
        return None if items is None else tuple(items)

    return Ledger(tup(lines), tup(invoices), tup(payments), tup(vendors))
