"""Duplicate payment checks: exact keys first, then blocked fuzzy matching."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from .models import DuplicateSettings, Flag, Ledger

NAME_CAP = 100
SUFFIXES = frozenset(
    {
        "inc",
        "incorporated",
        "llc",
        "ltd",
        "limited",
        "co",
        "corp",
        "corporation",
        "company",
        "lp",
        "llp",
        "plc",
    }
)


@dataclass(frozen=True)
class DuplicatePair:
    kind: str
    earlier_id: str
    later_id: str
    name_similarity: float
    invoice_similarity: float
    days_apart: int
    same_amount: bool
    reason: str


@dataclass(frozen=True)
class DuplicateResult:
    """k is the most same-amount payments inside one date window."""

    pairs: list[DuplicatePair]
    flags: list[Flag]
    k: int
    compares: int


@dataclass(frozen=True)
class _Rec:
    payment_id: str
    invoice_id: str
    day: date
    amount: int
    name: str
    number: str
    exact_key: tuple[str, str, int] | None


def normalize_name(name: str) -> str:
    """Lowercase, no punctuation, trailing legal suffixes removed, capped."""
    kept = "".join(c for c in name.lower() if c.isalnum() or c.isspace())
    words = kept.split()
    while words and words[-1] in SUFFIXES:
        words.pop()
    return " ".join(words)[:NAME_CAP]


def normalize_number(number: str) -> str:
    return "".join(c for c in number.lower() if c.isalnum())[:NAME_CAP]


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        new = [i]
        for j, cb in enumerate(b, start=1):
            new.append(min(row[j] + 1, new[j - 1] + 1, row[j - 1] + (ca != cb)))
        row = new
    return row[-1]


def ratio(a: str, b: str) -> float:
    longest = max(len(a), len(b))
    if longest == 0:
        return 1.0
    return 1 - levenshtein(a, b) / longest


def name_similarity(a: str, b: str) -> float:
    """Levenshtein ratio of the normalized names, from 0 to 1."""
    return ratio(normalize_name(a), normalize_name(b))


def number_similarity(a: str, b: str) -> float:
    x, y = normalize_number(a), normalize_number(b)
    if x == "" or y == "":
        return 0.0
    return ratio(x, y)


def _records(ledger: Ledger) -> list[_Rec]:
    payments = ledger.payments or ()
    numbers = {i.invoice_id: i.invoice_number for i in ledger.invoices or ()}
    names = {v.vendor_id: normalize_name(v.vendor_name) for v in ledger.vendors or ()}
    out = []
    for p in payments:
        number = numbers.get(p.invoice_id, "")
        key = (p.vendor_id, number, p.amount_cents) if number else None
        name = names.get(p.vendor_id, "")
        out.append(
            _Rec(
                p.payment_id,
                p.invoice_id,
                p.payment_date,
                p.amount_cents,
                name,
                number,
                key,
            )  # fmt: skip
        )
    return sorted(out, key=lambda r: (r.day, r.payment_id))


def _exact_pairs(records: list[_Rec]) -> list[DuplicatePair]:
    by_invoice: dict[str, list[_Rec]] = defaultdict(list)
    by_key: dict[tuple[str, str, int], list[_Rec]] = defaultdict(list)
    for r in records:
        if r.invoice_id:
            by_invoice[r.invoice_id].append(r)
        if r.exact_key:
            by_key[r.exact_key].append(r)
    found: dict[str, DuplicatePair] = {}
    for invoice_id, group in sorted(by_invoice.items()):
        for later in group[1:]:
            reason = (
                f"Invoice {invoice_id} was paid twice, first by {group[0].payment_id}"
            )
            found.setdefault(later.payment_id, _exact(group[0], later, reason))
    for key, group in sorted(by_key.items()):
        for later in group[1:]:
            reason = (
                f"Same vendor {key[0]}, invoice number {key[1]} and amount "
                f"were paid before by {group[0].payment_id}"
            )
            found.setdefault(later.payment_id, _exact(group[0], later, reason))
    return sorted(found.values(), key=lambda p: p.later_id)


def _exact(first: _Rec, later: _Rec, reason: str) -> DuplicatePair:
    days = (later.day - first.day).days
    same = first.amount == later.amount
    return DuplicatePair("exact", first.payment_id, later.payment_id,
                         1.0, 1.0, days, same, reason)  # fmt: skip


def _is_exact(a: _Rec, b: _Rec) -> bool:
    if a.invoice_id and a.invoice_id == b.invoice_id:
        return True
    return a.exact_key is not None and a.exact_key == b.exact_key


def _fuzzy_pair(a: _Rec, b: _Rec, s: DuplicateSettings) -> DuplicatePair | None:
    """a is the earlier record. None when the pair does not match."""
    if a.name == "" or b.name == "" or _is_exact(a, b):
        return None
    name = ratio(a.name, b.name)
    number = number_similarity(a.number, b.number)
    if name < s.name_threshold or number < s.invoice_threshold:
        return None
    days = (b.day - a.day).days
    same = ", same amount" if a.amount == b.amount else ""
    reason = (
        f"Paid {days} days after {a.payment_id}{same}, "
        f"vendor name similarity {name:.2f}, invoice number similarity {number:.2f}"
    )
    return DuplicatePair("fuzzy", a.payment_id, b.payment_id, name, number,
                         days, a.amount == b.amount, reason)  # fmt: skip


def _fuzzy_blocked(
    records: list[_Rec], s: DuplicateSettings
) -> tuple[list[DuplicatePair], int, int]:
    ordered = sorted(records, key=lambda r: (r.amount, r.day, r.payment_id))
    pairs: list[DuplicatePair] = []
    compares = 0
    k = 0
    for i, a in enumerate(ordered):
        j = i + 1
        while (
            j < len(ordered)
            and ordered[j].amount == a.amount
            and (ordered[j].day - a.day).days <= s.window_days
        ):
            compares += 1
            if compares > s.max_compares:
                raise ValueError(
                    f"duplicate_fuzzy stopped after {s.max_compares} pair compares. "
                    f"Many payments share one amount within {s.window_days} days. "
                    "Lower window_days or raise max_compares in the settings file"
                )
            pair = _fuzzy_pair(a, ordered[j], s)
            if pair:
                pairs.append(pair)
            j += 1
        k = max(k, j - i)
    return pairs, k, compares


def fuzzy_pairs_all(ledger: Ledger, settings: DuplicateSettings) -> list[DuplicatePair]:
    """Reference: compare every pair, ignoring amount and date. O(n^2)."""
    records = _records(ledger)
    out = []
    for i, a in enumerate(records):
        for b in records[i + 1 :]:
            pair = _fuzzy_pair(a, b, settings)
            if pair:
                out.append(pair)
    return out


def _flags(pairs: list[DuplicatePair]) -> list[Flag]:
    first: dict[tuple[str, str], DuplicatePair] = {}
    for p in sorted(pairs, key=lambda p: (p.later_id, p.earlier_id)):
        first.setdefault((p.kind, p.later_id), p)
    out = []
    for (kind, later), p in sorted(first.items()):
        rule = f"duplicate_{kind}"
        out.append(Flag(rule, "ap_payments", later, (later, p.earlier_id), p.reason))
    return out


def find_duplicates(ledger: Ledger, settings: DuplicateSettings) -> DuplicateResult:
    """Exact duplicates, then fuzzy ones that exact matching did not find."""
    if ledger.payments is None:
        return DuplicateResult([], [], 0, 0)
    records = _records(ledger)
    pairs = _exact_pairs(records)
    k = compares = 0
    if ledger.invoices is not None and ledger.vendors is not None:
        fuzzy, k, compares = _fuzzy_blocked(records, settings)
        pairs += fuzzy
    return DuplicateResult(pairs, _flags(pairs), k, compares)
