import random
from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from helpers import invoice, ledger, line
from ledgercheck.models import Flag, Settings
from ledgercheck.rules import (
    RULES,
    missing_ranges,
    money,
    run_rules,
    skip_reasons,
)

S = Settings()


def flags_for(rule: str, **tables: list) -> list[Flag]:  # type: ignore[type-arg]
    return [f for f in run_rules(ledger(**tables), S) if f.rule == rule]


def units(rule: str, **tables: list) -> set[str]:  # type: ignore[type-arg]
    return {f.unit_id for f in flags_for(rule, **tables)}


def test_weekend_reason_and_unit() -> None:
    sat = line(je="JE-1", day=date(2025, 3, 8))
    mon = line(je="JE-2", day=date(2025, 3, 10))
    found = flags_for("weekend_posting", lines=[sat, mon])
    assert [f.unit_id for f in found] == ["JE-1"]
    assert found[0].reason == "Posted on Saturday 2025-03-08"
    assert found[0].table == "journal_lines"


def test_multi_line_entry_is_one_flag() -> None:
    day = date(2025, 3, 9)
    lines = [
        line(je="JE-1", day=day, line_id="L2", debit=0, credit=500),
        line(je="JE-1", day=day, line_id="L1", debit=500),
    ]
    found = flags_for("weekend_posting", lines=lines)
    assert len(found) == 1
    assert found[0].row_ids == ("L1", "L2")


def test_holiday_observed_on_friday_and_monday() -> None:
    friday = date(2020, 7, 3)
    monday = date(2021, 7, 5)
    saturday = date(2020, 7, 4)
    lines = [
        line(je="JE-1", day=friday),
        line(je="JE-2", day=monday),
        line(je="JE-3", day=saturday),
        line(je="JE-4", day=date(2020, 7, 6)),
    ]
    assert units("holiday_posting", lines=lines) == {"JE-1", "JE-2"}


def test_holiday_reason_names_the_holiday() -> None:
    found = flags_for("holiday_posting", lines=[line(day=date(2025, 12, 25))])
    assert found[0].reason == "Posted on 2025-12-25, Christmas Day"


def test_user_holiday_list_and_switch() -> None:
    day = date(2025, 3, 5)
    lines = [line(day=day)]
    custom = Settings(extra_holidays=(day,), us_holidays=False)
    found = run_rules(ledger(lines=lines), custom)
    assert [f.rule for f in found] == ["holiday_posting"]


def test_round_amount_uses_entry_debit_total() -> None:
    lines = [
        line(je="JE-1", debit=60_000, line_id="a"),
        line(je="JE-1", debit=40_000, line_id="b"),
        line(je="JE-2", debit=100_000, credit=0, line_id="c"),
        line(je="JE-3", debit=100_001, line_id="d"),
        line(je="JE-4", debit=0, credit=100_000, line_id="e"),
    ]
    assert units("round_amount", lines=lines) == {"JE-1", "JE-2"}


def test_round_amount_reason() -> None:
    found = flags_for("round_amount", lines=[line(debit=300_000)])
    assert found[0].reason == "Debit total 3,000.00 is a whole multiple of 1,000.00"


def test_no_approver() -> None:
    lines = [line(je="JE-1", approver=""), line(je="JE-2", approver="A")]
    assert units("no_approver", lines=lines) == {"JE-1"}


def test_period_mismatch() -> None:
    lines = [
        line(je="JE-1", day=date(2025, 3, 5), period="2025-02"),
        line(je="JE-2", day=date(2025, 3, 5), period="2025-03"),
    ]
    found = flags_for("period_mismatch", lines=lines)
    assert [f.unit_id for f in found] == ["JE-1"]
    assert found[0].reason == "Period 2025-02 differs from posting month 2025-03"


def rare_ledger() -> list:  # type: ignore[type-arg]
    lines = [line(je=f"JE-{i:03d}", user="common") for i in range(40)]
    lines.append(line(je="JE-900", user="seldom"))
    return lines


def test_rare_poster_only_says_the_user_posts_rarely() -> None:
    found = flags_for("rare_poster", lines=rare_ledger())
    assert [f.unit_id for f in found] == ["JE-900"]
    assert found[0].reason == "User id seldom posts rarely"


def test_rare_poster_needs_enough_entries() -> None:
    lines = [line(je=f"JE-{i}", user="common") for i in range(5)]
    lines.append(line(je="JE-9", user="seldom"))
    assert units("rare_poster", lines=lines) == set()


def test_rare_poster_is_per_source_type() -> None:
    lines = [line(je=f"JE-{i:03d}", user="u1", source="A") for i in range(30)]
    lines += [line(je=f"JE-{i:03d}", user="u2", source="B") for i in range(30, 60)]
    assert units("rare_poster", lines=lines) == set()


def test_rare_poster_skips_listed_users() -> None:
    settings = Settings(rare_skip_users=("seldom",))
    found = run_rules(ledger(lines=rare_ledger()), settings)
    assert [f for f in found if f.rule == "rare_poster"] == []


def test_rare_poster_skip_list_is_exact_and_leaves_others() -> None:
    lines = rare_ledger() + [line(je="JE-901", user="other")]
    settings = Settings(rare_skip_users=("seldom", "sel"))
    found = run_rules(ledger(lines=lines), settings)
    assert [f.unit_id for f in found if f.rule == "rare_poster"] == ["JE-901"]


@given(st.lists(st.sampled_from(["a", "b", "c", "d"]), max_size=4))
def test_skip_list_only_removes_rare_poster_flags(skip: list[str]) -> None:
    lines = [line(je=f"JE-{i:03d}", user="common") for i in range(40)]
    lines += [line(je=f"JE-9{i}", user=u) for i, u in enumerate("abcd")]
    base = run_rules(ledger(lines=lines), S)
    cut = run_rules(ledger(lines=lines), Settings(rare_skip_users=tuple(skip)))
    assert set(cut) <= set(base)
    left = {f for f in base if f not in cut}
    assert all(f.rule == "rare_poster" for f in left)
    users = {"JE-9" + str(i): u for i, u in enumerate("abcd")}
    assert {f.unit_id for f in left} == {k for k, u in users.items() if u in skip}


def test_skipped_users_still_count_in_the_total() -> None:
    lines = [line(je=f"JE-{i:03d}", user="common") for i in range(19)]
    lines += [line(je=f"JE-8{i}", user="job") for i in range(10)]
    lines += [line(je="JE-900", user="seldom")]
    wide = Settings(rare_share=0.05, rare_skip_users=("job",))
    found = run_rules(ledger(lines=lines), wide)
    assert [f.unit_id for f in found if f.rule == "rare_poster"] == ["JE-900"]
    dropped = [x for x in lines if x.created_by != "job"]
    alone = run_rules(ledger(lines=dropped), Settings(rare_share=0.05))
    assert [f for f in alone if f.rule == "rare_poster"] == []


def test_skip_list_is_exact_match_only() -> None:
    lines = [line(je=f"JE-{i:03d}", user="common") for i in range(40)]
    others = ["seldom", "seldom2", "SELDOM", "sel"]
    lines += [line(je=f"JE-9{i}", user=u) for i, u in enumerate(others)]
    found = run_rules(ledger(lines=lines), Settings(rare_skip_users=("seldom",)))
    users = {f.reason for f in found if f.rule == "rare_poster"}
    assert users == {f"User id {u} posts rarely" for u in others[1:]}


def invoices_for_split(amounts: list[int], gap_days: int = 1) -> list:  # type: ignore[type-arg]
    start = date(2025, 3, 3)
    return [
        invoice(f"I{i}", "V1", f"N{i}", start + timedelta(days=i * gap_days), a)
        for i, a in enumerate(amounts)
    ]


def test_split_group_unit_and_rows() -> None:
    found = flags_for("split_under_limit", invoices=invoices_for_split([400_000] * 2))
    assert len(found) == 1
    assert found[0].unit_id == "I0"
    assert found[0].row_ids == ("I0", "I1")
    assert found[0].table == "ap_invoices"
    assert "total 8,000.00" in found[0].reason


def test_split_ignores_far_apart_and_out_of_band() -> None:
    assert (
        units("split_under_limit", invoices=invoices_for_split([400_000] * 2, 30))
        == set()
    )
    assert (
        units("split_under_limit", invoices=invoices_for_split([100_000] * 2)) == set()
    )
    assert units("split_under_limit", invoices=invoices_for_split([400_000])) == set()
    assert (
        units("split_under_limit", invoices=invoices_for_split([500_000] * 2)) == set()
    )


def test_split_needs_one_vendor() -> None:
    a = invoice("I1", "V1", "N1", date(2025, 3, 3), 400_000)
    b = invoice("I2", "V2", "N2", date(2025, 3, 4), 400_000)
    assert units("split_under_limit", invoices=[a, b]) == set()


def test_split_two_separate_groups() -> None:
    start = date(2025, 3, 3)
    items = [
        invoice("I1", "V1", "N", start, 400_000),
        invoice("I2", "V1", "N", start + timedelta(days=1), 400_000),
        invoice("I3", "V1", "N", start + timedelta(days=60), 450_000),
        invoice("I4", "V1", "N", start + timedelta(days=61), 450_000),
    ]
    assert units("split_under_limit", invoices=items) == {"I1", "I3"}


def test_entry_number_gap() -> None:
    lines = [line(je=f"JE-{n:06d}") for n in (1, 2, 5, 6, 9)]
    found = flags_for("entry_number_gap", lines=lines)
    assert [f.unit_id for f in found] == ["JE-000003", "JE-000007"]
    assert found[0].reason == "Entry numbers JE-000003 to JE-000004 are missing"
    assert found[1].reason == "Entry numbers JE-000007 to JE-000008 are missing"
    assert flags_for("entry_number_gap", lines=lines[:2]) == []


def test_single_missing_number_reason() -> None:
    lines = [line(je=f"JE-{n}") for n in (1, 3)]
    found = flags_for("entry_number_gap", lines=lines)
    assert found[0].reason == "Entry number JE-2 is missing from the sequence"


def test_ids_without_numbers_are_ignored_by_gap_rule() -> None:
    lines = [line(je="alpha"), line(je="beta")]
    assert flags_for("entry_number_gap", lines=lines) == []


def test_skip_reasons_for_missing_tables() -> None:
    reasons = skip_reasons(ledger(lines=[line()]))
    assert "weekend_posting" not in reasons
    assert reasons["split_under_limit"].startswith("needs ap_invoices")
    assert "duplicate_fuzzy" in reasons
    assert skip_reasons(ledger([], [], [], [])) == {}


def test_run_rules_skips_absent_tables() -> None:
    assert run_rules(ledger(), S) == []


def test_money_format() -> None:
    assert money(123456) == "1,234.56"
    assert money(-5) == "-0.05"


def test_output_is_sorted_by_rule_then_unit() -> None:
    lines = [
        line(je="JE-2", day=date(2025, 3, 8)),
        line(je="JE-1", day=date(2025, 3, 9)),
    ]
    found = run_rules(ledger(lines=lines), S)
    keys = [(RULES.index(f.rule), f.unit_id) for f in found]
    assert keys == sorted(keys)


days = st.dates(min_value=date(2024, 1, 1), max_value=date(2026, 12, 31))


@st.composite
def entries(draw: st.DrawFn) -> list:  # type: ignore[type-arg]
    count = draw(st.integers(1, 25))
    out = []
    for i in range(count):
        out.append(
            line(
                je=f"JE-{i + 1:04d}",
                day=draw(days),
                debit=draw(st.integers(0, 3_000_000)),
                period=draw(st.sampled_from(["2024-05", "2025-03", "2026-01"])),
                source=draw(st.sampled_from(["MANUAL", "AP"])),
                user=draw(st.sampled_from(["u1", "u2", "u3"])),
                approver=draw(st.sampled_from(["", "a1"])),
                line_id=f"L{i:04d}",
            )
        )
    return out


def flag_keys(flags: list[Flag], rename: dict[str, str] | None = None) -> set[tuple]:  # type: ignore[type-arg]
    rename = rename or {}
    return {
        (f.rule, f.table, f.unit_id, f.row_ids, _rename_text(f.reason, rename))
        for f in flags
    }


def _rename_text(text: str, rename: dict[str, str]) -> str:
    for old, new in rename.items():
        text = text.replace(old, new)
    return text


@given(entries(), st.integers(0, 1000))
def test_shuffling_changes_no_flag(items: list, seed: int) -> None:  # type: ignore[type-arg]
    shuffled = list(items)
    random.Random(seed).shuffle(shuffled)
    loose = Settings(rare_min_entries=1, rare_share=0.5)
    a = run_rules(ledger(lines=items), loose)
    b = run_rules(ledger(lines=shuffled), loose)
    assert a == b


@given(entries())
def test_renaming_users_changes_no_flag(items: list) -> None:  # type: ignore[type-arg]
    from dataclasses import replace

    rename = {"u1": "x-9", "u2": "x-8", "u3": "x-7", "a1": "b-5"}
    renamed = [
        replace(
            x,
            created_by=rename[x.created_by],
            approved_by=rename.get(x.approved_by, x.approved_by),
        )
        for x in items
    ]
    loose = Settings(rare_min_entries=1, rare_share=0.5)
    a = flag_keys(run_rules(ledger(lines=items), loose), rename)
    b = flag_keys(run_rules(ledger(lines=renamed), loose))
    assert a == b


@given(st.lists(days, min_size=1, max_size=20))
def test_weekend_flags_exactly_weekday_5_and_6(dates: list[date]) -> None:
    items = [line(je=f"JE-{i}", day=d) for i, d in enumerate(dates)]
    flagged = units("weekend_posting", lines=items)
    expected = {f"JE-{i}" for i, d in enumerate(dates) if d.weekday() >= 5}
    assert flagged == expected


@given(st.sets(st.integers(2, 200), max_size=60))
def test_gap_finds_exactly_removed_numbers(removed: set[int]) -> None:
    top = 201
    kept = [n for n in range(1, top + 1) if n not in removed]
    found = set()
    for first, last, _, _ in missing_ranges(kept):
        found.update(range(first, last + 1))
    assert found == removed
