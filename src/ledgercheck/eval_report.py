"""Write the evaluation files: evaluation.md, evaluation.html, metrics.json."""

import json
from pathlib import Path
from typing import Any

from .evaluate import (
    BOOTSTRAP_SEED,
    DRAWS,
    CostTable,
    EvalReport,
    RulePooled,
    RuleScore,
    Scores,
    f1,
    precision,
    recall,
)
from .io import plain
from .measured import (
    METHOD,
    RATE_HEAD,
    SYNTHETIC,
    entries,
    number,
    rate_rows,
    setup_lines,
    with_interval,
)
from .models import Settings
from .report import DISCLAIMER, FLAG_NOTE, NOTICE, h, html_table, prepare, write

EVAL_FILES = ("evaluation.md", "evaluation.html", "metrics.json", "README.txt")
COST_NOTE = (
    "Costs are placeholders in currency units, not real prices. "
    "Pass your own with --costs."
)
COST_HEAD = [
    "Rule",
    "Miss cost",
    "Check cost",
    "Cost",
    "Flag nothing",
    "Flag everything",
]
ANY_HEAD = [
    "Anomaly type",
    "Labeled",
    "Caught by any scored rule",
    "Recall (95% interval)",
]
COUNT_HEAD = ["Rule", "Labeled", "Flags", "True positives", "False positives",
              "Other label", "Misses"]  # fmt: skip

README = f"""\
ledgercheck evaluation (an analysis, {SYNTHETIC})

Files in this folder:
- evaluation.md and evaluation.html: precision, recall and F1 per rule, with intervals
- metrics.json: the same numbers, rounded to 4 places
- README.txt: this file

{FLAG_NOTE}

{DISCLAIMER}

{NOTICE}
"""


def _ci(value: tuple[float, float] | None) -> list[float] | None:
    return None if value is None else [round(value[0], 4), round(value[1], 4)]


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _rule_dict(r: RulePooled, report: EvalReport) -> dict[str, Any]:
    n = len(report.report_seeds)
    return {
        "anomaly_type": r.anomaly_type,
        "labeled": r.labeled,
        "flags": r.flags,
        "true_positives": r.tp,
        "false_positives": r.fp,
        "other_label": r.other_label,
        "misses": r.misses,
        "precision": _round(r.precision),
        "precision_ci": _ci(r.precision_ci),
        "recall": _round(r.recall),
        "recall_ci": _ci(r.recall_ci),
        "f1": _round(r.f1),
        "f1_ci": _ci(r.f1_ci),
        "miss_cost": report.costs.miss_cost[r.anomaly_type],
        "cost_per_seed": round(r.cost / n, 4),
        "cost_flag_nothing_per_seed": round(r.cost_nothing / n, 4),
        "cost_flag_everything_per_seed": round(r.cost_everything / n, 4),
    }


def _settings_dict(s: Settings) -> dict[str, float]:
    return {
        "name_threshold": s.duplicates.name_threshold,
        "invoice_threshold": s.duplicates.invoice_threshold,
        "rare_share": s.rare_share,
    }


def metrics_dict(report: EvalReport, command: str) -> dict[str, Any]:
    p = report.params
    g = report.grid
    return {
        "command": command,
        "synthetic": True,
        "label": SYNTHETIC,
        "method": METHOD.format(draws=DRAWS, seed=BOOTSTRAP_SEED),
        "params": {"size": p.size, "months": p.months},
        "planted": {
            "anomaly_rate": p.rate,
            "mean_labels_per_seed": round(report.mean_labels, 4),
        },
        "tune_seeds": list(report.tune_seeds),
        "report_seeds": list(report.report_seeds),
        "settings": {
            "defaults": _settings_dict(report.default_settings),
            "tuned": _settings_dict(report.settings),
        },
        "grid": {
            "name_thresholds": list(g.name_thresholds),
            "invoice_thresholds": list(g.invoice_thresholds),
            "rare_shares": list(g.rare_shares),
        },
        "costs": {
            "placeholder": True,
            "check_cost": report.costs.check_cost,
            "miss_cost": dict(sorted(report.costs.miss_cost.items())),
        },
        "rules": {k: _rule_dict(r, report) for k, r in report.rules.items()},
        "tuned_rules": {
            k: _rule_dict(r, report) for k, r in report.tuned_rules.items()
        },
        "any_rule": {
            kind: {
                "labeled": a.labeled,
                "caught": a.caught,
                "recall": _round(a.recall),
                "recall_ci": _ci(a.recall_ci),
            }
            for kind, a in report.any_rule.items()
        },
    }


def metrics_text(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def _count_rows(doc: dict[str, Any]) -> list[list[str]]:
    return [
        [
            label,
            str(r["labeled"]),
            str(r["flags"]),
            str(r["true_positives"]),
            str(r["false_positives"]),
            str(r["other_label"]),
            str(r["misses"]),
        ]
        for label, r in entries(doc, True)
    ]


def _f1_rows(doc: dict[str, Any]) -> list[list[str]]:
    return [
        [label, with_interval(r["f1"], r["f1_ci"])] for label, r in entries(doc, True)
    ]


def _cost_rows(doc: dict[str, Any]) -> list[list[str]]:
    check = doc["costs"]["check_cost"]
    return [
        [
            label,
            number(r["miss_cost"]),
            number(check),
            number(r["cost_per_seed"]),
            number(r["cost_flag_nothing_per_seed"]),
            number(r["cost_flag_everything_per_seed"]),
        ]
        for label, r in entries(doc, True)
    ]


def _any_rows(doc: dict[str, Any]) -> list[list[str]]:
    return [
        [
            kind,
            str(a["labeled"]),
            str(a["caught"]),
            with_interval(a["recall"], a["recall_ci"]),
        ]
        for kind, a in doc["any_rule"].items()
    ]


def _cost_lines(doc: dict[str, Any]) -> list[str]:
    costs = doc["costs"]
    miss = ", ".join(f"{k} {v}" for k, v in costs["miss_cost"].items())
    return [
        COST_NOTE,
        f"Costs used: check cost {costs['check_cost']} per flag. Miss cost by "
        f"anomaly type: {miss}.",
        "Cost is misses times the miss cost plus flags times the check cost.",
    ]


def sections(doc: dict[str, Any]) -> list[tuple[str, list[str], list[list[str]]]]:
    """Each part: a heading, text lines, then an optional table (head first)."""
    rates = [RATE_HEAD] + rate_rows(doc, True)
    return [
        ("Setup", setup_lines(doc, True), []),
        ("Precision and recall per rule (measured on synthetic data)", [], rates),
        ("F1 per rule", [], [["Rule", "F1 (95% interval)"]] + _f1_rows(doc)),
        (
            "Counts per rule",
            [
                "Flags on a unit that carries another anomaly label are counted "
                "under Other label, not as false positives. A rule with no flags "
                "has no precision (n/a)."
            ],
            [COUNT_HEAD] + _count_rows(doc),
        ),
        (
            "Recall by any scored rule",
            [
                "Caught by any scored rule means a flag from any of the nine "
                "scored rules landed on the labeled unit. entry_number_gap and "
                "benford_first_digit are not scored. Rates are at the run defaults."
            ],
            [ANY_HEAD] + _any_rows(doc),
        ),
        (
            "Cost per seed (placeholder costs, synthetic data)",
            _cost_lines(doc),
            [COST_HEAD] + _cost_rows(doc),
        ),
    ]


def markdown(doc: dict[str, Any]) -> str:
    out = ["# ledgercheck evaluation", "", NOTICE, "", DISCLAIMER, "", FLAG_NOTE, ""]
    for title, lines, table in sections(doc):
        out += [f"## {title}", ""]
        for text in lines:
            out += [text, ""]
        if table:
            out += ["| " + " | ".join(table[0]) + " |"]
            out += ["| " + " | ".join("---" for _ in table[0]) + " |"]
            out += ["| " + " | ".join(row) + " |" for row in table[1:]] + [""]
    return "\n".join(out)


def page(doc: dict[str, Any]) -> str:
    body = [
        "<h1>ledgercheck evaluation</h1>",
        f"<p>{h(NOTICE)}</p>",
        f"<p>{h(DISCLAIMER)}</p>",
        f"<p>{h(FLAG_NOTE)}</p>",
    ]
    for title, lines, table in sections(doc):
        body.append(f"<h2>{h(title)}</h2>")
        body += [f"<p>{h(text)}</p>" for text in lines]
        if table:
            body.append(html_table(table[0], table[1:]))
    style = (
        "body{font-family:sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem}"
        "table{border-collapse:collapse}"
        "td,th{border:1px solid #888;padding:.25rem .5rem}"
    )
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<title>ledgercheck evaluation</title>\n"
        f"<style>{style}</style>\n</head>\n<body>\n"
        + "\n".join(body)
        + "\n</body>\n</html>\n"
    )


def write_eval_report(out: Path, doc: dict[str, Any], force: bool = False) -> None:
    prepare(out, force, EVAL_FILES)
    write(out, "evaluation.md", markdown(doc))
    write(out, "evaluation.html", page(doc))
    write(out, "metrics.json", metrics_text(doc))
    write(out, "README.txt", README + "\n" + doc["method"] + "\n")


def _text_table(rows: list[list[str]]) -> list[str]:
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return [
        "  ".join(c.ljust(w) for c, w in zip(row, widths, strict=True)) for row in rows
    ]


def _shown(text: str) -> str:
    return plain(text)[:80]


def folder_text(
    scores: Scores, labels: int, info: dict[str, str] | None, costs: CostTable
) -> str:
    """A short table for one labeled folder."""
    head = f"Scores for one folder, {labels} labels"
    if info:
        head += f", synthbiz seed {_shown(info['seed'])}"
        head += f", size {_shown(info['size'])}, {_shown(info['months'])} months"
        head += f", planted rate {_shown(info['anomaly_rate'])}"
    rows = [COUNT_HEAD[:1] + ["P", "R", "F1"] + COUNT_HEAD[1:]]
    cost_rows = [["Rule", "Cost", "Flag nothing", "Flag everything"]]
    for rule, r in scores.rules.items():
        rows.append(_folder_row(rule, r))
        cost_rows.append(
            [rule, number(r.cost), number(r.cost_nothing), number(r.cost_everything)]
        )
    lines = [head, ""] + _text_table(rows) + ["", COST_NOTE]
    lines += [f"Check cost {costs.check_cost}. Miss costs by anomaly type:"]
    lines += [f"  {k}: {v}" for k, v in sorted(costs.miss_cost.items())]
    lines += [""] + _text_table(cost_rows)
    for kind, count in scores.unscored.items():
        lines.append(f"labels of a type no rule scores: {_shown(kind)} {count}")
    for rule, r in scores.rules.items():
        for text in r.missed_details:
            lines.append(f"missed by {rule}: {_shown(text)}")
    lines += ["", NOTICE, "", DISCLAIMER]
    return "\n".join(lines)


def _folder_row(rule: str, r: RuleScore) -> list[str]:
    return [
        rule,
        number(precision(r.tp, r.fp)),
        number(recall(r.tp, r.misses)),
        number(f1(r.tp, r.fp, r.misses)),
        str(r.labeled),
        str(r.flags),
        str(r.tp),
        str(r.fp),
        str(r.other_label),
        str(r.misses),
    ]
