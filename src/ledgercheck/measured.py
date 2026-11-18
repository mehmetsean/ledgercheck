"""Measured rates shipped with the package, and the text that shows them."""

import json
from importlib import resources
from typing import Any

SYNTHETIC = "measured on synthetic data (synthbiz)"
FUZZY_LIMIT = (
    "synthbiz near duplicates differ only in vendor suffix or punctuation and "
    "keep the invoice number, so measured fuzzy recall says nothing about typos."
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


def rate_rows(doc: dict[str, Any]) -> list[list[str]]:
    rows = []
    for rule, r in doc["rules"].items():
        rows.append(
            [
                rule,
                r["anomaly_type"],
                str(r["flags"]),
                with_interval(r["precision"], r["precision_ci"]),
                with_interval(r["recall"], r["recall_ci"]),
            ]
        )
    return rows


def setup_lines(doc: dict[str, Any]) -> list[str]:
    p, s, planted = doc["params"], doc["settings"], doc["planted"]
    return [
        f"All rates here are {SYNTHETIC}. Rates on real books will differ.",
        f"Report seeds {seed_text(doc['report_seeds'])}, tuning seeds "
        f"{seed_text(doc['tune_seeds'])}, size {p['size']}, {p['months']} months.",
        f"Planted anomaly rate {planted['anomaly_rate']}, about "
        f"{planted['mean_labels_per_seed']} labeled anomalies per seed. "
        "Precision depends on this rate.",
        f"Settings chosen on the tuning seeds: fuzzy name_threshold "
        f"{s['name_threshold']}, invoice_threshold {s['invoice_threshold']}, "
        f"rare_share {s['rare_share']}. A run with other settings gives other rates.",
        doc["method"],
        FUZZY_LIMIT,
        f"Reproduce: {doc['command']}",
    ]
