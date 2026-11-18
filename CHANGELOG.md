# Changelog

All notable changes are listed here. The format follows Keep a Changelog.

## Unreleased

### Changed

- Moved the synthbiz pin to 0.2.0 (commit e60de623bba11135dac1794a8e883bcc9b02face), which adds legitimate unlabeled background rows.
- Re-measured the rates in src/ledgercheck/measured.json, the benchmark in docs/benchmark.md, the examples and the README numbers. Precision now shows false alarms on the background rows.
- Precision and recall per rule at the run defaults, old to new (precision, recall): duplicate_exact 1.0000 to 1.0000, 1.0000 to 1.0000; duplicate_fuzzy 1.0000 to 0.5134, 1.0000 to 0.8547; holiday_posting 1.0000 to 0.7027, 1.0000 to 1.0000; no_approver 1.0000 to 0.3562, 1.0000 to 1.0000; period_mismatch 1.0000 to 0.5417, 1.0000 to 1.0000; rare_poster 1.0000 to 0.8286, 0.2402 to 0.9295; round_amount 0.9667 to 0.4196, 1.0000 to 1.0000; split_under_limit 0.5130 to 0.4319, 1.0000 to 1.0000; weekend_posting 1.0000 to 0.6190, 1.0000 to 1.0000.
- rare_poster recall rose because the background rows add manual entries, which lowers the share of the planted users. CFO_1 and TAX_ACCOUNTANT_1 are the new false alarms.
- The metrics file lists miss_costs per label type for each rule, and unscored_label_types.
- Rewrote the README sections on how to read the numbers, the typo limit and the clean ledger.

### Added

- The in-browser demo in site/, built by scripts/build_site.py. It runs synthetic data and your own CSV files in the page with Pyodide served from the Pages origin, and downloads items_to_check.csv. A browser test in CI fails on any request to another host. See docs/adr/0012-demo-unpacks-wheels-and-fetches-pyodide-at-build-time.md.
- ledgercheck.demo, the entry points the page calls.
- The Pages workflow, and a browser job that the aggregate ci job needs.
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
