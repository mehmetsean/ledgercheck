import json
from datetime import date
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from helpers import invoice, ledger, line, payment
from ledgercheck import evaluate as ev
from ledgercheck.models import Flag

COSTS = ev.DEFAULT_COSTS
SAT = date(2025, 3, 8)


def label(table: str, row: str, kind: str, details: str = "d") -> ev.Label:
    return ev.Label(table, row, kind, details)


def jflag(rule: str, je: str) -> Flag:
    return Flag(rule, "journal_lines", je, (je + "-L1",), "r")


def two_line_ledger():
    lines = [
        line("JE-1", SAT, line_id="L1"),
        line("JE-1", SAT, line_id="L2"),
        line("JE-2", SAT, line_id="L3"),
        line("JE-3", SAT, line_id="L4"),
    ]
    return ledger(lines=lines)


def test_journal_label_on_first_line_maps_to_entry():
    lab = [label("journal_lines", "L1", "weekend_posting")]
    s = ev.score([jflag("weekend_posting", "JE-1")], lab, two_line_ledger(), COSTS)
    r = s.rules["weekend_posting"]
    assert (r.tp, r.fp, r.misses) == (1, 0, 0)


def test_journal_label_on_later_line_maps_to_same_entry():
    lab = [label("journal_lines", "L2", "weekend_posting")]
    s = ev.score([jflag("weekend_posting", "JE-1")], lab, two_line_ledger(), COSTS)
    assert s.rules["weekend_posting"].tp == 1


def test_unknown_label_row_is_an_error():
    lab = [label("journal_lines", "NOPE", "weekend_posting")]
    with pytest.raises(ValueError, match="journal line"):
        ev.score([], lab, two_line_ledger(), COSTS)


def test_label_for_a_table_not_loaded_is_ignored():
    lab = [label("ap_payments", "P1", "exact_duplicate_payment")]
    s = ev.score([], lab, two_line_ledger(), COSTS)
    assert "duplicate_exact" not in s.rules


def test_duplicate_scores_on_the_later_payment():
    inv = [invoice("I1", "V1", "N1", date(2025, 3, 3), 1000)]
    pays = [
        payment("P1", "V1", "I1", date(2025, 3, 5), 1000),
        payment("P2", "V1", "I1", date(2025, 3, 6), 1000),
    ]
    led = ledger(invoices=inv, payments=pays, vendors=[])
    later = Flag("duplicate_exact", "ap_payments", "P2", ("P2", "P1"), "r")
    earlier = Flag("duplicate_exact", "ap_payments", "P1", ("P1",), "r")
    lab = [label("ap_payments", "P2", "exact_duplicate_payment")]
    hit = ev.score([later], lab, led, COSTS).rules["duplicate_exact"]
    wrong = ev.score([earlier], lab, led, COSTS).rules["duplicate_exact"]
    assert (hit.tp, hit.fp, hit.misses) == (1, 0, 0)
    assert (wrong.tp, wrong.fp, wrong.misses) == (0, 1, 1)


def test_split_group_is_a_hit_when_it_holds_the_labeled_invoice():
    inv = [invoice(f"I{n}", "V1", f"N{n}", date(2025, 3, 3), 480_000) for n in (1, 2)]
    led = ledger(invoices=inv)
    group = Flag("split_under_limit", "ap_invoices", "I1", ("I1", "I2"), "r")
    first = [label("ap_invoices", "I1", "split_invoice")]
    second = [label("ap_invoices", "I2", "split_invoice")]
    assert ev.score([group], first, led, COSTS).rules["split_under_limit"].tp == 1
    assert ev.score([group], second, led, COSTS).rules["split_under_limit"].tp == 1


def test_flag_on_a_unit_with_another_label_is_other_label_not_fp():
    lab = [label("journal_lines", "L3", "round_amount_entry")]
    flags = [jflag("weekend_posting", "JE-2"), jflag("weekend_posting", "JE-3")]
    r = ev.score(flags, lab, two_line_ledger(), COSTS).rules["weekend_posting"]
    assert (r.tp, r.fp, r.other_label) == (0, 1, 1)


def test_no_flags_means_precision_is_undefined():
    lab = [label("journal_lines", "L1", "weekend_posting")]
    r = ev.score([], lab, two_line_ledger(), COSTS).rules["weekend_posting"]
    assert ev.precision(r.tp, r.fp) is None
    assert ev.recall(r.tp, r.misses) == 0.0
    assert ev.f1(r.tp, r.fp, r.misses) is None


def test_cost_and_baselines():
    costs = ev.CostTable(10.0, {**COSTS.miss_cost, "weekend_posting": 100.0})
    lab = [
        label("journal_lines", "L1", "weekend_posting"),
        label("journal_lines", "L3", "weekend_posting"),
    ]
    flags = [jflag("weekend_posting", "JE-1"), jflag("weekend_posting", "JE-3")]
    r = ev.score(flags, lab, two_line_ledger(), costs).rules["weekend_posting"]
    assert r.cost == 100.0 * 1 + 10.0 * 2
    assert r.cost_nothing == 200.0
    assert r.cost_everything == 10.0 * 3


def test_any_rule_recall_counts_other_rules_and_ignores_unscored_ones():
    lab = [label("journal_lines", "L1", "round_amount_entry")]
    flags = [jflag("weekend_posting", "JE-1"), jflag("entry_number_gap", "JE-2")]
    s = ev.score(flags, lab, two_line_ledger(), COSTS)
    assert s.any_rule["round_amount_entry"] == ev.AnyRule(1, 1)
    assert s.rules["round_amount"].misses == 1


def test_missed_details_are_shown_not_parsed():
    lab = [label("journal_lines", "L1", "weekend_posting", "free text {x}")]
    r = ev.score([], lab, two_line_ledger(), COSTS).rules["weekend_posting"]
    assert r.missed_details == ("free text {x}",)


def test_rules_with_missing_tables_are_skipped():
    s = ev.score([], [], ledger(invoices=[]), COSTS)
    assert set(s.rules) == {"split_under_limit"}


counts = st.integers(0, 50)


@given(counts, counts, counts)
def test_metrics_stay_in_range(tp, fp, fn):
    for value in (ev.precision(tp, fp), ev.recall(tp, fn), ev.f1(tp, fp, fn)):
        assert value is None or 0.0 <= value <= 1.0


@given(counts, counts)
def test_perfect_counts_give_one(tp, n):
    if tp:
        assert ev.precision(tp, 0) == ev.recall(tp, 0) == ev.f1(tp, 0, 0) == 1.0


@given(counts, counts)
def test_extra_false_positive_never_raises_precision(tp, fp):
    before = ev.precision(tp, fp)
    after = ev.precision(tp, fp + 1)
    assert after is not None
    assert before is None or after <= before


@given(st.sets(st.integers(0, 14), max_size=15), st.sets(st.integers(0, 14)))
def test_score_perfect_flags_and_extra_flag(labeled, extra):
    lines = [line(f"JE-{n}", SAT, line_id=f"L{n}") for n in range(15)]
    led = ledger(lines=lines)
    lab = [label("journal_lines", f"L{n}", "weekend_posting") for n in labeled]
    perfect = [jflag("weekend_posting", f"JE-{n}") for n in sorted(labeled)]
    r = ev.score(perfect, lab, led, COSTS).rules["weekend_posting"]
    assert r.misses == 0 and r.fp == 0
    more = perfect + [jflag("weekend_posting", f"JE-{n}") for n in extra - labeled]
    r2 = ev.score(more, lab, led, COSTS).rules["weekend_posting"]
    p1, p2 = ev.precision(r.tp, r.fp), ev.precision(r2.tp, r2.fp)
    assert p1 is None or p2 is None or p2 <= p1


def test_bootstrap_is_repeatable_and_ordered():
    per_seed = [(3, 1, 2), (4, 0, 1), (2, 2, 2), (5, 1, 0)]
    a = ev.bootstrap(per_seed, ev._pick_recall)
    b = ev.bootstrap(per_seed, ev._pick_recall)
    assert a == b and a is not None and a[0] <= a[1]


@given(
    st.lists(st.tuples(counts, counts, counts), min_size=1, max_size=8),
    st.integers(0, 1000),
)
def test_bootstrap_lower_not_above_upper(per_seed, seed):
    for pick in (ev._pick_precision, ev._pick_recall, ev._pick_f1):
        got = ev.bootstrap(per_seed, pick, draws=50, seed=seed)
        assert got is None or got[0] <= got[1]


@given(st.tuples(counts, counts, counts), st.integers(1, 8))
def test_bootstrap_has_zero_width_when_every_seed_scores_the_same(one, n):
    for pick in (ev._pick_precision, ev._pick_recall, ev._pick_f1):
        got = ev.bootstrap([one] * n, pick, draws=50)
        assert got is None or got[0] == got[1]


def test_bootstrap_with_no_defined_value_is_none():
    assert ev.bootstrap([(0, 0, 0)], ev._pick_precision, draws=10) is None


def test_parse_seeds():
    assert ev.parse_seeds("1-3", "x") == (1, 2, 3)
    assert ev.parse_seeds("5,1-2", "x") == (5, 1, 2)
    assert len(ev.parse_seeds("1-1000", "x")) == 1000


@pytest.mark.parametrize(
    "text", ["", "a", "3-1", "1-1001", "1,1", "-5", "1-2-3", "1,,2", "9999999999"]
)
def test_parse_seeds_errors(text):
    with pytest.raises(ValueError):
        ev.parse_seeds(text, "seeds")


def test_load_costs(tmp_path: Path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"check_cost": 5, "miss_cost": {"split_invoice": 9}}))
    got = ev.load_costs(path)
    assert got.check_cost == 5.0
    assert got.miss_cost["split_invoice"] == 9.0
    assert got.miss_cost["weekend_posting"] == COSTS.miss_cost["weekend_posting"]


@pytest.mark.parametrize(
    "body",
    [
        "{bad",
        "[]",
        '{"other": 1}',
        '{"check_cost": -1}',
        '{"check_cost": true}',
        '{"check_cost": "5"}',
        '{"miss_cost": 3}',
        '{"miss_cost": {"nope": 1}}',
        '{"miss_cost": {"split_invoice": 1e99}}',
    ],
)
def test_load_costs_errors(tmp_path: Path, body: str):
    path = tmp_path / "c.json"
    path.write_text(body)
    with pytest.raises(ValueError):
        ev.load_costs(path)


def test_load_costs_missing_file(tmp_path: Path):
    with pytest.raises(ValueError):
        ev.load_costs(tmp_path / "none.json")


def test_read_labels_and_errors(tmp_path: Path):
    with pytest.raises(ValueError, match="no labels.csv"):
        ev.read_labels(tmp_path)
    path = tmp_path / "labels.csv"
    path.write_text('table,row_id,anomaly_type,details\nap_payments,P1,x,"a, b"\n')
    assert ev.read_labels(tmp_path) == [label("ap_payments", "P1", "x", "a, b")]
    path.write_text("a,b\n")
    with pytest.raises(ValueError, match="columns"):
        ev.read_labels(tmp_path)
    path.write_text("table,row_id,anomaly_type,details\nonly,two\n")
    with pytest.raises(ValueError, match="not valid"):
        ev.read_labels(tmp_path)
    path.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(ValueError, match="not valid CSV"):
        ev.read_labels(tmp_path)


def test_read_manifest_info(tmp_path: Path):
    assert ev.read_manifest_info(tmp_path) is None
    path = tmp_path / "manifest.json"
    params = {"seed": 1, "size": "small", "months": 3, "anomaly_rate": 0.1}
    path.write_text(json.dumps({"parameters": params}))
    got = ev.read_manifest_info(tmp_path)
    assert got is not None and got["anomaly_rate"] == "0.1"
    path.write_text("{}")
    with pytest.raises(ValueError, match="manifest"):
        ev.read_manifest_info(tmp_path)
