"""Plain data classes shared by every module."""

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class JournalLine:
    line_id: str
    je_id: str
    posting_date: date
    period: str
    account_id: str
    debit_cents: int
    credit_cents: int
    source_type: str
    created_by: str
    approved_by: str


@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    vendor_id: str
    invoice_number: str
    invoice_date: date
    amount_cents: int


@dataclass(frozen=True)
class Payment:
    payment_id: str
    vendor_id: str
    invoice_id: str
    payment_date: date
    amount_cents: int


@dataclass(frozen=True)
class Vendor:
    vendor_id: str
    vendor_name: str


@dataclass(frozen=True)
class Ledger:
    """Tables are None when the input has no file for them."""

    journal_lines: tuple[JournalLine, ...] | None = None
    invoices: tuple[Invoice, ...] | None = None
    payments: tuple[Payment, ...] | None = None
    vendors: tuple[Vendor, ...] | None = None


@dataclass(frozen=True)
class Flag:
    """One item to check. unit_id is the scoring unit."""

    rule: str
    table: str
    unit_id: str
    row_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class DuplicateSettings:
    """Defaults for the duplicate payment checks.

    window_days: 14. Fuzzy pairs must be paid within this many days.
    name_threshold: 0.8. Least vendor name similarity, from 0 to 1.
    invoice_threshold: 0.8. Least invoice number similarity, from 0 to 1.
    max_cell_steps: 400,000,000. The fuzzy search stops with an error when its
        work passes this. Work is counted in Levenshtein cell steps: each
        compare costs 16 for call overhead, plus len(a) x len(b) when the
        edit distance really runs. The default allows about 19 seconds of
        edit distance work on the benchmark machine, about 21 million cell
        steps per second (benchmarks/bench.py, docs/benchmark.md). A user may
        raise max_cell_steps, up to 10**15, at the cost of a longer run.
    """

    window_days: int = 14
    name_threshold: float = 0.8
    invoice_threshold: float = 0.8
    max_cell_steps: int = 400_000_000


@dataclass(frozen=True)
class Settings:
    """Defaults for the journal and invoice rules.

    approval_limit_cents: 500,000 (5,000.00). Invoices at or over it need approval.
    round_step_cents: 100,000 (1,000.00). Entry debit totals that are a whole
        multiple of this are flagged.
    rare_share: 0.05. A user who posts under this share of a source type's
        entries is flagged.
    rare_min_entries: 20. Source types with fewer entries are not tested.
    rare_skip_users: none. User ids that rare_poster never flags, such as system
        or batch users. Their entries still count toward the source type total.
    close_window_days: 0. An entry posted on this day of the month or earlier
        with the previous month as its period is normal close activity and is
        not flagged by period_mismatch. 0 turns it off. Most 31.
    split_window_days: 7. Invoices of one vendor this close together can form a group.
    split_band: 0.3. "Just under the limit" means within this share below it.
    extra_holidays: none. Dates added to the US federal holiday calendar.
    us_holidays: True. Use the US federal holiday calendar.
    """

    approval_limit_cents: int = 500_000
    round_step_cents: int = 100_000
    rare_share: float = 0.05
    rare_min_entries: int = 20
    rare_skip_users: tuple[str, ...] = ()
    close_window_days: int = 0
    split_window_days: int = 7
    split_band: float = 0.3
    extra_holidays: tuple[date, ...] = ()
    us_holidays: bool = True
    duplicates: DuplicateSettings = field(default_factory=DuplicateSettings)


@dataclass(frozen=True)
class ColumnMap:
    """Where each table and column lives in a non-synthbiz export."""

    files: dict[str, str] = field(default_factory=dict)
    columns: dict[str, dict[str, str]] = field(default_factory=dict)
    date_format: str = "%Y-%m-%d"
    amounts: str = "cents"
