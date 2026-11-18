"""Entry points for the browser demo. The page calls these inside Pyodide."""

import csv
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .analyze import AnalysisResult, analyze
from .benford import BenfordResult
from .config import load_column_map
from .evaluate import (
    DEFAULT_COSTS,
    INSTALL_HINT,
    RULE_TYPES,
    Label,
    Scores,
    _flag_units,
    _labeled_units,
    f1,
    precision,
    read_labels,
    recall,
    score,
)
from .io import SPECS, plain, read_folder
from .models import Flag, Ledger, Settings
from .report import DISCLAIMER, NOTICE, _benford_head, _csv_text

MAX_MONTHS = 24
MAX_RATE = 0.2
SIZES = ("small", "medium", "large")
UNUSED = "__not_used__.csv"
Result = dict[str, Any]


def _check_inputs(seed: object, months: object, size: object, rate: object) -> None:
    if type(seed) is not int or seed < 0:
        raise ValueError("seed: use a whole number, 0 or more")
    if type(months) is not int or not 1 <= months <= MAX_MONTHS:
        raise ValueError(f"months: use a whole number from 1 to {MAX_MONTHS}")
    if size not in SIZES:
        raise ValueError("size: use small, medium or large")
    if not isinstance(rate, int | float) or isinstance(rate, bool):
        raise ValueError(f"rate: use a number from 0 to {MAX_RATE}")
    if not 0 <= rate <= MAX_RATE:
        raise ValueError(f"rate: use a number from 0 to {MAX_RATE}")


def _benford_dict(b: BenfordResult) -> Result:
    return {
        "field": b.field,
        "status": b.status,
        "reason": b.reason,
        "line": _benford_head(b),
        "n": b.n,
        "counts": list(b.counts),
        "expected": list(b.expected_shares),
        "mad": b.mad,
        "mad_label": b.mad_label,
        "chi_square": b.chi_square,
        "p_value": b.p_value,
        "note": b.note,
    }


def _item(flag: Flag, mark: str) -> Result:
    return {
        "rule": flag.rule,
        "table": flag.table,
        "unit_id": flag.unit_id,
        "row_ids": " ".join(flag.row_ids),
        "reason": flag.reason,
        "mark": mark,
    }


def _common(result: AnalysisResult, mode: str) -> Result:
    return {
        "mode": mode,
        "counts": result.counts,
        "skips": result.skips,
        "tables": result.table_rows,
        "benford": [_benford_dict(b) for b in result.benford],
        "items_csv": _csv_text(result),
        "notice": NOTICE,
        "disclaimer": DISCLAIMER,
        "rules": [],
        "unscored": {},
    }


def _marks(
    flags: list[Flag], labels: list[Label], ledger: Ledger, skipped: set[str]
) -> list[Result]:
    """Each flag as hit, false_alarm or other_label, then each miss."""
    by_type, details = _labeled_units(labels, ledger)
    covered: dict[str, set[tuple[str, str]]] = {}
    items = []
    for flag in flags:
        kinds = RULE_TYPES.get(flag.rule)
        if kinds is None:
            items.append(_item(flag, "not_scored"))
            continue
        mine = set().union(*(by_type.get(k, set()) for k in kinds))
        units = _flag_units(flag)
        if units & mine:
            covered.setdefault(flag.rule, set()).update(units & mine)
            items.append(_item(flag, "hit"))
        elif units & set().union(*(u for t, u in by_type.items() if t not in kinds)):
            items.append(_item(flag, "other_label"))
        else:
            items.append(_item(flag, "false_alarm"))
    for rule, kinds in RULE_TYPES.items():
        if rule in skipped:
            continue
        mine = set().union(*(by_type.get(k, set()) for k in kinds))
        for unit in sorted(mine - covered.get(rule, set())):
            miss = Flag(rule, unit[0], unit[1], (), details[unit][0])
            items.append(_item(miss, "miss"))
    return items


def _rule_rows(scores: Scores) -> list[Result]:
    rows = []
    for rule, s in scores.rules.items():
        rows.append(
            {
                "rule": rule,
                "anomaly_type": s.anomaly_type,
                "labeled": s.labeled,
                "flags": s.flags,
                "tp": s.tp,
                "fp": s.fp,
                "other_label": s.other_label,
                "misses": s.misses,
                "precision": precision(s.tp, s.fp),
                "recall": recall(s.tp, s.misses),
                "f1": f1(s.tp, s.fp, s.misses),
            }
        )
    return rows


def run_synthetic(seed: int, months: int, size: str, rate: float) -> Result:
    """Make synthbiz data, run the rules and score them against its labels."""
    _check_inputs(seed, months, size, rate)
    try:
        from synthbiz.generate import Params, generate
        from synthbiz.io import write_dataset
    except ImportError:
        raise ValueError(INSTALL_HINT) from None
    params = Params(seed=seed, months=months, size=size, anomaly_rate=float(rate))
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "data"
        write_dataset(generate(params), folder)
        ledger = read_folder(folder)
        labels = read_labels(folder)
    result = analyze(ledger, Settings())
    scores = score(result.flags, labels, ledger, DEFAULT_COSTS)
    out = _common(result, "synthetic")
    out["info"] = {
        "seed": seed,
        "months": months,
        "size": size,
        "rate": float(rate),
        "labels": len(labels),
    }
    out["rules"] = _rule_rows(scores)
    out["unscored"] = dict(scores.unscored)
    out["items"] = _marks(result.flags, labels, ledger, set(result.skips))
    return out


def prepare_folder(path: str) -> None:
    """Make an empty folder, removing what was there."""
    folder = Path(path)
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)


def read_header(folder: str, name: str) -> list[str]:
    """The header row of one file, so the page can offer the columns."""
    path = Path(folder) / name
    shown = plain(name)
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            header = next(csv.reader(f, strict=True), None)
    except UnicodeDecodeError:
        raise ValueError(f"{shown}: not valid UTF-8, save it as a UTF-8 CSV") from None
    except csv.Error as e:
        raise ValueError(f"{shown}: not valid CSV, {e}") from None
    except OSError as e:
        raise ValueError(f"{shown}: could not read the file ({e.strerror})") from None
    if header is None:
        raise ValueError(f"{shown}: file is empty")
    return header


def _column_map_json(
    tables: dict[str, dict[str, Any]], date_format: str, amounts: str
) -> str:
    files = {t: UNUSED for t in SPECS}
    columns: dict[str, dict[str, str]] = {}
    for table, spec in tables.items():
        if table not in SPECS:
            raise ValueError(
                f"table {plain(str(table))[:40]}: use one of {list(SPECS)}"
            )
        if not spec.get("file"):
            raise ValueError(f"Choose a file for {table}, or remove the table.")
        files[table] = spec["file"]
        chosen = {k: v for k, v in spec.get("columns", {}).items() if v}
        if chosen:
            columns[table] = chosen
    data = {
        "files": files,
        "columns": columns,
        "date_format": date_format,
        "amounts": amounts,
    }
    return json.dumps(data)


def run_files(
    folder: str,
    tables: dict[str, dict[str, Any]],
    date_format: str = "%Y-%m-%d",
    amounts: str = "cents",
) -> Result:
    """Run the rules on CSV files already written to folder."""
    if not tables:
        raise ValueError("Choose a file for at least one table, then run again.")
    text = _column_map_json(tables, date_format, amounts)
    with tempfile.TemporaryDirectory() as tmp:
        map_path = Path(tmp) / "column_map.json"
        map_path.write_text(text, "utf-8")
        cmap = load_column_map(map_path)
    ledger = read_folder(Path(folder), cmap)
    result = analyze(ledger, Settings())
    out = _common(result, "files")
    out["items"] = [_item(f, "to_check") for f in result.flags]
    return out
