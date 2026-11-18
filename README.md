# ledgercheck

ledgercheck checks CSV exports of journal entries, AP invoices and AP payments for patterns worth a second look. It uses only the Python standard library and runs on your own machine. It writes a list of items to check, with a plain reason for each one. It also scores nine rules against synthbiz data, where the anomalies are labeled, so each scored rule has a measured precision and recall next to it. Every flag is an item to check, not a finding of fraud or error. The output is an analysis.

Status: version 0.1.0, not released yet.

A sample output is in examples/ledgercheck-seed42-12m/analysis.md. It is made from synthetic data.

## Who it is for

- People who review journal entries and AP payments at small and mid-size companies and want a first pass before a close or before outside accountants start.
- Analytics engineers who want rules they can read, run and test.
- Instructors who want to show what each rule catches and misses on labeled data.

## Disclaimer

Decision support only, not legal, tax, accounting or assurance advice. No guarantee of compliance, and no guarantee that all errors or duplicate payments are found. False positives and misses are expected; the measured rates are shown.

## Quickstart

These steps work from a clean clone. They need Python 3.11 or newer and git.

1. Clone the repo and enter it.

```
git clone https://github.com/mehmetsean/ledgercheck
cd ledgercheck
```

2. Make a virtual environment and install ledgercheck with the eval extra. The extra installs synthbiz, which makes the synthetic data.

```
python -m venv .venv
source .venv/bin/activate
pip install -e ".[eval]"
```

On Windows, run `.venv\Scripts\activate` instead.

3. Make synthetic data and run the rules on it.

```
synthbiz generate --seed 42 --size small --months 12 --out data
ledgercheck run data --out results
```

4. Open results/analysis.md. The items are in results/items_to_check.csv. A finished copy of this run is in examples/.

The run writes items_to_check.csv, analysis.md, analysis.html and README.txt. The analysis has a table of precision and recall per rule, read from src/ledgercheck/measured.json. Those rates are measured on synthetic data (synthbiz) and do not predict results on real books.

## Rules

| Rule | What it flags |
| --- | --- |
| weekend_posting | An entry posted on a Saturday or Sunday. |
| holiday_posting | An entry posted on a US federal holiday, or on a date you add in the settings file. |
| round_amount | An entry whose debit total is a whole multiple of a step setting. |
| rare_poster | An entry created by a user id that posts under a share threshold of that source type. It says the id posts rarely, nothing more. |
| no_approver | An entry with an empty approved_by. |
| period_mismatch | An entry whose period differs from the month of its posting date. |
| split_under_limit | Two or more invoices from one vendor, close in time, each just under the approval limit setting and together at or over it. |
| duplicate_exact | The same invoice paid twice, or the same vendor, invoice number and amount paid twice. |
| duplicate_fuzzy | Payments with the same amount inside a date window and a similar vendor name and invoice number. |
| entry_number_gap | A missing number in the journal entry id sequence. Not scored. |
| benford_first_digit | A first digit table for one amount field, printed with a status line (weak_sample, not_applicable or ok). Not scored. |

The approval limit, the round step, the windows and the thresholds are settings. Pass a JSON file with `--settings`. A JSON column map (`--column-map`) lets you read an export that does not use synthbiz column names.

## Check the numbers

Most numbers in this README are in the numbers block below. Caps, limits, the Python version, the pinned commit and the benchmark figures are checked by tests/test_readme_facts.py. Run these from the repo root after `pip install -e ".[eval]"`.

```
python scripts/reproduce_readme.py --check
python scripts/make_measured.py --check
python benchmarks/bench.py --quick
python scripts/make_examples.py --check
```

- reproduce_readme.py --check rebuilds the numbers block and exits 1 if it differs from the one below.
- make_measured.py --check reruns the evaluation and exits 1 if src/ledgercheck/measured.json differs.
- bench.py --quick runs a small 3 month duplicate search benchmark with one repeat. It exits non-zero if blocking misses a same-amount match inside the window.
- make_examples.py --check rebuilds the examples folders and compares them byte for byte.

Rebuild the shipped rates with `python scripts/make_measured.py`. The full benchmark is `python benchmarks/bench.py`.

## Evaluate

The evaluate command scores the rules against the labeled anomalies in synthbiz data. It needs the eval extra.

```
ledgercheck evaluate data/
ledgercheck evaluate --size large --months 12 --tune-seeds 1-10 --seeds 101-130 --rate 0.1 --out eval/
```

The first form scores one labeled folder. The second generates each seed in memory and reports at the run defaults on the report seeds. For the two rules that have a setting to tune (duplicate_fuzzy and rare_poster) it also picks the fuzzy thresholds and the rare_share with the lowest placeholder cost on the tuning seeds, keeps the default on a tie, and shows the tuned rows next to the default rows. It writes evaluation.md, evaluation.html, metrics.json and README.txt. Intervals are 95 percent percentile bootstrap intervals over seeds (2,000 draws, fixed RNG seed). Costs are placeholders; pass your own with --costs. Limits: 50 tuning seeds, 200 report seeds, and (tuning seeds + report seeds) times months at most 6,000.

## How to read the numbers

- Recall and precision of 1.0 for weekend_posting, holiday_posting, no_approver, period_mismatch, duplicate_exact and duplicate_fuzzy come from how synthbiz plants anomalies, not from accuracy on real books. synthbiz's clean ledger has no weekend, holiday, unapproved or odd-period entries, and its near duplicates keep the amount and the invoice number. The rules match how synthbiz plants anomalies; that is all these numbers show.
- A zero-width interval means every report seed scored the same. It is not high certainty.
- round_amount and split_under_limit show false alarms on synthbiz. The clean ledger section of the numbers block shows how many items each rule flags when nothing is planted.
- rare_poster at its default rare_share misses most planted anomalies. The tuned row uses a higher rare_share. Both recalls are in the numbers block.
- Limit: synthbiz near duplicates differ only in vendor suffix or punctuation and keep the invoice number, so measured fuzzy recall says nothing about typos. The generator is `_near_duplicate` in src/synthbiz/anomalies.py of synthbiz at commit e60de623bba11135dac1794a8e883bcc9b02face, the commit pinned in pyproject.toml.
- "Caught by any scored rule" (shown in the evaluation report) counts a labeled unit as caught when a flag from any of the nine scored rules lands on it. entry_number_gap and benford_first_digit are not scored.

To see which rules flag anything on a clean ledger (synthbiz with a planted rate of 0), run these two commands, then open /tmp/clean_ledger_out/analysis.md and read the "Items to check per rule" table.

```
synthbiz generate --anomaly-rate 0 --out /tmp/clean_ledger
ledgercheck run /tmp/clean_ledger --out /tmp/clean_ledger_out
```

## Numbers

Written by scripts/reproduce_readme.py. Do not edit by hand.

<!-- numbers:start -->
### Measured rates, synthetic data

Command: `ledgercheck evaluate --size large --months 12 --tune-seeds 1-10 --seeds 101-130 --rate 0.1`. Size large, 12 months, planted rate 0.1, tuning seeds 1-10, report seeds 101-130. Run defaults: 0.05 rare_share, 0.8 name_threshold, 0.8 invoice_threshold.

| Rule | Flags | Precision | Recall |
| --- | --- | --- | --- |
| duplicate_exact | 900 | 1.0000 | 1.0000 |
| duplicate_fuzzy | 870 | 1.0000 | 1.0000 |
| holiday_posting | 870 | 1.0000 | 1.0000 |
| no_approver | 870 | 1.0000 | 1.0000 |
| period_mismatch | 870 | 1.0000 | 1.0000 |
| rare_poster | 209 | 1.0000 | 0.2402 |
| round_amount | 900 | 0.9667 | 1.0000 |
| split_under_limit | 1686 | 0.5130 | 1.0000 |
| weekend_posting | 870 | 1.0000 | 1.0000 |

Flags and counts are summed over the 30 report seeds. Precision is true positives over true plus false positives. True positives are counted per labeled unit and false positives per flag, so Flags can be lower than that sum when one flag covers several units. split_under_limit is the example: 1686 flags, 870 true positives plus 826 false positives is 1696.

Tuned rows (settings picked on the tuning seeds):

| Rule | Flags | Precision | Recall |
| --- | --- | --- | --- |
| duplicate_fuzzy | 870 | 1.0000 | 1.0000 |
| rare_poster | 870 | 1.0000 | 1.0000 |

rare_poster at rare_share 0.05 has recall 0.2402. At rare_share 0.1 it has recall 1.0000.

### Clean ledger

synthbiz with anomaly rate 0 and the default seed, then `ledgercheck run`. Items to check: 3. Rules with items:

- round_amount: 1
- split_under_limit: 2

### Duplicate search benchmark

Rows are copied from docs/benchmark.md and this script does not rerun them. Times are from one machine, see that file for the machine. A test reruns the exact key and blocked methods on 12 months and checks their near duplicate counts and recall against that file. It also checks the blocked compare count.

large, 12 months, 1,288 payments:

| Method | Pair compares | Time s | Near P | Near R |
| --- | --- | --- | --- | --- |
| exact key only | 0 | 0.002 | n/a | 0.000 |
| all-pairs fuzzy | 828,828 | 12.562 | 0.806 | 1.000 |
| blocked fuzzy | 59 | 0.003 | 1.000 | 1.000 |

All-pairs matches that blocking leaves out: 7, of which 7 have a different amount.

large, 36 months, 4,132 payments:

| Method | Pair compares | Time s | Near P | Near R |
| --- | --- | --- | --- | --- |
| exact key only | 0 | 0.006 | n/a | 0.000 |
| all-pairs fuzzy | 8,534,646 | 126.177 | 0.524 | 1.000 |
| blocked fuzzy | 176 | 0.009 | 1.000 | 1.000 |

All-pairs matches that blocking leaves out: 87, of which 87 have a different amount.

### Example folders

examples/ holds synthbiz seed 42, size small, 12 months, and the analysis of it. The synthetic data has 6 planted anomalies. The analysis lists 9 items to check:

- duplicate_exact: 1
- duplicate_fuzzy: 1
- holiday_posting: 1
- round_amount: 2
- split_under_limit: 3
- weekend_posting: 1
<!-- numbers:end -->

## Benchmark summary

After `pip install -e ".[eval]"`, `python benchmarks/bench.py` times exact-key matching, all-pairs fuzzy matching and the blocked fuzzy search on synthetic data (synthbiz, seed 42, size large). The benchmark tables in the numbers block show the compare counts, times and near duplicate precision and recall for 12 and 36 months. Blocked fuzzy compares far fewer pairs than all-pairs and finds every planted near duplicate on this data. Exact-key matching finds none of them. All-pairs fuzzy has lower precision because it also matches pairs with a different amount. This is synthetic data, not real books, and synthbiz plants no typo near duplicates, so it says nothing about typos. The full tables and the machine details are in docs/benchmark.md. Times are from one machine and will differ on yours. Add `--quick` for a small 3 month run with one repeat.

## Limits

- Measurements on synthetic data do not predict results on real books. Rates on real books will differ.
- Blocked fuzzy duplicate search compares only payments with the same amount, so a near duplicate whose amount was changed is never found. On the 36 month benchmark all-pairs fuzzy found 87 different-amount pairs, and none of them was planted. The benchmark scores one flag per later payment, so the 87 pairs appear as 80 near duplicate false positives in docs/benchmark.md. The numbers block lists the pair count for both sizes. The reason for blocking is speed, see docs/adr/0004-fuzzy-duplicates-are-blocked.md.
- synthbiz near duplicates differ only in vendor suffix or punctuation and keep the invoice number, so measured fuzzy recall says nothing about typos.
- The holiday calendar is US federal holidays only, computed by rule. You can add dates in the settings file.
- Input is CSV only. Parquet, Excel and direct ERP or bank connections are not supported.
- Input caps: 3,000,000 rows per file, 5,000,000 rows in the folder, 500,000,000 bytes per file, 1,000,000,000 bytes in the folder, 128 characters in a field and 256 characters in a vendor name. A file over a cap is refused with a clear message.
- The fuzzy duplicate search stops with an error when its work passes max_cell_steps (400,000,000 by default), which can happen when many payments share one amount in one window.
- entry_number_gap and benford_first_digit are not scored, so they have no measured rates.
- Text is English only. Vendor name matching strips an English list of legal suffixes, and every reason is written in English.

## Demo

An in-browser demo is planned and is not live yet.

## Contributions

Outside code contributions are not accepted. Bug reports by issue are fine.

## License

All rights reserved. You may view the code and run it to evaluate it. Commercial use needs a paid license from Mehmet Tuzunkan: https://www.linkedin.com/in/mstuzunkan
