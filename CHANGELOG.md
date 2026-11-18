# Changelog

All notable changes are listed here. The format follows Keep a Changelog.

## Unreleased

### Added

- Rules core: weekend_posting, holiday_posting, round_amount, rare_poster, no_approver, period_mismatch, split_under_limit and entry_number_gap, with a plain reason for every flag.
- Duplicate checks: exact keys, then fuzzy matching blocked by amount and a date window, with a work budget.
- A Benford first digit table that prints a status line (weak_sample, not_applicable or ok) before the numbers.
- The `ledgercheck run` command, which writes items_to_check.csv, analysis.md, analysis.html and README.txt.
- The evaluation harness, `ledgercheck evaluate`, which scores the rules against synthbiz labels with bootstrap intervals over seeds.
- src/ledgercheck/measured.json, the measured rates shipped with the package, and scripts/make_measured.py to rebuild and check it.
- A duplicate search benchmark, benchmarks/bench.py, and docs/benchmark.md.
- Docs: a rewritten README, docs/adr/, DATA.md, THIRD_PARTY_NOTICES.md and SECURITY.md.
- Issue templates and a pull request template.
- examples/, built from synthbiz seed 42 with scripts/make_examples.py, which also checks them byte for byte.
- scripts/reproduce_readme.py, which rebuilds the numbers block in the README and checks it in CI.
