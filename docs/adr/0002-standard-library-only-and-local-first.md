# 2. Standard library only and local-first

Status: Accepted

## Context

The files this tool reads are a company's journal entries and payments. Sending them to a service adds a confidentiality question for the reader. The same code should also run in a browser page through Pyodide, where a package with compiled parts may not be available.

## Decision

The runtime has no dependencies, only the Python standard library (`dependencies = []` in pyproject.toml). The tool makes no network calls and has no server, accounts or upload. Files are read from a folder on the machine, and results are written to a folder on the machine. Tools that need other packages (synthbiz for data, pytest, hypothesis, ruff, mypy) are in the optional eval and dev extras and are not shipped.

Options considered:

- A hosted service. Easy to update, but client files leave the machine.
- A pandas based tool. Short code, but a large dependency and a harder fit for Pyodide.
- The standard library (chosen). Longer code for CSV reading and date rules, but one wheel runs on a laptop and in a browser.

## Consequences

CSV is the only input format. Date rules, such as US federal holidays, and string matching are written in this repo. Speed depends on algorithm choices (see ADR 4), not on compiled libraries. synthbiz is imported only inside the evaluate module.
