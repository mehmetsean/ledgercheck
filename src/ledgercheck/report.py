"""Write the four output files."""

import csv
import html
import io
import os
from collections.abc import Sequence
from pathlib import Path

from .analyze import AnalysisResult
from .benford import BenfordResult
from .measured import RATE_HEAD, load_measured, rate_rows, setup_lines
from .rules import RULES

NOTICE = (
    "All rights reserved. You may view the code and run it to evaluate it. "
    "Commercial use needs a paid license from Mehmet Tuzunkan: "
    "https://www.linkedin.com/in/mstuzunkan"
)
DISCLAIMER = (
    "Decision support only, not legal, tax, accounting or assurance advice. "
    "No guarantee of compliance, and no guarantee that all errors or duplicate "
    "payments are found. False positives and misses are expected; the measured "
    "rates are shown."
)
FLAG_NOTE = (
    "Every line is an item to check. It is not a finding of fraud or error. "
    "A rare_poster line only says that a user id posts rarely."
)
FILES = ("items_to_check.csv", "analysis.md", "analysis.html", "README.txt")
CSV_HEADER = ["rule", "table", "unit_id", "row_ids", "reason"]
RISKY_START = ("=", "+", "-", "@", "\t", "\r", "\n")

README = f"""\
ledgercheck output (an analysis)

Files in this folder:
- items_to_check.csv: one row per item to check, with the rule and the reason
- analysis.md and analysis.html: counts per rule, skipped rules, Benford table
- README.txt: this file

{FLAG_NOTE}

{DISCLAIMER}

{NOTICE}
"""


def safe_cell(text: str) -> str:
    """Neutralize spreadsheet formulas and show control characters as text."""
    risky = text.lstrip(" ").startswith(RISKY_START)
    clean = "".join(
        f"\\x{ord(c):02x}" if ord(c) < 0x20 or ord(c) == 0x7F else c for c in text
    )
    return "'" + clean if risky else clean


def csv_text(result: AnalysisResult) -> str:
    rows = [
        [f.rule, f.table, f.unit_id, " ".join(f.row_ids), f.reason]
        for f in result.flags
    ]
    return _to_csv([CSV_HEADER] + rows)


def _to_csv(rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(rows[0])
    for row in rows[1:]:
        writer.writerow([safe_cell(c) for c in row])
    return buffer.getvalue()


def _rule_rows(result: AnalysisResult) -> list[tuple[str, str, str]]:
    rows = []
    for rule in RULES:
        if rule == "benford_first_digit":
            continue
        if rule in result.skips:
            rows.append((rule, "SKIP", result.skips[rule]))
        else:
            rows.append((rule, str(result.counts[rule]), ""))
    return rows


def _input_lines(result: AnalysisResult) -> list[str]:
    out = []
    for table, count in result.table_rows.items():
        text = "not in the input" if count is None else f"{count} rows"
        out.append(f"{table}: {text}")
    if result.table_rows.get("journal_lines") is not None:
        out.append(
            "journal entry ids with no trailing digits, skipped by "
            f"entry_number_gap: {result.unnumbered_ids}"
        )
        out.append(f"journal entry ids that share a number: {result.shared_numbers}")
    return out


def _digit_rows(b: BenfordResult) -> list[tuple[str, str, str, str]]:
    rows = []
    for i in range(9):
        share = b.counts[i] / b.n if b.n else 0.0
        rows.append(
            (
                str(i + 1),
                str(b.counts[i]),
                f"{share:.4f}",
                f"{b.expected_shares[i]:.4f}",
            )
        )
    return rows


def benford_head(b: BenfordResult) -> str:
    return f"{b.field}: status {b.status} ({b.reason})"


def _benford_tail(b: BenfordResult) -> str:
    return (
        f"Mean absolute deviation {b.mad:.4f} ({b.mad_label}). "
        f"Chi-square {b.chi_square:.2f} with 8 degrees of freedom, "
        f"p-value {b.p_value:.4f}. {b.note}"
    )


def _dup_line(result: AnalysisResult) -> str:
    return (
        f"duplicate_fuzzy search: k = {result.dup_k} (most same-amount payments "
        f"in one window), {result.dup_compares} pair compares."
    )


def _measured_markdown() -> list[str]:
    doc = load_measured()
    out = ["## Measured on synthetic data", ""]
    if doc is None:
        return out + ["No measured rates are shipped with this copy.", ""]
    for text in setup_lines(doc):
        out += [text, ""]
    out += ["| " + " | ".join(RATE_HEAD) + " |"]
    out += ["| " + " | ".join("---" for _ in RATE_HEAD) + " |"]
    out += ["| " + " | ".join(row) + " |" for row in rate_rows(doc)]
    return out + [""]


def _measured_html() -> list[str]:
    doc = load_measured()
    out = ["<h2>Measured on synthetic data</h2>"]
    if doc is None:
        return out + ["<p>No measured rates are shipped with this copy.</p>"]
    out += [f"<p>{h(text)}</p>" for text in setup_lines(doc)]
    return out + [html_table(RATE_HEAD, rate_rows(doc))]


def markdown(result: AnalysisResult) -> str:
    out = ["# ledgercheck analysis", "", NOTICE, "", DISCLAIMER, "", FLAG_NOTE, ""]
    out += ["## Input", ""] + [f"- {line}" for line in _input_lines(result)] + [""]
    out += [
        "## Items to check per rule",
        "",
        "| Rule | Items | Note |",
        "| --- | --- | --- |",
    ]
    out += [f"| {r} | {n} | {note} |" for r, n, note in _rule_rows(result)]
    out += ["", _dup_line(result), ""] + _measured_markdown()
    out += ["## Benford first digit", ""]
    if not result.benford:
        out += ["SKIP: no amount field in the input.", ""]
    for b in result.benford:
        out += [benford_head(b), ""]
        out += ["| Digit | Count | Share | Expected |", "| --- | --- | --- | --- |"]
        out += [f"| {a} | {c} | {s} | {e} |" for a, c, s, e in _digit_rows(b)]
        out += ["", _benford_tail(b), ""]
    out += ["The items are listed in items_to_check.csv.", ""]
    return "\n".join(out)


def h(text: str) -> str:
    return html.escape(text, quote=True)


def html_table(head: list[str], rows: Sequence[Sequence[str]]) -> str:
    out = ["<table>", "<tr>" + "".join(f"<th>{h(c)}</th>" for c in head) + "</tr>"]
    for row in rows:
        out.append("<tr>" + "".join(f"<td>{h(c)}</td>" for c in row) + "</tr>")
    out.append("</table>")
    return "\n".join(out)


def page(result: AnalysisResult) -> str:
    body = [
        "<h1>ledgercheck analysis</h1>",
        f"<p>{h(NOTICE)}</p>",
        f"<p>{h(DISCLAIMER)}</p>",
        f"<p>{h(FLAG_NOTE)}</p>",
        "<h2>Input</h2>",
        "<ul>" + "".join(f"<li>{h(x)}</li>" for x in _input_lines(result)) + "</ul>",
        "<h2>Items to check per rule</h2>",
        html_table(["Rule", "Items", "Note"], _rule_rows(result)),
        f"<p>{h(_dup_line(result))}</p>",
        *_measured_html(),
        "<h2>Benford first digit</h2>",
    ]
    if not result.benford:
        body.append("<p>SKIP: no amount field in the input.</p>")
    for b in result.benford:
        body.append(f"<p>{h(benford_head(b))}</p>")
        body.append(html_table(["Digit", "Count", "Share", "Expected"], _digit_rows(b)))
        body.append(f"<p>{h(_benford_tail(b))}</p>")
    body.append("<p>The items are listed in items_to_check.csv.</p>")
    style = (
        "body{font-family:sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem}"
    )
    style += "table{border-collapse:collapse}"
    style += "td,th{border:1px solid #888;padding:.25rem .5rem}"
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<title>ledgercheck analysis</title>\n"
        f"<style>{style}</style>\n</head>\n<body>\n"
        + "\n".join(body)
        + "\n</body>\n</html>\n"
    )


def check_existing(out: Path, force: bool, names: tuple[str, ...] = FILES) -> None:
    if out.exists() and not out.is_dir():
        raise ValueError(f"{ascii(str(out))} is a file, not a folder")
    found = sorted(p.name for p in out.iterdir()) if out.is_dir() else []
    if not found:
        return
    if not force:
        raise ValueError(
            f"{ascii(str(out))} is not empty, use --force to replace the output files"
        )
    other = [n for n in found if n not in names]
    if other:
        raise ValueError(
            f"{ascii(str(out))} holds files that are not ledgercheck output, "
            f"first one {ascii(other[0][:40])}. Use an empty folder"
        )


def check_out_folder(out: Path, data: Path, force: bool = False) -> None:
    """Refuse a bad output folder before any data is read."""
    out_path, data_path = out.resolve(), data.resolve()
    if out_path == data_path or data_path in out_path.parents:
        raise ValueError(
            f"{ascii(str(out))}: output folder must not be inside the data"
        )
    check_existing(out, force)


def prepare(out: Path, force: bool, names: tuple[str, ...] = FILES) -> None:
    check_existing(out, force, names)
    out.mkdir(parents=True, exist_ok=True)


def write(out: Path, name: str, text: str) -> None:
    temp = out / f".{name}.tmp"
    try:
        with temp.open("w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(temp, out / name)
    finally:
        if temp.exists():
            temp.unlink()


def write_report(out: Path, result: AnalysisResult, force: bool = False) -> None:
    prepare(out, force)
    write(out, "items_to_check.csv", csv_text(result))
    write(out, "analysis.md", markdown(result))
    write(out, "analysis.html", page(result))
    write(out, "README.txt", README)
