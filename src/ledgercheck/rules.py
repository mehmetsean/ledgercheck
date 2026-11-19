"""Journal entry and invoice rules. Each flag is an item to check."""

import re
from collections import Counter, defaultdict
from datetime import date
from fractions import Fraction

from .dates import WEEKDAYS, holiday_map
from .models import Flag, Invoice, JournalLine, Ledger, Settings

RULES = (
    "weekend_posting",
    "holiday_posting",
    "round_amount",
    "rare_poster",
    "no_approver",
    "period_mismatch",
    "split_under_limit",
    "duplicate_exact",
    "duplicate_fuzzy",
    "entry_number_gap",
    "benford_first_digit",
)

NEEDS = {
    "weekend_posting": ("journal_lines",),
    "holiday_posting": ("journal_lines",),
    "round_amount": ("journal_lines",),
    "rare_poster": ("journal_lines",),
    "no_approver": ("journal_lines",),
    "period_mismatch": ("journal_lines",),
    "entry_number_gap": ("journal_lines",),
    "split_under_limit": ("ap_invoices",),
    "duplicate_exact": ("ap_payments",),
    "duplicate_fuzzy": ("ap_payments", "ap_invoices", "vendors"),
}

NUMBERED = re.compile(r"(.*?)([0-9]+)")
DIGITS = re.compile(r"([0-9]+)")


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, part = divmod(abs(cents), 100)
    return f"{sign}{whole:,}.{part:02d}"


def present_tables(ledger: Ledger) -> set[str]:
    named = {
        "journal_lines": ledger.journal_lines,
        "ap_invoices": ledger.invoices,
        "ap_payments": ledger.payments,
        "vendors": ledger.vendors,
    }
    return {name for name, rows in named.items() if rows is not None}


def skip_reasons(ledger: Ledger) -> dict[str, str]:
    """Rules that cannot run because a table is missing."""
    have = present_tables(ledger)
    out: dict[str, str] = {}
    for rule, tables in NEEDS.items():
        missing = [t for t in tables if t not in have]
        if missing:
            out[rule] = f"needs {', '.join(missing)}, which is not in the input"
    return out


def natural_key(text: str) -> tuple[tuple[int, int, str], ...]:
    """Sort key where digit runs compare as integers, so L2 comes before L10."""
    parts = DIGITS.split(text)
    return tuple((0, int(p), "") if i % 2 else (1, 0, p) for i, p in enumerate(parts))


def group_entries(lines: tuple[JournalLine, ...]) -> dict[str, list[JournalLine]]:
    """Lines by je_id. Each list is in natural line_id order.

    The first line of a group gives the entry's date, period, source type,
    creator and approver.
    """
    entries: dict[str, list[JournalLine]] = defaultdict(list)
    for item in lines:
        entries[item.je_id].append(item)
    for group in entries.values():
        group.sort(key=lambda x: (natural_key(x.line_id), x.line_id))
    return entries


def _flag(rule: str, je_id: str, group: list[JournalLine], reason: str) -> Flag:
    ids = tuple(x.line_id for x in group)
    return Flag(rule, "journal_lines", je_id, ids, reason)


def _weekend(je_id: str, group: list[JournalLine]) -> Flag | None:
    d = group[0].posting_date
    if d.weekday() < 5:
        return None
    reason = f"Posted on {WEEKDAYS[d.weekday()]} {d.isoformat()}"
    return _flag("weekend_posting", je_id, group, reason)


def _holiday(
    je_id: str, group: list[JournalLine], calendar: dict[date, str]
) -> Flag | None:
    d = group[0].posting_date
    name = calendar.get(d)
    if name is None:
        return None
    reason = f"Posted on {d.isoformat()}, {name}"
    return _flag("holiday_posting", je_id, group, reason)


def _round(je_id: str, group: list[JournalLine], settings: Settings) -> Flag | None:
    total = sum(x.debit_cents for x in group)
    step = settings.round_step_cents
    if total <= 0 or total % step != 0:
        return None
    reason = f"Debit total {money(total)} is a whole multiple of {money(step)}"
    return _flag("round_amount", je_id, group, reason)


def _no_approver(je_id: str, group: list[JournalLine]) -> Flag | None:
    if group[0].approved_by != "":
        return None
    return _flag("no_approver", je_id, group, "No approver is recorded")


def _period(je_id: str, group: list[JournalLine]) -> Flag | None:
    first = group[0]
    month = first.posting_date.strftime("%Y-%m")
    if first.period == month:
        return None
    reason = f"Period {first.period} differs from posting month {month}"
    return _flag("period_mismatch", je_id, group, reason)


def _rare_posters(
    entries: dict[str, list[JournalLine]], settings: Settings
) -> list[Flag]:
    by_type: Counter[str] = Counter()
    by_user: Counter[tuple[str, str]] = Counter()
    for group in entries.values():
        first = group[0]
        by_type[first.source_type] += 1
        by_user[(first.source_type, first.created_by)] += 1
    out: list[Flag] = []
    for je_id, group in entries.items():
        source, user = group[0].source_type, group[0].created_by
        total = by_type[source]
        count = by_user[(source, user)]
        if user == "" or user in settings.rare_skip_users:
            continue
        if total < settings.rare_min_entries:
            continue
        if count / total >= settings.rare_share:
            continue
        reason = f"User id {user} posts rarely"
        out.append(_flag("rare_poster", je_id, group, reason))
    return out


def journal_flags(lines: tuple[JournalLine, ...], settings: Settings) -> list[Flag]:
    entries = group_entries(lines)
    years = {x.posting_date.year for x in lines}
    calendar = holiday_map(years, settings.extra_holidays, settings.us_holidays)
    out: list[Flag] = []
    for je_id, group in entries.items():
        found = [
            _weekend(je_id, group),
            _holiday(je_id, group, calendar),
            _round(je_id, group, settings),
            _no_approver(je_id, group),
            _period(je_id, group),
        ]
        out.extend(f for f in found if f is not None)
    out.extend(_rare_posters(entries, settings))
    out.extend(gap_flags(entries))
    return out


def missing_ranges(numbers: list[int]) -> list[tuple[int, int, int, int]]:
    """Gaps in a number list as (first missing, last missing, before, after)."""
    ordered = sorted(set(numbers))
    out = []
    for before, after in zip(ordered, ordered[1:], strict=False):
        if after - before > 1:
            out.append((before + 1, after - 1, before, after))
    return out


def unnumbered_count(entries: dict[str, list[JournalLine]]) -> int:
    """Entry ids with no trailing digits. entry_number_gap skips them."""
    return sum(1 for je_id in entries if NUMBERED.fullmatch(je_id) is None)


def shared_number_count(entries: dict[str, list[JournalLine]]) -> int:
    """Ids that share a prefix and a number with another id, such as JE-1 and JE-001."""
    seen: set[tuple[str, int]] = set()
    shared = 0
    for je_id in entries:
        match = NUMBERED.fullmatch(je_id)
        if match is None:
            continue
        key = (match.group(1), int(match.group(2)))
        if key in seen:
            shared += 1
        seen.add(key)
    return shared


def gap_flags(entries: dict[str, list[JournalLine]]) -> list[Flag]:
    """Missing numbers in the je_id sequence.

    An id is a prefix plus a trailing run of digits, read as an integer of any
    width. Ids with the same prefix form one sequence, so JE1 to JE9 and JE11
    flag JE10, and JE-2025-0001 has the prefix JE-2025-. Ids with no trailing
    digits are skipped. Zero padding follows the id before the gap.
    """
    groups: dict[str, dict[int, str]] = defaultdict(dict)
    for je_id in entries:
        match = NUMBERED.fullmatch(je_id)
        if match is not None:
            groups[match.group(1)][int(match.group(2))] = je_id
    out: list[Flag] = []
    for prefix, by_number in groups.items():
        for first, last, before, after in missing_ranges(list(by_number)):
            digits = NUMBERED.fullmatch(by_number[before])
            pad = len(digits.group(2)) if digits and digits.group(2)[0] == "0" else 0
            name = f"{prefix}{first:0{pad}d}"
            ids = (by_number[before], by_number[after])
            if first == last:
                reason = f"Entry number {name} is missing from the sequence"
            else:
                end = f"{prefix}{last:0{pad}d}"
                reason = f"Entry numbers {name} to {end} are missing"
            out.append(Flag("entry_number_gap", "journal_lines", name, ids, reason))
    return out


def _in_band(inv: Invoice, settings: Settings) -> bool:
    limit = settings.approval_limit_cents
    band = Fraction(settings.split_band).limit_denominator(1_000_000)
    below = limit - inv.amount_cents
    return 0 < below and below * band.denominator <= limit * band.numerator


def _split_groups(items: list[Invoice], settings: Settings) -> list[list[Invoice]]:
    items.sort(key=lambda x: (x.invoice_date, x.invoice_id))
    groups = []
    i = 0
    while i < len(items):
        j = i + 1
        while (
            j < len(items)
            and (items[j].invoice_date - items[i].invoice_date).days
            <= settings.split_window_days
        ):
            j += 1
        chosen = items[i:j]
        total = sum(x.amount_cents for x in chosen)
        if len(chosen) >= 2 and total >= settings.approval_limit_cents:
            groups.append(chosen)
            i = j
        else:
            i += 1
    return groups


def split_flags(invoices: tuple[Invoice, ...], settings: Settings) -> list[Flag]:
    """Invoices of one vendor, each just under the limit, close together.

    Grouping is greedy and disjoint. A group starts at the earliest unused
    invoice and takes every invoice within split_window_days of that start.
    A single day-0, day-6, day-12 run with a 7 day window groups only the
    first two, and the day-12 invoice starts its own check.
    """
    by_vendor: dict[str, list[Invoice]] = defaultdict(list)
    for inv in invoices:
        if _in_band(inv, settings):
            by_vendor[inv.vendor_id].append(inv)
    out: list[Flag] = []
    for vendor, items in by_vendor.items():
        for group in _split_groups(items, settings):
            total = sum(x.amount_cents for x in group)
            ids = tuple(x.invoice_id for x in group)
            reason = (
                f"{len(group)} invoices from vendor {vendor} within "
                f"{settings.split_window_days} days, each just under "
                f"{money(settings.approval_limit_cents)}, total {money(total)}"
            )
            out.append(Flag("split_under_limit", "ap_invoices", ids[0], ids, reason))
    return out


def run_rules(ledger: Ledger, settings: Settings) -> list[Flag]:
    """Journal rules and split_under_limit. Duplicates are in duplicates.py."""
    out: list[Flag] = []
    if ledger.journal_lines is not None:
        out.extend(journal_flags(ledger.journal_lines, settings))
    if ledger.invoices is not None:
        out.extend(split_flags(ledger.invoices, settings))
    return sorted(out, key=lambda f: (RULES.index(f.rule), f.unit_id))
