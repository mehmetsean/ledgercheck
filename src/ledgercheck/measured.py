"""Measured rates shipped with the package, and the text that shows them."""

import json
from importlib import resources
from typing import Any

SYNTHETIC = "measured on synthetic data (synthbiz)"
FUZZY_LIMIT = (
    "synthbiz plants near duplicates under a new vendor id, with the same invoice "
    "number and amount. It also plants typo duplicates, with a small change to "
    "the invoice number (one deletion, duplication or adjacent swap). "
    "duplicate_fuzzy scores both. The blocked search never finds a duplicate "
    "whose amount was changed."
)
METHOD = (
    "95 percent intervals come from a percentile bootstrap over seeds: "
    "{draws} draws, fixed RNG seed {seed}, seeds resampled with replacement, "
    "pooled precision, recall and F1 recomputed from summed counts."
)
RATE_HEAD = [
    "Rule",
    "Anomaly type",
    "Flags",
    "Precision (95% interval)",
    "Recall (95% interval)",
]


def number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def with_interval(value: float | None, ci: list[float] | None) -> str:
    if value is None:
        return "n/a"
    if ci is None:
        return number(value)
    return f"{number(value)} ({number(ci[0])} to {number(ci[1])})"


def seed_text(seeds: list[int]) -> str:
    """Seeds as ranges, for example 1-10, 15."""
    parts: list[str] = []
    start = prev = seeds[0]
    for s in seeds[1:] + [-2]:
        if s == prev + 1:
            prev = s
            continue
        parts.append(str(start) if start == prev else f"{start}-{prev}")
        start = prev = s
    return ", ".join(parts)


def load_measured() -> dict[str, Any] | None:
    try:
        text = (
            resources.files("ledgercheck").joinpath("measured.json").read_text("utf-8")
        )
        data = json.loads(text)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


Entry = tuple[str, dict[str, Any]]


def entries(doc: dict[str, Any], tuned: bool) -> list[Entry]:
    """Rows per rule at the run defaults. With tuned, two rows per tuned rule."""
    seeds = seed_text(doc["tune_seeds"])
    out: list[Entry] = []
    for rule, r in doc["rules"].items():
        if tuned and rule in doc["tuned_rules"]:
            out.append((f"{rule} (defaults)", r))
            out.append((f"{rule} (tuned on seeds {seeds})", doc["tuned_rules"][rule]))
        else:
            out.append((rule, r))
    return out


def rate_rows(doc: dict[str, Any], tuned: bool = False) -> list[list[str]]:
    return [
        [
            label,
            r["anomaly_type"],
            str(r["flags"]),
            with_interval(r["precision"], r["precision_ci"]),
            with_interval(r["recall"], r["recall_ci"]),
        ]
        for label, r in entries(doc, tuned)
    ]


def _settings_text(s: dict[str, Any]) -> str:
    return (
        f"fuzzy name_threshold {s['name_threshold']}, "
        f"invoice_threshold {s['invoice_threshold']}, rare_share {s['rare_share']}"
    )


def setup_lines(doc: dict[str, Any], tuned: bool = False) -> list[str]:
    p, planted = doc["params"], doc["planted"]
    out = [
        f"All rates here are {SYNTHETIC}. These rates come from generated data, "
        "so they do not predict precision or recall on real books.",
        f"Report seeds {seed_text(doc['report_seeds'])}, tuning seeds "
        f"{seed_text(doc['tune_seeds'])}, size {p['size']}, {p['months']} months.",
        f"Planted anomaly rate {planted['anomaly_rate']}, about "
        f"{planted['mean_labels_per_seed']} labeled anomalies per seed. "
        "Precision depends on this rate.",
        f"Run defaults, used for the rows named after a rule: "
        f"{_settings_text(doc['settings']['defaults'])}.",
    ]
    if tuned:
        out.append(
            f"Tuned on seeds {seed_text(doc['tune_seeds'])}: "
            f"{_settings_text(doc['settings']['tuned'])}. The default is kept "
            "unless another value has a strictly lower placeholder cost."
        )
    out += [
        doc["method"],
        FUZZY_LIMIT,
        "A 1.0000 to 1.0000 interval means every report seed scored 1.0000 on "
        "synthetic data. It is not a guarantee for real books.",
        f"Reproduce: {doc['command']}",
    ]
    return out
