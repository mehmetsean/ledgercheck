"""Score flags against synthbiz labels. The only module that reads labels."""

import csv
import json
import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from .duplicates import find_duplicates
from .io import MAX_ROWS_PER_FILE, plain
from .models import (
    DuplicateSettings,
    Flag,
    Invoice,
    JournalLine,
    Ledger,
    Payment,
    Settings,
    Vendor,
)
from .rules import RULES, group_entries, journal_flags, run_rules, skip_reasons

RULE_TYPES = {
    "weekend_posting": "weekend_posting",
    "holiday_posting": "holiday_posting",
    "round_amount": "round_amount_entry",
    "rare_poster": "unusual_user",
    "no_approver": "missing_approval",
    "period_mismatch": "out_of_period_entry",
    "split_under_limit": "split_invoice",
    "duplicate_exact": "exact_duplicate_payment",
    "duplicate_fuzzy": "near_duplicate_payment",
}
SCORED_RULES = tuple(r for r in RULES if r in RULE_TYPES)
TYPE_TABLE = {
    "split_invoice": "ap_invoices",
    "exact_duplicate_payment": "ap_payments",
    "near_duplicate_payment": "ap_payments",
}
LABEL_COLUMNS = ["table", "row_id", "anomaly_type", "details"]
JOURNAL = "journal_lines"
INVOICES = "ap_invoices"
PAYMENTS = "ap_payments"

DRAWS = 2000
BOOTSTRAP_SEED = 20261117
MAX_SEEDS = 1000
DEFAULT_RATE = 0.02
INSTALL_HINT = (
    'synthbiz is not installed, install the eval extra: pip install "ledgercheck[eval]"'
)
SYNTHETIC = "measured on synthetic data (synthbiz)"
FUZZY_LIMIT = (
    "synthbiz near duplicates differ only in vendor suffix or punctuation and "
    "keep the invoice number, so measured fuzzy recall says nothing about typos."
)

Unit = tuple[str, str]


@dataclass(frozen=True)
class Label:
    table: str
    row_id: str
    anomaly_type: str
    details: str


@dataclass(frozen=True)
class CostTable:
    """Placeholder costs, not real prices."""

    check_cost: float
    miss_cost: dict[str, float]


DEFAULT_COSTS = CostTable(
    check_cost=20.0,
    miss_cost={
        "weekend_posting": 100.0,
        "holiday_posting": 100.0,
        "round_amount_entry": 100.0,
        "unusual_user": 150.0,
        "missing_approval": 200.0,
        "out_of_period_entry": 300.0,
        "split_invoice": 600.0,
        "exact_duplicate_payment": 1000.0,
        "near_duplicate_payment": 800.0,
    },
)


@dataclass(frozen=True)
class RuleScore:
    rule: str
    anomaly_type: str
    labeled: int
    flags: int
    tp: int
    fp: int
    other_label: int
    misses: int
    units: int
    cost: float
    cost_nothing: float
    cost_everything: float
    missed_details: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnyRule:
    labeled: int
    caught: int


@dataclass(frozen=True)
class Scores:
    rules: dict[str, RuleScore]
    any_rule: dict[str, AnyRule]


@dataclass(frozen=True)
class Grid:
    name_thresholds: tuple[float, ...]
    invoice_thresholds: tuple[float, ...]
    rare_shares: tuple[float, ...]


THRESHOLDS = tuple(round(0.6 + 0.05 * i, 2) for i in range(8))
DEFAULT_GRID = Grid(THRESHOLDS, THRESHOLDS, (0.02, 0.05, 0.1))


@dataclass(frozen=True)
class EvalParams:
    size: str = "small"
    months: int = 12
    rate: float = DEFAULT_RATE


Interval = tuple[float, float]


@dataclass(frozen=True)
class RulePooled:
    rule: str
    anomaly_type: str
    labeled: int
    flags: int
    tp: int
    fp: int
    other_label: int
    misses: int
    units: int
    cost: float
    cost_nothing: float
    cost_everything: float
    precision: float | None
    recall: float | None
    f1: float | None
    precision_ci: Interval | None
    recall_ci: Interval | None
    f1_ci: Interval | None


@dataclass(frozen=True)
class AnyPooled:
    labeled: int
    caught: int
    recall: float | None
    recall_ci: Interval | None


@dataclass(frozen=True)
class EvalReport:
    params: EvalParams
    costs: CostTable
    grid: Grid
    tune_seeds: tuple[int, ...]
    report_seeds: tuple[int, ...]
    settings: Settings
    rules: dict[str, RulePooled]
    any_rule: dict[str, AnyPooled]
    mean_labels: float
    tune_cost: float = 0.0
    seed_scores: list[Scores] = field(default_factory=list)


def precision(tp: int, fp: int) -> float | None:
    return tp / (tp + fp) if tp + fp else None


def recall(tp: int, misses: int) -> float | None:
    return tp / (tp + misses) if tp + misses else None


def f1(tp: int, fp: int, misses: int) -> float | None:
    if tp + fp == 0 or tp + misses == 0:
        return None
    return 2 * tp / (2 * tp + fp + misses)


def _csv_error(name: str, message: str) -> ValueError:
    return ValueError(f"{name}: {message}")


def read_labels(folder: Path) -> list[Label]:
    path = folder / "labels.csv"
    if not path.is_file():
        raise ValueError(f"no labels.csv in {plain(str(folder))}")
    out: list[Label] = []
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            rows = csv.reader(f, strict=True)
            header = next(rows, None)
            if header != LABEL_COLUMNS:
                raise _csv_error(
                    "labels.csv", "columns must be table,row_id,anomaly_type,details"
                )
            for row in rows:
                if len(out) >= MAX_ROWS_PER_FILE:
                    raise _csv_error("labels.csv", "too many rows")
                if len(row) != 4:
                    raise _csv_error("labels.csv", f"line {rows.line_num} is not valid")
                out.append(Label(row[0], row[1], row[2], row[3]))
    except (csv.Error, UnicodeDecodeError) as e:
        raise _csv_error("labels.csv", f"not valid CSV ({type(e).__name__})") from None
    return out


def read_manifest_info(folder: Path) -> dict[str, str] | None:
    """Seed, size, months and rate for display. None if there is no manifest."""
    path = folder / "manifest.json"
    if not path.is_file():
        return None
    try:
        params = json.loads(path.read_text("utf-8"))["parameters"]
        return {
            k: str(params[k])[:40] for k in ("seed", "size", "months", "anomaly_rate")
        }
    except (ValueError, KeyError, TypeError, RecursionError, OSError):
        raise ValueError("manifest.json could not be read") from None


def labels_from_dataset(rows: Sequence[dict[str, str]]) -> list[Label]:
    return [
        Label(r["table"], r["row_id"], r["anomaly_type"], r["details"]) for r in rows
    ]


def ledger_from_dataset(tables: dict[str, list[dict[str, Any]]]) -> Ledger:
    """The same Ledger that writing the files and read_folder would give."""
    lines = tuple(
        JournalLine(
            r["line_id"],
            r["je_id"],
            date.fromisoformat(r["posting_date"]),
            r["period"],
            r["account_id"],
            int(r["debit_cents"]),
            int(r["credit_cents"]),
            r["source_type"],
            r["created_by"],
            r["approved_by"],
        )
        for r in tables["journal_lines"]
    )
    invoices = tuple(
        Invoice(
            r["invoice_id"],
            r["vendor_id"],
            r["invoice_number"],
            date.fromisoformat(r["invoice_date"]),
            int(r["amount_cents"]),
        )
        for r in tables["ap_invoices"]
    )
    payments = tuple(
        Payment(
            r["payment_id"],
            r["vendor_id"],
            r["invoice_id"],
            date.fromisoformat(r["payment_date"]),
            int(r["amount_cents"]),
        )
        for r in tables["ap_payments"]
    )
    vendors = tuple(Vendor(r["vendor_id"], r["vendor_name"]) for r in tables["vendors"])
    return Ledger(lines, invoices, payments, vendors)


def _label_unit(
    label: Label, je_of_line: dict[str, str], ledger: Ledger
) -> Unit | None:
    """The scoring unit a label points to. None if its table is not loaded."""
    if label.table == JOURNAL and ledger.journal_lines is not None:
        if label.row_id not in je_of_line:
            raise ValueError("labels.csv names a journal line that is not in the data")
        return (JOURNAL, je_of_line[label.row_id])
    if label.table == INVOICES and ledger.invoices is not None:
        if label.row_id not in {x.invoice_id for x in ledger.invoices}:
            raise ValueError("labels.csv names an invoice that is not in the data")
        return (INVOICES, label.row_id)
    if label.table == PAYMENTS and ledger.payments is not None:
        if label.row_id not in {x.payment_id for x in ledger.payments}:
            raise ValueError("labels.csv names a payment that is not in the data")
        return (PAYMENTS, label.row_id)
    return None


def _labeled_units(
    labels: Sequence[Label], ledger: Ledger
) -> tuple[dict[str, set[Unit]], dict[Unit, list[str]]]:
    je_of_line = {x.line_id: x.je_id for x in ledger.journal_lines or ()}
    by_type: dict[str, set[Unit]] = {}
    details: dict[Unit, list[str]] = {}
    for label in labels:
        unit = _label_unit(label, je_of_line, ledger)
        if unit is None:
            continue
        by_type.setdefault(label.anomaly_type, set()).add(unit)
        details.setdefault(unit, []).append(label.details)
    return by_type, details


def _flag_units(flag: Flag) -> set[Unit]:
    if flag.table == INVOICES:
        return {(INVOICES, x) for x in flag.row_ids}
    return {(flag.table, flag.unit_id)}


def _unit_total(ledger: Ledger, table: str) -> int:
    if table == JOURNAL:
        return len(group_entries(ledger.journal_lines or ()))
    rows = ledger.invoices if table == INVOICES else ledger.payments
    return len(rows or ())


def score(
    flags: Sequence[Flag],
    labels: Sequence[Label],
    ledger: Ledger,
    costs: CostTable,
) -> Scores:
    by_type, details = _labeled_units(labels, ledger)
    skipped = skip_reasons(ledger)
    totals: dict[str, int] = {}
    rules: dict[str, RuleScore] = {}
    caught: set[Unit] = set()
    for rule in SCORED_RULES:
        if rule in skipped:
            continue
        kind = RULE_TYPES[rule]
        table = TYPE_TABLE.get(kind, JOURNAL)
        mine = by_type.get(kind, set())
        others = set().union(*(u for t, u in by_type.items() if t != kind))
        mine_flags = [f for f in flags if f.rule == rule]
        covered: set[Unit] = set()
        fp = other = 0
        for flag in mine_flags:
            units = _flag_units(flag)
            if units & mine:
                covered |= units & mine
            elif units & others:
                other += 1
            else:
                fp += 1
        caught |= set().union(*(_flag_units(f) for f in mine_flags))
        totals.setdefault(table, _unit_total(ledger, table))
        miss_cost = costs.miss_cost[kind]
        missed = sorted(mine - covered)
        rules[rule] = RuleScore(
            rule=rule,
            anomaly_type=kind,
            labeled=len(mine),
            flags=len(mine_flags),
            tp=len(covered),
            fp=fp,
            other_label=other,
            misses=len(mine) - len(covered),
            units=totals[table],
            cost=miss_cost * len(missed) + costs.check_cost * len(mine_flags),
            cost_nothing=miss_cost * len(mine),
            cost_everything=costs.check_cost * totals[table],
            missed_details=tuple(details[u][0] for u in missed[:5]),
        )
    any_rule = {}
    for score_ in rules.values():
        units = by_type.get(score_.anomaly_type, set())
        any_rule[score_.anomaly_type] = AnyRule(len(units), len(units & caught))
    return Scores(rules, any_rule)


def _ratio_metrics(
    triple: tuple[int, int, int],
) -> tuple[float | None, float | None, float | None]:
    tp, fp, misses = triple
    return precision(tp, fp), recall(tp, misses), f1(tp, fp, misses)


def bootstrap(
    per_seed: Sequence[tuple[int, int, int]],
    pick: Callable[[int, int, int], float | None],
    draws: int = DRAWS,
    seed: int = BOOTSTRAP_SEED,
) -> Interval | None:
    """95 percent percentile interval. Seeds are resampled with replacement.

    per_seed holds (tp, fp, misses) for each seed. Each draw sums the counts
    of the resampled seeds, then computes the metric from the sums.
    """
    rng = random.Random(seed)
    n = len(per_seed)
    values: list[float] = []
    for _ in range(draws):
        tp = fp = misses = 0
        for _ in range(n):
            a, b, c = per_seed[rng.randrange(n)]
            tp, fp, misses = tp + a, fp + b, misses + c
        value = pick(tp, fp, misses)
        if value is not None:
            values.append(value)
    if not values:
        return None
    values.sort()
    low = values[max(math.ceil(0.025 * len(values)) - 1, 0)]
    high = values[max(math.ceil(0.975 * len(values)) - 1, 0)]
    return (low, high)


def _pick_precision(tp: int, fp: int, misses: int) -> float | None:
    return precision(tp, fp)


def _pick_recall(tp: int, fp: int, misses: int) -> float | None:
    return recall(tp, misses)


def _pick_f1(tp: int, fp: int, misses: int) -> float | None:
    return f1(tp, fp, misses)


def _pool_rule(rule: str, items: list[RuleScore]) -> RulePooled:
    tp = sum(x.tp for x in items)
    fp = sum(x.fp for x in items)
    misses = sum(x.misses for x in items)
    per_seed = [(x.tp, x.fp, x.misses) for x in items]
    p, r, f = _ratio_metrics((tp, fp, misses))
    return RulePooled(
        rule=rule,
        anomaly_type=items[0].anomaly_type,
        labeled=sum(x.labeled for x in items),
        flags=sum(x.flags for x in items),
        tp=tp,
        fp=fp,
        other_label=sum(x.other_label for x in items),
        misses=misses,
        units=sum(x.units for x in items),
        cost=sum(x.cost for x in items),
        cost_nothing=sum(x.cost_nothing for x in items),
        cost_everything=sum(x.cost_everything for x in items),
        precision=p,
        recall=r,
        f1=f,
        precision_ci=bootstrap(per_seed, _pick_precision),
        recall_ci=bootstrap(per_seed, _pick_recall),
        f1_ci=bootstrap(per_seed, _pick_f1),
    )


def _pool_any(items: list[AnyRule]) -> AnyPooled:
    labeled = sum(x.labeled for x in items)
    caught = sum(x.caught for x in items)
    per_seed = [(x.caught, 0, x.labeled - x.caught) for x in items]
    return AnyPooled(
        labeled,
        caught,
        recall(caught, labeled - caught),
        bootstrap(per_seed, _pick_recall),
    )


def _synthbiz() -> Any:
    try:
        import synthbiz.check
        import synthbiz.generate
    except ImportError:
        raise ValueError(INSTALL_HINT) from None
    return synthbiz


@dataclass(frozen=True)
class SeedData:
    seed: int
    ledger: Ledger
    labels: list[Label]


def make_seed(seed: int, params: EvalParams) -> SeedData:
    gen = _synthbiz().generate
    ds = gen.generate(
        gen.Params(
            seed=seed, months=params.months, size=params.size, anomaly_rate=params.rate
        )
    )
    return SeedData(
        seed, ledger_from_dataset(ds.tables), labels_from_dataset(ds.labels)
    )


def max_months() -> int:
    return int(_synthbiz().check.MAX_MONTHS)


def settings_for(name: float, invoice: float, rare: float) -> Settings:
    dup = DuplicateSettings(name_threshold=name, invoice_threshold=invoice)
    return Settings(rare_share=rare, duplicates=dup)


def all_flags(ledger: Ledger, settings: Settings) -> list[Flag]:
    flags = (
        run_rules(ledger, settings) + find_duplicates(ledger, settings.duplicates).flags
    )
    return sorted(flags, key=lambda f: (RULES.index(f.rule), f.unit_id))


def _rule_cost(flags: list[Flag], data: SeedData, costs: CostTable, rule: str) -> float:
    return score(flags, data.labels, data.ledger, costs).rules[rule].cost


def tune(
    seeds: Sequence[SeedData], costs: CostTable, grid: Grid
) -> tuple[Settings, float]:
    """Lowest total cost on the tuning seeds.

    Costs add up per rule, and each setting changes one rule only: the two
    thresholds change duplicate_fuzzy, rare_share changes rare_poster. So the
    best point of the full grid is the best value of each part.
    """
    best_dup = (math.inf, grid.name_thresholds[0], grid.invoice_thresholds[0])
    for name in grid.name_thresholds:
        for inv in grid.invoice_thresholds:
            dup = DuplicateSettings(name_threshold=name, invoice_threshold=inv)
            total = 0.0
            for d in seeds:
                flags = find_duplicates(d.ledger, dup).flags
                total += _rule_cost(flags, d, costs, "duplicate_fuzzy")
            if total < best_dup[0]:
                best_dup = (total, name, inv)
    best_rare = (math.inf, grid.rare_shares[0])
    for share in grid.rare_shares:
        total = 0.0
        for d in seeds:
            lines = d.ledger.journal_lines or ()
            flags = journal_flags(lines, Settings(rare_share=share))
            total += _rule_cost(flags, d, costs, "rare_poster")
        if total < best_rare[0]:
            best_rare = (total, share)
    chosen = settings_for(best_dup[1], best_dup[2], best_rare[1])
    return chosen, best_dup[0] + best_rare[0]


def evaluate_seeds(
    tune_seeds: Sequence[int],
    report_seeds: Sequence[int],
    params: EvalParams,
    costs: CostTable,
    grid: Grid = DEFAULT_GRID,
) -> EvalReport:
    if params.months > max_months():
        raise ValueError(f"months must be at most {max_months()}")
    tuning = [make_seed(s, params) for s in tune_seeds]
    settings, tune_cost = tune(tuning, costs, grid)
    seed_scores = []
    label_total = 0
    for seed in report_seeds:
        data = make_seed(seed, params)
        flags = all_flags(data.ledger, settings)
        seed_scores.append(score(flags, data.labels, data.ledger, costs))
        label_total += len(data.labels)
    rules = {
        rule: _pool_rule(rule, [s.rules[rule] for s in seed_scores])
        for rule in seed_scores[0].rules
    }
    any_rule = {
        kind: _pool_any([s.any_rule[kind] for s in seed_scores])
        for kind in seed_scores[0].any_rule
    }
    return EvalReport(
        params=params,
        costs=costs,
        grid=grid,
        tune_seeds=tuple(tune_seeds),
        report_seeds=tuple(report_seeds),
        settings=settings,
        rules=rules,
        any_rule=any_rule,
        mean_labels=label_total / len(report_seeds),
        tune_cost=tune_cost,
        seed_scores=seed_scores,
    )


def evaluate_folder(
    folder: Path, settings: Settings, costs: CostTable
) -> tuple[Scores, int]:
    from .io import read_folder

    ledger = read_folder(folder)
    labels = read_labels(folder)
    return score(all_flags(ledger, settings), labels, ledger, costs), len(labels)


def load_costs(path: Path) -> CostTable:
    try:
        data = json.loads(path.read_text("utf-8"))
    except (ValueError, RecursionError):
        raise ValueError(f"{plain(path.name)}: not valid JSON") from None
    except OSError as e:
        raise ValueError(f"{plain(path.name)}: could not read ({e.strerror})") from None
    if not isinstance(data, dict) or set(data) - {"check_cost", "miss_cost"}:
        raise ValueError("costs file: keys must be check_cost and miss_cost only")
    check = _cost(data.get("check_cost", DEFAULT_COSTS.check_cost), "check_cost")
    miss = dict(DEFAULT_COSTS.miss_cost)
    given = data.get("miss_cost", {})
    if not isinstance(given, dict):
        raise ValueError("costs file: miss_cost must be an object")
    for kind, value in given.items():
        if kind not in miss:
            raise ValueError(
                f"costs file: unknown anomaly type {plain(str(kind))[:40]}"
            )
        miss[kind] = _cost(value, f"miss_cost {kind}")
    return CostTable(check, miss)


def _cost(value: Any, name: str) -> float:
    ok = isinstance(value, int | float) and not isinstance(value, bool)
    if not ok or not math.isfinite(value) or value < 0 or value > 1e12:
        raise ValueError(f"costs file: {name} must be a number from 0 to 1e12")
    return float(value)


def parse_seeds(text: str, name: str) -> tuple[int, ...]:
    """Seeds like 1-10 or 3,5,101-130. At most 1,000 of them."""
    seeds: list[int] = []
    for part in text.split(","):
        low, dash, high = part.strip().partition("-")
        if not (low.isdigit() and (not dash or high.isdigit())) or len(low + high) > 9:
            raise ValueError(f"{name}: use numbers like 1-10 or 3,5,101-130")
        first, last = int(low), int(high or low)
        if last < first:
            raise ValueError(f"{name}: range {part.strip()} runs backwards")
        if len(seeds) + last - first + 1 > MAX_SEEDS:
            raise ValueError(f"{name}: at most {MAX_SEEDS} seeds")
        seeds.extend(range(first, last + 1))
    if len(set(seeds)) != len(seeds):
        raise ValueError(f"{name}: a seed is listed twice")
    return tuple(seeds)
