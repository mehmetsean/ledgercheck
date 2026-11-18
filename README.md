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

- The data comes from synthbiz 0.2.0 at commit e60de623bba11135dac1794a8e883bcc9b02face, the commit pinned in pyproject.toml. It adds legitimate background rows that labels.csv does not list. The synthbiz README.txt in the data folder says the background rows are legitimate and not listed in labels.csv, and manifest.json counts them. Every flag on one of them counts as a false alarm for that rule. The precision shown is on synthetic data, not on real books.
- With synthbiz 0.1.x most rules showed a precision of 1.0, because the data had no ordinary rows for those rules to hit. That 1.0 did not show the false alarms a rule raises on ordinary entries. The lower precision here is the number to read.
- Which background rows each rule flags:
  - weekend_posting: system batch entries on weekends and the quarter-end weekend close entries made by a person.
  - holiday_posting: system batch entries on US federal holidays.
  - no_approver: system batch entries and recurring system entries, which have no approver.
  - period_mismatch: close-window accruals posted on business days 1 to 3 with the previous period.
  - round_amount: the round monthly rent accrual and the entries made from the round monthly retainer invoice.
  - rare_poster: the CFO and the tax accountant, who post rarely.
  - duplicate_fuzzy: the weekly freight invoices, whose invoice numbers are one apart.
  - duplicate_exact: none. No background row repeats a vendor, invoice number and amount, so it has no false positives and is the only rule at a precision of 1.0.
  - split_under_limit: none. No background kind targets it. Its false positives are ordinary invoices: two invoices from one vendor inside the split window, each in the band under the approval limit and together over it. The clean ledger run below shows these items. The same kind of false positive was already in the 0.1.x numbers.
- A zero-width interval means every report seed scored the same. It is not high certainty.
- rare_poster at its default rare_share and duplicate_fuzzy at its default thresholds miss some planted rows. The tuned rows use the settings picked on the tuning seeds. Both are in the numbers block.
- Typo duplicates: synthbiz plants them (typo_duplicate_payment, an invoice number with one deletion, duplication or adjacent swap). duplicate_fuzzy scores against them and near_duplicate_payment together. The numbers block shows the recall on typo duplicates at the run defaults and the recall of duplicate_fuzzy at the tuned invoice_threshold, which is higher. It flags more payments, and its precision is a little higher too, see the tuned rows.
- "Caught by any scored rule" (shown in the evaluation report) counts a labeled unit as caught when a flag from any of the nine scored rules lands on it. entry_number_gap and benford_first_digit are not scored.
- Label types that no rule scores are never an error. A folder score lists them with their counts.

A clean ledger is no longer empty. To see what the rules flag when nothing is planted (synthbiz with seed 42, size small, 12 months, rate 0 and the other defaults), run these two commands, then open /tmp/clean_ledger_out/analysis.md and read the "Items to check per rule" table.

```
synthbiz generate --anomaly-rate 0 --out /tmp/clean_ledger
ledgercheck run /tmp/clean_ledger --out /tmp/clean_ledger_out
```

That run still holds the background rows, so many rules show items. They are the rows listed above: weekend and holiday system entries, entries with no approver, close-window accruals, round rent and retainer entries, rare posters and freight invoices. split_under_limit items and one round_amount item (the opening entry) come from ordinary rows. items_to_check.csv lists every item, and the numbers block has the counts.

## Numbers

Written by scripts/reproduce_readme.py. Do not edit by hand.

<!-- numbers:start -->
### Measured rates, synthetic data

Command: `ledgercheck evaluate --size large --months 12 --tune-seeds 1-10 --seeds 101-130 --rate 0.1`. Size large, 12 months, planted rate 0.1, tuning seeds 1-10, report seeds 101-130. Run defaults: 0.05 rare_share, 0.8 name_threshold, 0.8 invoice_threshold.

| Rule | Flags | Precision | Recall |
| --- | --- | --- | --- |
| duplicate_exact | 810 | 1.0000 | 1.0000 |
| duplicate_fuzzy | 2647 | 0.5134 | 0.8547 |
| holiday_posting | 1110 | 0.7027 | 1.0000 |
| no_approver | 2190 | 0.3562 | 1.0000 |
| period_mismatch | 1440 | 0.5417 | 1.0000 |
| rare_poster | 875 | 0.8286 | 0.9295 |
| round_amount | 1859 | 0.4196 | 1.0000 |
| split_under_limit | 1800 | 0.4319 | 1.0000 |
| weekend_posting | 1260 | 0.6190 | 1.0000 |

Flags and counts are summed over the 30 report seeds. Precision is true positives over true plus false positives. True positives are counted per labeled unit and false positives per flag, so Flags can be lower than that sum when one flag covers several units. split_under_limit is the example: 1800 flags, 780 true positives plus 1026 false positives is 1806.

Tuned rows (settings picked on the tuning seeds):

| Rule | Flags | Precision | Recall |
| --- | --- | --- | --- |
| duplicate_fuzzy | 3008 | 0.5286 | 1.0000 |
| rare_poster | 875 | 0.8286 | 0.9295 |

rare_poster has recall 0.9295 at rare_share 0.05. Tuning kept rare_share 0.05, so its tuned row equals its default row.

duplicate_fuzzy at invoice_threshold 0.8 has recall 0.8547. At invoice_threshold 0.6 it has recall 1.0000.

typo_duplicate_payment: 549 of 780 labeled payments are flagged by a scored rule at the run defaults, recall 0.7038 (95 percent interval 0.6744 to 0.7321).

### Clean ledger

synthbiz with anomaly rate 0 and the default seed, then `ledgercheck run`. Items to check: 169. Rules with items:

- duplicate_fuzzy: 41
- holiday_posting: 11
- no_approver: 47
- period_mismatch: 11
- rare_poster: 5
- round_amount: 36
- split_under_limit: 2
- weekend_posting: 16

### Duplicate search benchmark

Rows are copied from docs/benchmark.md and this script does not rerun them. Times are from one machine, see that file for the machine. A test reruns the exact key and blocked methods on 12 months and checks their near duplicate counts and recall against that file. It also checks the blocked compare count.

large, 12 months, 1,387 payments:

| Method | Pair compares | Time s | Near P | Near R |
| --- | --- | --- | --- | --- |
| exact key only | 0 | 0.002 | n/a | 0.000 |
| all-pairs fuzzy | 961,191 | 14.112 | 0.430 | 0.868 |
| blocked fuzzy | 167 | 0.005 | 0.529 | 0.868 |

All-pairs matches that blocking leaves out: 244, of which 9 have a different amount.

large, 36 months, 4,439 payments:

| Method | Pair compares | Time s | Near P | Near R |
| --- | --- | --- | --- | --- |
| exact key only | 0 | 0.007 | n/a | 0.000 |
| all-pairs fuzzy | 9,850,141 | 146.359 | 0.336 | 0.842 |
| blocked fuzzy | 526 | 0.016 | 0.489 | 0.842 |

All-pairs matches that blocking leaves out: 1191, of which 91 have a different amount.

### Example folders

examples/ holds synthbiz seed 42, size small, 12 months, and the analysis of it. The synthetic data has 6 planted anomalies. The analysis lists 176 items to check:

- duplicate_exact: 1
- duplicate_fuzzy: 43
- holiday_posting: 11
- no_approver: 47
- period_mismatch: 11
- rare_poster: 5
- round_amount: 37
- split_under_limit: 4
- weekend_posting: 17
<!-- numbers:end -->

## Benchmark summary

After `pip install -e ".[eval]"`, `python benchmarks/bench.py` times exact-key matching, all-pairs fuzzy matching and the blocked fuzzy search on synthetic data (synthbiz, seed 42, size large). The benchmark tables in the numbers block show the compare counts, times and near duplicate precision and recall for 12 and 36 months. Blocked fuzzy compares far fewer pairs than all-pairs and finds the same planted near and typo duplicates on this data, at the run defaults. Exact-key matching finds none of them. Both fuzzy methods have a low precision here, partly because of legitimate weekly freight invoices with invoice numbers one apart, which synthbiz does not label. All-pairs also matches pairs with a different amount or outside the date window. This is synthetic data, not real books. The full tables and the machine details are in docs/benchmark.md. Times are from one machine and will differ on yours. Add `--quick` for a small 3 month run with one repeat.

## Limits

- Measurements on synthetic data do not predict results on real books. Rates on real books will differ.
- Blocked fuzzy duplicate search compares only payments with the same amount, so a near duplicate whose amount was changed is never found. On the 36 month benchmark all-pairs fuzzy found 91 different-amount pairs, and none of them was planted. synthbiz plants near and typo duplicates with the amount of the original payment (`_near_duplicate` and `_typo_duplicate` in src/synthbiz/anomalies.py), and tests/test_evaluate_seeds.py checks this on labels. docs/benchmark.md shows 263 near duplicate false positives for that run. They also include pairs outside the date window and legitimate background rows. The numbers block lists the pair count for both sizes. The reason for blocking is speed, see docs/adr/0004-fuzzy-duplicates-are-blocked.md.
- duplicate_fuzzy finds a typo duplicate only when the amount is the same and the invoice numbers are similar enough. At the run defaults it flags part of the planted typo duplicates, see the numbers block. A lower invoice_threshold finds more and flags more payments, see the tuned rows.
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
