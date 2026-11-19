# Changelog

All notable changes are listed here. The format follows Keep a Changelog.

## Unreleased

### Added

- The round_recurring_min_months setting: round entries with the same debit accounts and total in at least that many different months, such as the monthly rent accrual, are not flagged by round_amount. The default is 0 (off), so no measured number changes. On synthetic data (large, 12 months, rate 0.1, seeds 101-130), round_amount precision goes from 0.4196 to 0.9625 at 4 and recall goes from 1.0000 to 0.9872. See docs/adr/0018-round-amount-recurring-series-skip.md.
- scripts/measure_round_series.py, which scores round_amount for several series minimums.
- The duplicates.sequence_max_step setting: fuzzy pairs whose invoice numbers have the same text before their final digits and differ by 1 up to that value (INV-1001 and INV-1002) are not flagged. The default is 0 (off), so no measured number changes. On synthetic data (large, 12 months, rate 0.1, seeds 101-130), duplicate_fuzzy precision goes from 0.5134 to 1.0000 at 2 and recall stays 0.8547. See docs/adr/0017-sequential-invoice-number-guard.md.
- scripts/measure_sequence.py, which scores duplicate_fuzzy for several sequence steps.
- The duplicates.recurring_min_count setting: fuzzy pairs inside a regular same-vendor, same-amount series of at least that many payments are not flagged. The default is 0 (off), so no measured number changes. On synthetic data (large, 12 months, rate 0.1, seeds 101-130), duplicate_fuzzy precision goes from 0.5134 to 0.9366 at 3 and recall stays 0.8547. See docs/adr/0016-recurring-series-skip-for-fuzzy-duplicates.md.
- scripts/measure_recurring.py, which scores duplicate_fuzzy for several series minimums.
- The close_window_days setting: an entry posted on day N of the month or earlier, where N is close_window_days, with the previous month as its period, is not flagged by period_mismatch. The default is 0, so no measured number changes. See docs/adr/0015-close-window-days.md.
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
