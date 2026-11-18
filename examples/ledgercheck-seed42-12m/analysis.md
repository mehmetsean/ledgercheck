# ledgercheck analysis

All rights reserved. You may view the code and run it to evaluate it. Commercial use needs a paid license from Mehmet Tuzunkan: https://www.linkedin.com/in/mstuzunkan

Decision support only, not legal, tax, accounting or assurance advice. No guarantee of compliance, and no guarantee that all errors or duplicate payments are found. False positives and misses are expected; the measured rates are shown.

Every line is an item to check. It is not a finding of fraud or error. A rare_poster line only says that a user id posts rarely.

## Input

- journal_lines: 1440 rows
- ap_invoices: 217 rows
- ap_payments: 185 rows
- vendors: 9 rows
- journal entry ids with no trailing digits, skipped by entry_number_gap: 0
- journal entry ids that share a number: 0

## Items to check per rule

| Rule | Items | Note |
| --- | --- | --- |
| weekend_posting | 17 |  |
| holiday_posting | 11 |  |
| round_amount | 37 |  |
| rare_poster | 5 |  |
| no_approver | 47 |  |
| period_mismatch | 11 |  |
| split_under_limit | 4 |  |
| duplicate_exact | 1 |  |
| duplicate_fuzzy | 43 |  |
| entry_number_gap | 0 |  |

duplicate_fuzzy search: k = 3 (most same-amount payments in one window), 89 pair compares.

## Measured on synthetic data

All rates here are measured on synthetic data (synthbiz). These rates come from generated data, so they do not predict precision or recall on real books.

Report seeds 101-130, tuning seeds 1-10, size large, 12 months.

Planted anomaly rate 0.1, about 262.0 labeled anomalies per seed. Precision depends on this rate.

Run defaults, used for the rows named after a rule: fuzzy name_threshold 0.8, invoice_threshold 0.8, rare_share 0.05.

95 percent intervals come from a percentile bootstrap over seeds: 2000 draws, fixed RNG seed 20261117, seeds resampled with replacement, pooled precision, recall and F1 recomputed from summed counts.

synthbiz plants near duplicates under a new vendor id, with the same invoice number and amount. It also plants typo duplicates, with a small change to the invoice number (one deletion, duplication or adjacent swap). duplicate_fuzzy scores both. The blocked search never finds a duplicate whose amount was changed.

A 1.0000 to 1.0000 interval means every report seed scored 1.0000 on synthetic data. It is not a guarantee for real books.

Reproduce: ledgercheck evaluate --size large --months 12 --tune-seeds 1-10 --seeds 101-130 --rate 0.1

| Rule | Anomaly type | Flags | Precision (95% interval) | Recall (95% interval) |
| --- | --- | --- | --- | --- |
| duplicate_exact | exact_duplicate_payment | 810 | 1.0000 (1.0000 to 1.0000) | 1.0000 (1.0000 to 1.0000) |
| duplicate_fuzzy | near_duplicate_payment | 2647 | 0.5134 (0.5085 to 0.5183) | 0.8547 (0.8403 to 0.8686) |
| holiday_posting | holiday_posting | 1110 | 0.7027 (0.7027 to 0.7027) | 1.0000 (1.0000 to 1.0000) |
| no_approver | missing_approval | 2190 | 0.3562 (0.3562 to 0.3562) | 1.0000 (1.0000 to 1.0000) |
| period_mismatch | out_of_period_entry | 1440 | 0.5417 (0.5417 to 0.5417) | 1.0000 (1.0000 to 1.0000) |
| rare_poster | unusual_user | 875 | 0.8286 (0.8132 to 0.8387) | 0.9295 (0.8372 to 1.0000) |
| round_amount | round_amount_entry | 1859 | 0.4196 (0.4185 to 0.4207) | 1.0000 (1.0000 to 1.0000) |
| split_under_limit | split_invoice | 1800 | 0.4319 (0.4196 to 0.4455) | 1.0000 (1.0000 to 1.0000) |
| weekend_posting | weekend_posting | 1260 | 0.6190 (0.6190 to 0.6190) | 1.0000 (1.0000 to 1.0000) |

## Benford first digit

ap_invoices.amount_cents: status weak_sample (217 non-zero values, fewer than 5000)

| Digit | Count | Share | Expected |
| --- | --- | --- | --- |
| 1 | 41 | 0.1889 | 0.3010 |
| 2 | 24 | 0.1106 | 0.1761 |
| 3 | 50 | 0.2304 | 0.1249 |
| 4 | 20 | 0.0922 | 0.0969 |
| 5 | 59 | 0.2719 | 0.0792 |
| 6 | 4 | 0.0184 | 0.0669 |
| 7 | 6 | 0.0276 | 0.0580 |
| 8 | 5 | 0.0230 | 0.0512 |
| 9 | 8 | 0.0369 | 0.0458 |

Mean absolute deviation 0.0663 (nonconformity). Chi-square 150.29 with 8 degrees of freedom, p-value 0.0000. Chi-square rejects almost any large sample, even a tiny gap from the Benford shares. Read the mean absolute deviation first.

ap_payments.amount_cents: status weak_sample (185 non-zero values, fewer than 5000)

| Digit | Count | Share | Expected |
| --- | --- | --- | --- |
| 1 | 34 | 0.1838 | 0.3010 |
| 2 | 22 | 0.1189 | 0.1761 |
| 3 | 44 | 0.2378 | 0.1249 |
| 4 | 14 | 0.0757 | 0.0969 |
| 5 | 52 | 0.2811 | 0.0792 |
| 6 | 3 | 0.0162 | 0.0669 |
| 7 | 5 | 0.0270 | 0.0580 |
| 8 | 4 | 0.0216 | 0.0512 |
| 9 | 7 | 0.0378 | 0.0458 |

Mean absolute deviation 0.0700 (nonconformity). Chi-square 140.44 with 8 degrees of freedom, p-value 0.0000. Chi-square rejects almost any large sample, even a tiny gap from the Benford shares. Read the mean absolute deviation first.

journal_lines.debit_cents: status weak_sample (720 non-zero values, fewer than 5000)

| Digit | Count | Share | Expected |
| --- | --- | --- | --- |
| 1 | 202 | 0.2806 | 0.3010 |
| 2 | 162 | 0.2250 | 0.1761 |
| 3 | 115 | 0.1597 | 0.1249 |
| 4 | 43 | 0.0597 | 0.0969 |
| 5 | 121 | 0.1681 | 0.0792 |
| 6 | 15 | 0.0208 | 0.0669 |
| 7 | 27 | 0.0375 | 0.0580 |
| 8 | 18 | 0.0250 | 0.0512 |
| 9 | 17 | 0.0236 | 0.0458 |

Mean absolute deviation 0.0383 (nonconformity). Chi-square 145.28 with 8 degrees of freedom, p-value 0.0000. Chi-square rejects almost any large sample, even a tiny gap from the Benford shares. Read the mean absolute deviation first.

The items are listed in items_to_check.csv.
