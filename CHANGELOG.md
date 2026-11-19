# Changelog

All notable changes are listed here. The format follows Keep a Changelog.

## Unreleased

### Added

- The close_window_days setting: an entry posted this many days into a month or earlier, with the previous month as its period, is not flagged by period_mismatch. The default is 0, so no measured number changes. See docs/adr/0015-close-window-days.md.
- scripts/measure_close_window.py, which scores period_mismatch for several windows.
- The rare_skip_users setting: user ids that rare_poster never flags. The default is empty, so no measured number changes. See docs/adr/0014-rare-poster-skip-list.md.
- scripts/measure_skip_users.py, which scores rare_poster with and without the system user skip list.

## 0.1.0 - 2026-11-18

First release.

### Added

- The in-browser demo in site/, built by scripts/build_site.py. It runs synthetic data and your own CSV files in the page with Pyodide served from the Pages origin, and downloads items_to_check.csv. A browser test in CI fails on any request to another host. See docs/adr/0012-demo-unpacks-wheels-and-fetches-pyodide-at-build-time.md.
- ledgercheck.demo, the entry points the page calls.
- The Pages workflow, and a browser test job in CI that the ci job waits for.
- Scoring of typo_duplicate_payment. duplicate_fuzzy now scores against near_duplicate_payment and typo_duplicate_payment.
- The evaluation lists label types that no rule scores, and never fails on them.
- Rules core: weekend_posting, holiday_posting, round_amount, rare_poster, no_approver, period_mismatch, split_under_limit and entry_number_gap, with a plain reason for every flag.
- Duplicate checks: exact keys, then fuzzy matching blocked by amount and a date window, with a work budget.
- A Benford first digit table that prints a status line (weak_sample, not_applicable or ok) before the numbers.
- The `ledgercheck run` command, which writes items_to_check.csv, analysis.md, analysis.html and README.txt.
- The evaluation harness, `ledgercheck evaluate`, which scores the rules against synthbiz labels with bootstrap intervals over seeds.
- src/ledgercheck/measured.json, the measured rates shipped with the package, and scripts/make_measured.py to rebuild and check it. The rates, the benchmark in docs/benchmark.md and the examples were made on synthbiz 0.2.0 (tag v0.2.0, commit e60de623bba11135dac1794a8e883bcc9b02face). That data has unlabeled background rows, so precision shows false alarms.
- A duplicate search benchmark, benchmarks/bench.py, and docs/benchmark.md.
- Docs: a rewritten README, docs/adr/, DATA.md, THIRD_PARTY_NOTICES.md and SECURITY.md.
- Issue templates and a pull request template.
- examples/, built from synthbiz seed 42 with scripts/make_examples.py, which also checks them byte for byte.
- scripts/reproduce_readme.py, which rebuilds the numbers block in the README and checks it in CI.
- The metrics file lists miss_costs per label type for each rule, and unscored_label_types.
