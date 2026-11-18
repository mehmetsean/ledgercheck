# Changelog

All notable changes are listed here. The format follows Keep a Changelog.

## Unreleased

### Changed

- Moved the synthbiz pin to 0.2.0 (commit e60de623bba11135dac1794a8e883bcc9b02face), which adds legitimate unlabeled background rows.
- Re-measured the rates in src/ledgercheck/measured.json, the benchmark in docs/benchmark.md, the examples and the README numbers. Precision now shows false alarms on the background rows.
- Rewrote the README sections on how to read the numbers, the typo limit and the clean ledger.

### Added

- Scoring of typo_duplicate_payment. duplicate_fuzzy now scores against near_duplicate_payment and typo_duplicate_payment.
- The evaluation lists label types that no rule scores, and never fails on them.
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
