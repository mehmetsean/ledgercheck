import json
import random
from datetime import date
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from helpers import invoice, ledger, line, payment
from ledgercheck import evaluate as ev
from ledgercheck.models import Flag, Vendor

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
    assert ev.parse_seeds("1-3", "x", 10) == (1, 2, 3)
    assert ev.parse_seeds("5,1-2", "x", 10) == (5, 1, 2)
    assert len(ev.parse_seeds("1-50", "x", 50)) == 50


@pytest.mark.parametrize(
    "text", ["", "a", "3-1", "1-51", "1,1", "-5", "1-2-3", "1,,2", "9999999999"]
)
def test_parse_seeds_errors(text):
    with pytest.raises(ValueError):
        ev.parse_seeds(text, "seeds", 50)


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
    with pytest.raises(ValueError, match="no such file"):
        ev.load_costs(tmp_path / "none.json")


def test_load_costs_refuses_big_files_and_links(tmp_path: Path):
    big = tmp_path / "big.json"
    big.write_text(" " * 1_000_001)
    with pytest.raises(ValueError, match="larger than"):
        ev.load_costs(big)
    link = tmp_path / "link.json"
    link.symlink_to(big)
    with pytest.raises(ValueError, match="symbolic link"):
        ev.load_costs(link)


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


def test_label_for_a_ledger_with_no_journal_table_is_ignored():
    lab = [label("journal_lines", "L1", "weekend_posting")]
    s = ev.score([], lab, ledger(invoices=[]), COSTS)
    assert set(s.rules) == {"split_under_limit"}


def test_lookup_is_built_once_per_score(monkeypatch: pytest.MonkeyPatch):
    calls = []
    real = ev._lookup
    monkeypatch.setattr(ev, "_lookup", lambda led: calls.append(1) or real(led))
    lab = [label("journal_lines", f"L{n}", "weekend_posting") for n in (1, 3, 4)]
    ev.score([], lab, two_line_ledger(), COSTS)
    assert len(calls) == 1


def test_bootstrap_percentile_indexes_on_a_small_draw_set():
    per_seed = [(1, 0, 0), (2, 0, 0), (4, 0, 0), (8, 0, 0), (16, 0, 0)]
    draws, seed = 40, 1
    rng = random.Random(seed)
    sums = sorted(
        sum(per_seed[rng.randrange(5)][0] for _ in range(5)) for _ in range(draws)
    )
    assert len({sums[0], sums[1], sums[2]}) == 3
    assert len({sums[37], sums[38], sums[39]}) == 3
    got = ev.bootstrap(per_seed, lambda tp, fp, m: float(tp), draws=draws, seed=seed)
    assert got == (sums[0], sums[38])


def test_each_draw_resamples_exactly_n_seeds():
    per_seed = [(1, 0, 0)] * 5
    got = ev.bootstrap(per_seed, lambda tp, fp, m: float(tp), draws=30)
    assert got == (5.0, 5.0)


def test_ties_go_to_the_run_default():
    from synthbiz.generate import Params

    seeds = [ev.make_seed(1, ev.EvalParams("small", 2, 0.3))]
    zero = ev.CostTable(0.0, dict.fromkeys(COSTS.miss_cost, 0.0))
    grid = ev.Grid((0.6, 0.9), (0.6, 0.9), (0.02, 0.1))
    chosen, _ = ev.tune(seeds, zero, grid)
    assert chosen.duplicates.name_threshold == 0.8
    assert chosen.duplicates.invoice_threshold == 0.8
    assert chosen.rare_share == 0.05
    assert Params().anomaly_rate == ev.DEFAULT_RATE


def test_labels_symlink_is_refused(tmp_path: Path):
    real = tmp_path / "real.csv"
    real.write_text("table,row_id,anomaly_type,details\n")
    (tmp_path / "labels.csv").symlink_to(real)
    with pytest.raises(ValueError, match="symbolic link"):
        ev.read_labels(tmp_path)


def test_big_labels_and_manifest_files_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    (tmp_path / "labels.csv").write_text("table,row_id,anomaly_type,details\n")
    (tmp_path / "manifest.json").write_text("{}" + " " * 50)
    monkeypatch.setattr(ev, "MAX_FILE_BYTES", 10)
    monkeypatch.setattr(ev, "MAX_MANIFEST_BYTES", 10)
    with pytest.raises(ValueError, match="larger than"):
        ev.read_labels(tmp_path)
    with pytest.raises(ValueError, match="larger than"):
        ev.read_manifest_info(tmp_path)


def test_manifest_symlink_is_refused(tmp_path: Path):
    real = tmp_path / "real.json"
    real.write_text("{}")
    (tmp_path / "manifest.json").symlink_to(real)
    with pytest.raises(ValueError, match="symbolic link"):
        ev.read_manifest_info(tmp_path)


def test_check_work_limits():
    ev.check_work(range(50), range(200), 24)
    with pytest.raises(ValueError, match="--tune-seeds"):
        ev.check_work(range(51), [1], 1)
    with pytest.raises(ValueError, match="--seeds"):
        ev.check_work([1], range(201), 1)
    with pytest.raises(ValueError, match="seeds times months"):
        ev.check_work(range(50), range(200), 25)


def pay_ledger():
    pays = [
        payment("P1", "V1", "I1", SAT, 500),
        payment("P2", "V1", "I2", SAT, 500),
        payment("P3", "V2", "I3", SAT, 700),
    ]
    vendors = [Vendor("V1", "A Co"), Vendor("V2", "B Co")]
    return ledger(invoices=[], payments=pays, vendors=vendors)


def pflag(rule: str, pay: str) -> Flag:
    return Flag(rule, "ap_payments", pay, (pay,), "r")


def test_every_rule_maps_to_a_tuple_of_types():
    assert ev.RULE_TYPES["duplicate_fuzzy"] == (
        "near_duplicate_payment",
        "typo_duplicate_payment",
    )
    assert ev.RULE_TYPES["duplicate_exact"] == ("exact_duplicate_payment",)
    for kinds in ev.RULE_TYPES.values():
        for kind in kinds:
            assert kind in COSTS.miss_cost


def test_typo_duplicate_is_ap_payments_and_costs_like_near():
    assert ev.TYPE_TABLE["typo_duplicate_payment"] == "ap_payments"
    typo = COSTS.miss_cost["typo_duplicate_payment"]
    assert typo == COSTS.miss_cost["near_duplicate_payment"] == 800.0


def test_fuzzy_scores_typo_duplicates():
    lab = [
        label("ap_payments", "P2", "typo_duplicate_payment"),
        label("ap_payments", "P3", "near_duplicate_payment"),
    ]
    flags = [pflag("duplicate_fuzzy", "P2")]
    s = ev.score(flags, lab, pay_ledger(), COSTS)
    r = s.rules["duplicate_fuzzy"]
    assert (r.labeled, r.tp, r.fp, r.other_label, r.misses) == (2, 1, 0, 0, 1)
    assert r.cost == 800.0 + 20.0
    assert s.any_rule["typo_duplicate_payment"] == ev.AnyRule(1, 1)
    assert s.any_rule["near_duplicate_payment"] == ev.AnyRule(1, 0)


def test_exact_rule_does_not_score_typo_duplicates():
    lab = [label("ap_payments", "P2", "typo_duplicate_payment")]
    flags = [pflag("duplicate_exact", "P2")]
    r = ev.score(flags, lab, pay_ledger(), COSTS).rules["duplicate_exact"]
    assert (r.labeled, r.tp, r.other_label) == (0, 0, 1)


def test_unknown_label_type_does_not_crash_and_is_reported():
    lab = [
        label("journal_lines", "L1", "future_type"),
        label("ap_payments", "P1", "other_future_type"),
        label("ap_payments", "P2", "other_future_type"),
    ]
    led = ledger(
        lines=[line("JE-1", SAT, line_id="L1")],
        payments=[payment("P1", "V1", "I1", SAT, 5), payment("P2", "V1", "I2", SAT, 5)],
    )
    flags = [jflag("weekend_posting", "JE-1")]
    s = ev.score(flags, lab, led, COSTS)
    assert s.unscored == {"future_type": 1, "other_future_type": 2}
    assert s.rules["weekend_posting"].other_label == 1
    assert s.rules["weekend_posting"].fp == 0


def test_scored_types_are_not_listed_as_unscored():
    lab = [label("journal_lines", "L1", "weekend_posting")]
    assert ev.score([], lab, two_line_ledger(), COSTS).unscored == {}


def test_costs_follow_each_label_type():
    miss = {**COSTS.miss_cost, "near_duplicate_payment": 800.0}
    miss["typo_duplicate_payment"] = 50.0
    costs = ev.CostTable(10.0, miss)
    lab = [
        label("ap_payments", "P2", "typo_duplicate_payment"),
        label("ap_payments", "P3", "near_duplicate_payment"),
    ]
    r = ev.score([], lab, pay_ledger(), costs).rules["duplicate_fuzzy"]
    assert r.cost == 850.0
    assert r.cost_nothing == 850.0
    caught = [pflag("duplicate_fuzzy", "P3")]
    r = ev.score(caught, lab, pay_ledger(), costs).rules["duplicate_fuzzy"]
    assert r.cost == 50.0 + 10.0
    assert r.cost_nothing == 850.0
