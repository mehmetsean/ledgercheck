# ledgercheck spec (v0.1, with the v0.2 plan)

## Problem
The target user is a small finance team that wants to check its own books before a close or before outside accountants start: journal entries posted on weekends, on holidays, by rare users or to the wrong period, invoices split under an approval limit, and vendor invoices paid twice. Journal entry testing is named in PCAOB AS 2401 and AICPA AU-C 240, so the tests themselves are well known. A list of flags is hard to act on without knowing how often each rule is right, and uploading client files to an outside service adds a confidentiality question.
ledgercheck runs these tests on the user's machine or in a static browser page, and every rule will ship with precision and recall measured against the labeled anomalies in synthbiz data, with confidence intervals. The scripts and seeds will be in the repo, so a reader can rerun every number.

## Buyer
- Small accounting and bookkeeping firms doing clean-up, month-end close or pre-checks for clients.
- Controllers, AP managers and internal controls teams at mid-sized companies with no analytics tool, checking their own data first. Not large firms that already own enterprise analytics tools.
- Instructors and students in accounting analytics, who can see each rule's hits and misses on synthbiz data.
- Money path: a paid commercial license per firm, paid setup (column maps and settings for one firm's exports) and paid support.

## MVP (v0.1)
Python 3.11+, standard library only at runtime, so the same wheel runs in Pyodide. CLI: `ledgercheck run data/ --out results/`, `ledgercheck evaluate data/` (one labeled folder) and `ledgercheck evaluate --size large --months 12 --tune-seeds 1-10 --seeds 101-130 --out eval/`.
Input is a synthbiz output folder in CSV. Another export is mapped to the same columns with a small JSON column map (names, date format, cents or dollars). Tables and columns read:
- journal_lines: line_id, je_id, posting_date, period, account_id, debit_cents, credit_cents, source_type, created_by, approved_by. memo is never read.
- ap_invoices: invoice_id, vendor_id, invoice_number, invoice_date, amount_cents. ap_payments: payment_id, vendor_id, invoice_id, payment_date, amount_cents. vendors: vendor_id, vendor_name.
- labels.csv (table, row_id, anomaly_type, details) and manifest.json are read only by `evaluate`. details is shown, never parsed.

| Rule | Flags | synthbiz label type | Scoring unit |
|---|---|---|---|
| weekend_posting | posting_date on Saturday or Sunday | weekend_posting | entry (je_id) |
| holiday_posting | posting_date in the holiday calendar setting | holiday_posting | entry |
| round_amount | entry debit total is a whole multiple of a step setting | round_amount_entry | entry |
| rare_poster | created_by posts under a share threshold of that source_type | unusual_user | entry |
| no_approver | approved_by is empty | missing_approval | entry |
| period_mismatch | period differs from the posting_date month | out_of_period_entry | entry |
| split_under_limit | 2 or more invoices, one vendor, within N days, each in a band just under the approval limit, together at or over it | split_invoice | invoice group |
| duplicate_exact | same invoice_id paid twice, or same vendor_id, invoice_number and amount | exact_duplicate_payment | later payment |
| duplicate_fuzzy | pairs not found by duplicate_exact: same amount within N days, similar vendor name and invoice number | near_duplicate_payment, typo_duplicate_payment | later payment |
| entry_number_gap | missing numbers in the je_id sequence | none, not scored | entry |
| benford_first_digit | first digit test on one amount field | none, not scored | field |

- Every flag is an item to check with a plain reason, for example "Posted on Saturday 2025-03-08" (synthetic data). No rule reads labels, memo or any synthbiz id or role name. The approval limit is a setting; synthetic mode uses synthbiz's 500,000 cents.
- Benford results carry a status that is printed before the numbers: weak_sample under 5,000 values, not_applicable for id-like or sequential fields (je_id, check numbers), ok otherwise. Mean absolute deviation with the first-digit cutoffs in Nigrini (2012), Benford's Law: Applications for Forensic Accounting, Auditing, and Fraud Detection, plus chi-square with a note that it rejects almost any large sample.

Evaluation harness, the core difference:
- Per rule and per anomaly type: true positives, false positives, misses, precision, recall, F1, and recall by any rule. A journal label points to the first line of an entry, so it maps to that line's je_id. Duplicates score on the later payment, which is the one synthbiz labels. A split group is a hit when it holds the labeled invoice. Flags on units labeled with another type are counted apart, not as false positives.
- Cost-weighted score: misses times a per-type miss cost plus flags times a check cost, shown next to two baselines, flag nothing and flag everything. Costs are a JSON input; the shipped defaults are placeholders and every report prints them.
- Seeds are generated in memory with synthbiz.generate. Thresholds (for example the fuzzy cutoff) are set to the lowest expected cost on the tuning seeds and reported on separate seeds. 95 percent intervals come from a percentile bootstrap over seeds (2,000 draws, fixed RNG seed), since rows inside one seed are not independent. Precision depends on the planted rate, so the report prints it.
- synthbiz 0.2.0 plants typo duplicates (typo_duplicate_payment), so duplicate_fuzzy is scored on them next to near_duplicate_payment. The README states the measured recall and the different-amount blocking limit.
- Output folder: items_to_check.csv, analysis.md, analysis.html (counts per rule, Benford table and status, measured rates labeled "measured on synthetic data") and a README.txt with the notice and disclaimer.

## Design
Constraints: runs in Pyodide, makes no network calls, rules never see labels, duplicate search must scale past all-pairs. Options for duplicates: exact keys only is O(n) but misses re-keyed vendors, which is how synthbiz plants near duplicates (new vendor_id, same invoice_number and amount); all-pairs fuzzy finds them with O(n^2) compares; chosen: block, then fuzzy compare. Blocks are by amount, not vendor_id, for that reason.
Modules: io (read, column map, input limits, typed records), dates (weekends and US federal holidays by rule, optional user list), rules, duplicates, benford, evaluate (the only module that reads labels; imports synthbiz from the optional eval extra), report (CSV, Markdown, HTML; text cells starting with =, +, - or @ are escaped), config (column map and settings files), analyze (builds the analysis result), cli. rules, duplicates and benford never import evaluate.
```python
def read_folder(path: Path, column_map: ColumnMap | None = None) -> Ledger: ...
def run_rules(ledger: Ledger, settings: Settings) -> list[Flag]: ...
def find_duplicates(ledger: Ledger, settings: DuplicateSettings) -> DuplicateResult: ...  # pairs, flags, k, compares
def benford_first_digit(values: Sequence[int], field: str) -> BenfordResult: ...
def score(flags: Sequence[Flag], labels: Sequence[Label], ledger: Ledger, costs: CostTable) -> Scores: ...
def evaluate_seeds(tune: Sequence[int], report: Sequence[int], params: EvalParams, costs: CostTable) -> EvalReport: ...
def write_report(out: Path, result: AnalysisResult) -> None: ...
```
Complexity (R journal lines, E entries, I invoices, n payments, S seeds, B draws): journal rules O(R) with hash maps; entry_number_gap O(E log E); split_under_limit O(I log I), a sort by vendor and date, then a sliding window; duplicate_exact O(n). duplicate_fuzzy sorts by (amount, date) in O(n log n), then compares each payment only with later same-amount payments inside the date window: O(n x k x c), where k is the most same-amount payments in one window and c is one Levenshtein compare on names capped at 100 characters. The worst case (one amount, one day) is O(n^2 x c); the report prints k, and a work budget, counted in Levenshtein cell steps, stops the run with a clear message. Benford O(N). Evaluation O(flags + labels) per seed, bootstrap O(B x S).
Benchmark: benchmarks/bench.py on synthbiz size large, 12 and 36 months, seed 42, writes docs/benchmark.md with time (median of several runs), pair compares, and precision and recall per duplicate type for exact-key matching, naive all-pairs fuzzy and blocked fuzzy. It asserts that blocked fuzzy finds every all-pairs match that shares an amount and falls in the window, and prints how many all-pairs matches blocking leaves out. CI runs a quick form with the assertion and no timing limits.

## Non-goals
- Not an audit, review, assurance or compilation, and no opinion on any financial statement. Flags are items to check, never findings of fraud or error.
- No bank to GL matching, classic ML, language models or Parquet input in v0.1. No ERP, bank or cloud connectors, no server, no accounts, no upload.
- No vendor master dedupe product; name matching is used only to find repeat payments.
- No recovery claims or contingency work. No copied vendor rule sets or third-party code.

## Version plan
- v0.1 is everything above. v0.2 at the earliest: bank to GL matching from matchopt, as an assignment problem (one-to-one with the Hungarian method, many-to-one as a MILP in HiGHS, amount and date tolerances) against greedy matching. Truth is bank_transactions.ref_type and ref_id, which the matcher never reads; reconciling_items lists the expected open items.
- Later, in anomaly-bench: classic ML and local-model comparisons, reusing ledgercheck's evaluate module as the harness.

## Demo plan
- Static GitHub Pages page in site/. Synthetic mode: pick seed, size and months, generate synthbiz data in the page, run ledgercheck, see each item marked hit, false alarm or miss, and precision, recall and F1 per rule. The page notes that synthbiz amounts are uniform draws, so a Benford misfit on them means nothing.
- Your files mode: choose CSV files, map columns, run. The File API reads them in the page and nothing is uploaded. Download items_to_check.csv.
- Pyodide and the ledgercheck and synthbiz wheels are served from the Pages origin, not a CDN, with a CSP of connect-src 'self', because this page may hold real client files. Check: the browser test fails on any request to another host, and the Network tab shows no request carrying file contents.
- Design tokens: the :root block of the synthbiz demo stylesheet, copied. Benford chart as hand-written inline SVG with the same numbers in a table and the status line above it. Keyboard-only use, a label on every control, status in text and not color alone, wide tables scroll in their own box. tools/browser-check/check.mjs must print RESULT: PASS at desktop and phone sizes.
- examples/: synthbiz seed 42, size small, 12 months, with its items_to_check.csv and analysis.md, marked synthetic data.

## Test plan
- Unit tests for every rule on small hand-built ledgers, including holidays observed on a Friday or Monday and multi-line entries.
- Property tests with hypothesis: shuffling rows or consistently renaming role ids and vendor ids changes no flag; blocked fuzzy equals all-pairs fuzzy on pairs inside a block; name similarity is symmetric, in [0, 1] and 1 for equal normalized names; weekend_posting equals weekday() >= 5; entry_number_gap finds exactly the numbers removed from a sequence; precision, recall and F1 stay in [0, 1], perfect flags give 1, an extra false positive never raises precision; bootstrap bounds satisfy lower <= upper and have zero width when every seed scores the same; Benford status is weak_sample for every sample under 5,000 and not_applicable for runs of consecutive integers.
- Cross-check: dates.holidays equals synthbiz.dates.holidays for 2021 to 2100 (Juneteenth is a federal holiday from 2021; synthbiz computes it for every year). Boundary tests: rules, duplicates and benford do not import evaluate; blanking memo and details changes no flag. Regression: golden items_to_check.csv for examples/ and golden metrics JSON for a fixed seed list; every fixed bug adds a case. Input limits: malformed CSV, BOM, row caps and huge fields give clear errors.
- scripts/reproduce_readme.py regenerates every number in the README. CI: ruff, mypy --strict, pytest, at least 90 percent line coverage on the core package; the browser test runs in its own job.

## License
- All rights reserved, see LICENSE. README, output README.txt, analysis files and examples carry: "All rights reserved. You may view the code and run it to evaluate it. Commercial use needs a paid license from Mehmet Tuzunkan: https://www.linkedin.com/in/mstuzunkan". CSV files keep a plain header row, so the notice sits in README.txt in the same folder as each CSV file. Package metadata: license = "LicenseRef-Proprietary", license-files = ["LICENSE"].
- Third-party parts (Pyodide, hypothesis, pytest and others) keep their own licenses, listed in THIRD_PARTY_NOTICES.md. The holiday calendar is computed by rule in code written for this repo, and so is the legal suffix list for name matching. Any outside list added later is recorded in DATA.md with its license.

## Liability notes
- Every output file except items_to_check.csv, and the demo footer, say: "Decision support only, not legal, tax, accounting or assurance advice. No guarantee of compliance, and no guarantee that all errors or duplicate payments are found. False positives and misses are expected; the measured rates are shown."
- The output is an analysis. Flags are items to check with a reason, never fraud findings or claims about a person. A rare_poster reason says the user id posts rarely, nothing more.
- Measured rates come from synthetic data and are labeled so; rates on real books will differ. Benford results always show their status. Demos, examples and tests use synthbiz synthetic data only, never real company data.
