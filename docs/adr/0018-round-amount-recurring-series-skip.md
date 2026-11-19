# 18. round_amount can skip recurring round entries

Status: Accepted

## Context

round_amount flags an entry whose debit total is a whole multiple of round_step_cents. A monthly rent accrual books the same round total every month, and so does an entry made from a monthly retainer invoice, if the books have one. These are normal and are false alarms. On synthetic data from synthbiz (large, 12 months, rate 0.1, seed 42) the rule gives 62 flags and 36 of them are false alarms. On synthetic data, report seeds 101-130, it gives 1,859 flags and 1,079 false alarms.

ADR 0016 does the same for duplicate_fuzzy, by vendor and amount. Journal lines have no vendor and no description column in the model, so this rule needs another key.

## Options

1. Skip an entry when its key repeats in at least N different calendar months. The key is the sorted list of debit account ids plus the debit total. Opt-in setting.
2. Skip any round total that repeats, with no check of the accounts or months. Two unrelated entries that share a total would hide each other.
3. Do nothing.

## Decision

Option 1. The setting is round_recurring_min_months. It is 0 by default, which turns it off, so no measured number changes. Otherwise it is at least 2. Only round entries (total above 0 and a whole multiple of the step) are counted. Months are year and month of the posting date, so March 2024 and March 2025 are two months, and three entries in one month are one month. Every entry of a series that reaches N months is skipped, including the first ones. Account ids are compared as given, with no trimming. Time is O(L log k), where L is the number of journal lines and k is the largest number of debit lines in one entry. Memory is one set of months per key. The check was added to journal_flags only, and the other rules do not read the setting.

## Consequences

Measured on synthetic data (large, 12 months, rate 0.1) with scripts/measure_round_series.py. Seed 42: at 0 the rule gives 62 flags, 26 true positives, precision 0.4194, recall 1.0000. At 2 it gives 23 flags, precision 0.9565, recall 0.8462. At 3 to 8 it gives 25 flags, precision 0.9600, recall 0.9231. At 12 it gives 36 flags, precision 0.6667, recall 0.9231. Report seeds 101-130: at 0, 1,859 flags, 780 true positives, precision 0.4196, recall 1.0000. At 2, 694 flags, precision 0.9568, recall 0.8513. At 3, 797 flags, precision 0.9624, recall 0.9833. At 4 and 6, 800 flags, precision 0.9625, recall 0.9872. At 8, 811 flags, precision 0.9494, recall 0.9872. At 12, 1,129 flags, precision 0.6820, recall 0.9872.

Recall drops. At 4 the rule hides 10 of the 780 planted round entries on seeds 101-130. They are planted entries whose account and total equal those of a background series, so they look like the rent. This is the limit of the setting: a real round entry that matches a recurring one is hidden too. At 2 the loss is larger because two coincidences are enough to make a series. At 12 a series must fill every month of the data, so the rent is missed whenever one month has no entry, and precision falls back. Use 4 or more and below the number of months in the data.

Reproduce with `python scripts/measure_round_series.py --seeds 42 --minimums 0,2,3,4,5,6,7,8,12` and `python scripts/measure_round_series.py --seeds 101-130 --minimums 0,2,3,4,6,8,12`. The default stays 0 because the README numbers block and the tuned rows are measured with it off.
