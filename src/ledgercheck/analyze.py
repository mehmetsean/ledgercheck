"""Run every rule on one ledger and collect the results."""

from collections import Counter
from dataclasses import dataclass

from .benford import BenfordResult, benford_first_digit
from .duplicates import find_duplicates
from .models import Flag, Ledger, Settings
from .rules import (
    RULES,
    group_entries,
    run_rules,
    shared_number_count,
    skip_reasons,
    unnumbered_count,
)


@dataclass(frozen=True)
class AnalysisResult:
    flags: list[Flag]
    counts: dict[str, int]
    skips: dict[str, str]
    benford: list[BenfordResult]
    table_rows: dict[str, int | None]
    dup_k: int
    dup_compares: int
    unnumbered_ids: int = 0
    shared_numbers: int = 0


def _benford(ledger: Ledger) -> list[BenfordResult]:
    out = []
    if ledger.invoices is not None:
        values = [x.amount_cents for x in ledger.invoices]
        out.append(benford_first_digit(values, "ap_invoices.amount_cents"))
    if ledger.payments is not None:
        values = [x.amount_cents for x in ledger.payments]
        out.append(benford_first_digit(values, "ap_payments.amount_cents"))
    if ledger.journal_lines is not None:
        values = [x.debit_cents for x in ledger.journal_lines]
        out.append(benford_first_digit(values, "journal_lines.debit_cents"))
    return out


def analyze(ledger: Ledger, settings: Settings) -> AnalysisResult:
    flags = run_rules(ledger, settings)
    dup = find_duplicates(ledger, settings.duplicates)
    flags = sorted(flags + dup.flags, key=lambda f: (RULES.index(f.rule), f.unit_id))
    counted = Counter(f.rule for f in flags)
    counts = {rule: counted[rule] for rule in RULES if rule != "benford_first_digit"}
    tables = {
        "journal_lines": ledger.journal_lines,
        "ap_invoices": ledger.invoices,
        "ap_payments": ledger.payments,
        "vendors": ledger.vendors,
    }
    unnumbered = shared = 0
    if ledger.journal_lines is not None:
        entries = group_entries(ledger.journal_lines)
        unnumbered = unnumbered_count(entries)
        shared = shared_number_count(entries)
    rows = {name: None if t is None else len(t) for name, t in tables.items()}
    return AnalysisResult(
        flags=flags,
        counts=counts,
        skips=skip_reasons(ledger),
        benford=_benford(ledger),
        table_rows=rows,
        dup_k=dup.k,
        dup_compares=dup.compares,
        unnumbered_ids=unnumbered,
        shared_numbers=shared,
    )
