from datetime import date, timedelta

from helpers import invoice, ledger, line
from ledgercheck import report
from ledgercheck.analyze import analyze
from ledgercheck.models import Flag, Settings
from ledgercheck.rules import natural_key, run_rules

S = Settings()
START = date(2025, 3, 3)


def only(rule: str, settings: Settings = S, **tables: list) -> list[Flag]:  # type: ignore[type-arg]
    return [f for f in run_rules(ledger(**tables), settings) if f.rule == rule]


def pair(first: int, second: int, gap: int = 1, vendor: str = "V1") -> list:  # type: ignore[type-arg]
    return [
        invoice("I1", vendor, "N1", START, first),
        invoice("I2", vendor, "N2", START + timedelta(days=gap), second),
    ]


def test_split_band_low_edge() -> None:
    assert only("split_under_limit", invoices=pair(350_000, 350_000))
    assert not only("split_under_limit", invoices=pair(349_999, 350_000))
    assert not only("split_under_limit", invoices=pair(500_000, 499_999))


def test_split_total_exactly_at_limit_is_flagged() -> None:
    wide = Settings(split_band=0.5)
    assert only("split_under_limit", wide, invoices=pair(250_000, 250_000))


def test_split_window_edge() -> None:
    assert only("split_under_limit", invoices=pair(400_000, 400_000, gap=7))
    assert not only("split_under_limit", invoices=pair(400_000, 400_000, gap=8))


def test_split_with_a_huge_limit_uses_whole_numbers() -> None:
    big = Settings(approval_limit_cents=10**15)
    items = pair(10**15 - 1, 10**15 - 2)
    assert only("split_under_limit", big, invoices=items)


def test_split_grouping_is_greedy_and_disjoint() -> None:
    items = [
        invoice("I0", "V1", "N", START, 400_000),
        invoice("I1", "V1", "N", START + timedelta(days=6), 400_000),
        invoice("I2", "V1", "N", START + timedelta(days=12), 400_000),
    ]
    found = only("split_under_limit", invoices=items)
    assert [f.row_ids for f in found] == [("I0", "I1")]


def people(total: int, rare: int) -> list:  # type: ignore[type-arg]
    lines = [line(je=f"JE-{i:03d}", user="common") for i in range(total - rare)]
    lines += [line(je=f"JE-9{i:02d}", user="seldom") for i in range(rare)]
    return lines


def test_rare_share_edge_is_not_flagged() -> None:
    cfg = Settings(rare_share=0.05)
    assert not only("rare_poster", cfg, lines=people(40, 2))
    assert len(only("rare_poster", cfg, lines=people(40, 1))) == 1


def test_rare_min_entries_edge() -> None:
    cfg = Settings(rare_share=0.1, rare_min_entries=20)
    assert len(only("rare_poster", cfg, lines=people(20, 1))) == 1
    assert not only("rare_poster", cfg, lines=people(19, 1))


def test_natural_key_orders_digit_runs_as_numbers() -> None:
    ids = ["L10", "L2", "L1", "M1", "L2a"]
    assert sorted(ids, key=natural_key) == ["L1", "L2", "L2a", "L10", "M1"]


def test_first_line_uses_natural_order_of_unpadded_ids() -> None:
    lines = [
        line(je="JE-1", line_id="L10", day=date(2025, 3, 8)),
        line(je="JE-1", line_id="L2", day=date(2025, 3, 10)),
    ]
    assert not only("weekend_posting", lines=lines)
    lines = [
        line(je="JE-1", line_id="L10", day=date(2025, 3, 10)),
        line(je="JE-1", line_id="L2", day=date(2025, 3, 8)),
    ]
    found = only("weekend_posting", lines=lines)
    assert found[0].row_ids == ("L2", "L10")


def test_gap_in_unpadded_numbers() -> None:
    ids = [f"JE{n}" for n in (*range(1, 10), 11)]
    found = only("entry_number_gap", lines=[line(je=i) for i in ids])
    assert [f.unit_id for f in found] == ["JE10"]


def test_gap_with_a_year_in_the_prefix() -> None:
    ids = ["JE-2025-0001", "JE-2025-0002", "JE-2025-0004"]
    found = only("entry_number_gap", lines=[line(je=i) for i in ids])
    assert [f.unit_id for f in found] == ["JE-2025-0003"]


def test_gap_prefixes_are_separate_sequences() -> None:
    ids = ["A1", "A3", "B1", "B2"]
    found = only("entry_number_gap", lines=[line(je=i) for i in ids])
    assert [f.unit_id for f in found] == ["A2"]


def test_report_counts_ids_without_digits() -> None:
    lines = [line(je="alpha"), line(je="beta"), line(je="JE-1")]
    result = analyze(ledger(lines=lines), S)
    assert result.unnumbered_ids == 2


def test_ids_that_share_a_number_are_counted() -> None:
    lines = [line(je="JE-1"), line(je="JE-001"), line(je="JE-3"), line(je="alpha")]
    result = analyze(ledger(lines=lines), S)
    assert result.shared_numbers == 1
    assert result.unnumbered_ids == 1
    text = report.markdown(result)
    assert "ids that share a number: 1" in text
