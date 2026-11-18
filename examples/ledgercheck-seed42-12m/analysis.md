# ledgercheck analysis

All rights reserved. You may view the code and run it to evaluate it. Commercial use needs a paid license from Mehmet Tuzunkan: https://www.linkedin.com/in/mstuzunkan

Decision support only, not legal, tax, accounting or assurance advice. No guarantee of compliance, and no guarantee that all errors or duplicate payments are found. False positives and misses are expected; the measured rates are shown.

Every line is an item to check. It is not a finding of fraud or error. A rare_poster line only says that a user id posts rarely.

## Input

- journal_lines: 1030 rows
- ap_invoices: 149 rows
- ap_payments: 126 rows
- vendors: 9 rows
- journal entry ids with no trailing digits, skipped by entry_number_gap: 0
- journal entry ids that share a number: 0

## Items to check per rule

| Rule | Items | Note |
| --- | --- | --- |
| weekend_posting | 1 |  |
| holiday_posting | 1 |  |
| round_amount | 2 |  |
| rare_poster | 0 |  |
| no_approver | 0 |  |
| period_mismatch | 0 |  |
| split_under_limit | 3 |  |
| duplicate_exact | 1 |  |
| duplicate_fuzzy | 1 |  |
| entry_number_gap | 0 |  |

duplicate_fuzzy search: k = 2 (most same-amount payments in one window), 2 pair compares.

## Measured on synthetic data

All rates here are measured on synthetic data (synthbiz). These rates come from generated data, so they do not predict precision or recall on real books.

Report seeds 101-130, tuning seeds 1-10, size large, 12 months.

Planted anomaly rate 0.1, about 262.0 labeled anomalies per seed. Precision depends on this rate.

Run defaults, used for the rows named after a rule: fuzzy name_threshold 0.8, invoice_threshold 0.8, rare_share 0.05.

95 percent intervals come from a percentile bootstrap over seeds: 2000 draws, fixed RNG seed 20261117, seeds resampled with replacement, pooled precision, recall and F1 recomputed from summed counts.

synthbiz near duplicates differ only in vendor suffix or punctuation and keep the invoice number, so measured fuzzy recall says nothing about typos.

A 1.0000 to 1.0000 interval means every report seed scored 1.0000 on synthetic data. It is not a guarantee for real books.

Reproduce: ledgercheck evaluate --size large --months 12 --tune-seeds 1-10 --seeds 101-130 --rate 0.1

| Rule | Anomaly type | Flags | Precision (95% interval) | Recall (95% interval) |
| --- | --- | --- | --- | --- |
| duplicate_exact | exact_duplicate_payment | 900 | 1.0000 (1.0000 to 1.0000) | 1.0000 (1.0000 to 1.0000) |
| duplicate_fuzzy | near_duplicate_payment | 870 | 1.0000 (1.0000 to 1.0000) | 1.0000 (1.0000 to 1.0000) |
| holiday_posting | holiday_posting | 870 | 1.0000 (1.0000 to 1.0000) | 1.0000 (1.0000 to 1.0000) |
| no_approver | missing_approval | 870 | 1.0000 (1.0000 to 1.0000) | 1.0000 (1.0000 to 1.0000) |
| period_mismatch | out_of_period_entry | 870 | 1.0000 (1.0000 to 1.0000) | 1.0000 (1.0000 to 1.0000) |
| rare_poster | unusual_user | 209 | 1.0000 (1.0000 to 1.0000) | 0.2402 (0.1724 to 0.3080) |
| round_amount | round_amount_entry | 900 | 0.9667 (0.9667 to 0.9667) | 1.0000 (1.0000 to 1.0000) |
| split_under_limit | split_invoice | 1686 | 0.5130 (0.4980 to 0.5295) | 1.0000 (1.0000 to 1.0000) |
| weekend_posting | weekend_posting | 870 | 1.0000 (1.0000 to 1.0000) | 1.0000 (1.0000 to 1.0000) |

## Benford first digit

ap_invoices.amount_cents: status weak_sample (149 non-zero values, fewer than 5000)

| Digit | Count | Share | Expected |
| --- | --- | --- | --- |
| 1 | 41 | 0.2752 | 0.3010 |
| 2 | 24 | 0.1611 | 0.1761 |
| 3 | 36 | 0.2416 | 0.1249 |
| 4 | 19 | 0.1275 | 0.0969 |
| 5 | 6 | 0.0403 | 0.0792 |
| 6 | 4 | 0.0268 | 0.0669 |
| 7 | 6 | 0.0403 | 0.0580 |
| 8 | 5 | 0.0336 | 0.0512 |
| 9 | 8 | 0.0537 | 0.0458 |

Mean absolute deviation 0.0345 (nonconformity). Chi-square 26.54 with 8 degrees of freedom, p-value 0.0008. Chi-square rejects almost any large sample, even a tiny gap from the Benford shares. Read the mean absolute deviation first.

ap_payments.amount_cents: status weak_sample (126 non-zero values, fewer than 5000)

| Digit | Count | Share | Expected |
| --- | --- | --- | --- |
| 1 | 34 | 0.2698 | 0.3010 |
| 2 | 22 | 0.1746 | 0.1761 |
| 3 | 31 | 0.2460 | 0.1249 |
| 4 | 14 | 0.1111 | 0.0969 |
| 5 | 6 | 0.0476 | 0.0792 |
| 6 | 3 | 0.0238 | 0.0669 |
| 7 | 5 | 0.0397 | 0.0580 |
| 8 | 4 | 0.0317 | 0.0512 |
| 9 | 7 | 0.0556 | 0.0458 |

Mean absolute deviation 0.0322 (nonconformity). Chi-square 22.47 with 8 degrees of freedom, p-value 0.0041. Chi-square rejects almost any large sample, even a tiny gap from the Benford shares. Read the mean absolute deviation first.

journal_lines.debit_cents: status weak_sample (515 non-zero values, fewer than 5000)

| Digit | Count | Share | Expected |
| --- | --- | --- | --- |
| 1 | 172 | 0.3340 | 0.3010 |
| 2 | 133 | 0.2583 | 0.1761 |
| 3 | 82 | 0.1592 | 0.1249 |
| 4 | 39 | 0.0757 | 0.0969 |
| 5 | 21 | 0.0408 | 0.0792 |
| 6 | 13 | 0.0252 | 0.0669 |
| 7 | 23 | 0.0447 | 0.0580 |
| 8 | 17 | 0.0330 | 0.0512 |
| 9 | 15 | 0.0291 | 0.0458 |

Mean absolute deviation 0.0332 (nonconformity). Chi-square 59.81 with 8 degrees of freedom, p-value 0.0000. Chi-square rejects almost any large sample, even a tiny gap from the Benford shares. Read the mean absolute deviation first.

The items are listed in items_to_check.csv.
