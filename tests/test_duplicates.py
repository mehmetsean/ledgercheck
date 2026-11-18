from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from helpers import invoice, ledger, payment
from ledgercheck.duplicates import (
    find_duplicates,
    fuzzy_pairs_all,
    levenshtein,
    name_similarity,
    normalize_name,
)
from ledgercheck.models import DuplicateSettings, Ledger, Vendor

D = DuplicateSettings()
DAY = date(2025, 3, 3)


def vendors() -> list[Vendor]:
    return [
        Vendor("V1", "Cedar Plastics Co"),
        Vendor("V2", "Cedar Plastics, Co."),
        Vendor("V3", "Harbor Logistics Corp"),
    ]


def rules(result):  # type: ignore[no-untyped-def]
    return sorted((f.rule, f.unit_id) for f in result.flags)


def test_same_invoice_paid_twice_flags_later_payment() -> None:
    inv = [invoice("I1", "V1", "N1", DAY, 5000)]
    pay = [
        payment("P2", "V1", "I1", DAY + timedelta(days=9), 5000),
        payment("P1", "V1", "I1", DAY, 5000),
    ]
    result = find_duplicates(ledger(invoices=inv, payments=pay, vendors=vendors()), D)
    assert rules(result) == [("duplicate_exact", "P2")]
    assert result.flags[0].row_ids == ("P2", "P1")
    assert result.flags[0].table == "ap_payments"
    assert "paid twice" in result.flags[0].reason


def test_same_vendor_number_and_amount_on_two_invoices() -> None:
    inv = [
        invoice("I1", "V1", "N1", DAY, 5000),
        invoice("I2", "V1", "N1", DAY, 5000),
    ]
    pay = [
        payment("P1", "V1", "I1", DAY, 5000),
        payment("P2", "V1", "I2", DAY + timedelta(days=3), 5000),
    ]
    result = find_duplicates(ledger(invoices=inv, payments=pay, vendors=vendors()), D)
    assert rules(result) == [("duplicate_exact", "P2")]


def test_different_amount_is_not_exact() -> None:
    inv = [invoice("I1", "V1", "N1", DAY, 5000), invoice("I2", "V1", "N1", DAY, 6000)]
    pay = [payment("P1", "V1", "I1", DAY, 5000), payment("P2", "V1", "I2", DAY, 6000)]
    result = find_duplicates(ledger(invoices=inv, payments=pay, vendors=vendors()), D)
    assert result.flags == []


def test_rekeyed_vendor_is_found_by_fuzzy_only() -> None:
    inv = [
        invoice("I1", "V1", "INV-100", DAY, 5000),
        invoice("I2", "V2", "INV-100", DAY, 5000),
    ]
    pay = [
        payment("P1", "V1", "I1", DAY, 5000),
        payment("P2", "V2", "I2", DAY + timedelta(days=5), 5000),
    ]
    result = find_duplicates(ledger(invoices=inv, payments=pay, vendors=vendors()), D)
    assert rules(result) == [("duplicate_fuzzy", "P2")]
    assert result.k == 2
    assert result.compares == 1
    assert "vendor name similarity 1.00" in result.flags[0].reason


def test_fuzzy_needs_same_amount_window_and_names() -> None:
    inv = [
        invoice("I1", "V1", "INV-100", DAY, 5000),
        invoice("I2", "V2", "INV-100", DAY, 5000),
        invoice("I3", "V3", "INV-100", DAY, 5000),
        invoice("I4", "V2", "INV-100", DAY, 5001),
    ]
    far = DAY + timedelta(days=40)
    pay = [
        payment("P1", "V1", "I1", DAY, 5000),
        payment("P2", "V2", "I2", far, 5000),
        payment("P3", "V3", "I3", DAY + timedelta(days=1), 5000),
        payment("P4", "V2", "I4", DAY + timedelta(days=1), 5001),
    ]
    result = find_duplicates(ledger(invoices=inv, payments=pay, vendors=vendors()), D)
    assert result.flags == []


def test_fuzzy_skipped_without_vendors_or_invoices() -> None:
    pay = [payment("P1", "V1", "I1", DAY, 5000), payment("P2", "V2", "I2", DAY, 5000)]
    result = find_duplicates(ledger(payments=pay), D)
    assert (result.k, result.compares) == (0, 0)
    assert find_duplicates(Ledger(), D).flags == []


def test_compare_budget_stops_with_clear_message() -> None:
    inv = [invoice(f"I{i}", "V1", "N", DAY, 5000) for i in range(6)]
    pay = [payment(f"P{i}", "V1", f"I{i}", DAY, 5000) for i in range(6)]
    tight = DuplicateSettings(max_compares=3)
    with pytest.raises(ValueError, match="stopped after 3 pair compares"):
        find_duplicates(ledger(invoices=inv, payments=pay, vendors=vendors()), tight)


def test_k_counts_largest_same_amount_window() -> None:
    inv = [invoice(f"I{i}", "V1", f"N{i}", DAY, 5000) for i in range(4)]
    pay = [payment(f"P{i}", "V1", f"I{i}", DAY, 5000) for i in range(4)]
    result = find_duplicates(ledger(invoices=inv, payments=pay, vendors=vendors()), D)
    assert result.k == 4
    assert result.compares == 6


def test_normalize_name() -> None:
    assert normalize_name("Cedar Plastics, Co.") == "cedar plastics"
    assert normalize_name("ACME Corp Inc") == "acme"
    assert normalize_name("Smith & Sons LLC") == "smith sons"
    assert normalize_name("x" * 300) == "x" * 100
    assert normalize_name("Company Store") == "company store"


def test_levenshtein_known_values() -> None:
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("", "abc") == 3
    assert levenshtein("same", "same") == 0


@given(st.text(max_size=30), st.text(max_size=30))
def test_name_similarity_symmetric_and_bounded(a: str, b: str) -> None:
    value = name_similarity(a, b)
    assert 0.0 <= value <= 1.0
    assert value == name_similarity(b, a)


@given(st.text(max_size=30), st.sampled_from(["", " Inc", ", LLC", " Co."]))
def test_equal_normalized_names_score_one(a: str, suffix: str) -> None:
    if normalize_name(a + suffix) == normalize_name(a):
        assert name_similarity(a, a + suffix) == 1.0


NAMES = ["Cedar Plastics Co", "Cedar Plastic Co.", "Cedar Plastics Inc", "Harbor Corp"]
NUMBERS = ["A100", "a-100", "A101", "B7"]


@st.composite
def payment_ledgers(draw: st.DrawFn) -> Ledger:
    count = draw(st.integers(2, 14))
    vend = [Vendor(f"V{i}", n) for i, n in enumerate(NAMES)]
    inv, pay = [], []
    for i in range(count):
        vendor = f"V{draw(st.integers(0, len(NAMES) - 1))}"
        amount = draw(st.sampled_from([5000, 5000, 7000]))
        day = DAY + timedelta(days=draw(st.integers(0, 30)))
        number = draw(st.sampled_from(NUMBERS))
        inv.append(invoice(f"I{i}", vendor, number, day, amount))
        pay.append(payment(f"P{i}", vendor, f"I{i}", day, amount))
    return ledger(invoices=inv, payments=pay, vendors=vend)


def pair_keys(pairs):  # type: ignore[no-untyped-def]
    return {(p.earlier_id, p.later_id) for p in pairs}


@settings(max_examples=150)
@given(payment_ledgers(), st.integers(0, 20))
def test_blocked_fuzzy_equals_all_pairs_inside_blocks(led: Ledger, window: int) -> None:
    cfg = DuplicateSettings(window_days=window)
    blocked = [p for p in find_duplicates(led, cfg).pairs if p.kind == "fuzzy"]
    inside = [
        p for p in fuzzy_pairs_all(led, cfg) if p.same_amount and p.days_apart <= window
    ]
    assert pair_keys(blocked) == pair_keys(inside)


@given(payment_ledgers())
def test_renaming_vendor_ids_changes_no_flag(led: Ledger) -> None:
    from dataclasses import replace

    def rename(v: str) -> str:
        return "Z" + v

    renamed = Ledger(
        invoices=tuple(
            replace(i, vendor_id=rename(i.vendor_id)) for i in led.invoices or ()
        ),
        payments=tuple(
            replace(p, vendor_id=rename(p.vendor_id)) for p in led.payments or ()
        ),
        vendors=tuple(
            replace(v, vendor_id=rename(v.vendor_id)) for v in led.vendors or ()
        ),
    )
    a = find_duplicates(led, D)
    b = find_duplicates(renamed, D)
    assert [(f.rule, f.unit_id, f.row_ids) for f in a.flags] == [
        (f.rule, f.unit_id, f.row_ids) for f in b.flags
    ]


@given(payment_ledgers(), st.integers(0, 1000))
def test_shuffling_rows_changes_no_flag(led: Ledger, seed: int) -> None:
    import random

    def shuffled(rows):  # type: ignore[no-untyped-def]
        items = list(rows)
        random.Random(seed).shuffle(items)
        return tuple(items)

    other = Ledger(
        None,
        shuffled(led.invoices or ()),
        shuffled(led.payments or ()),
        shuffled(led.vendors or ()),
    )
    a = find_duplicates(led, D)
    b = find_duplicates(other, D)
    assert a.flags == b.flags
