# 17. duplicate_fuzzy can skip normal invoice number sequences

Status: Accepted

## Context

duplicate_fuzzy compares payments with the same amount, paid within window_days, whose vendor names and invoice numbers are alike. INV-1001 and INV-1002 are 1 edit apart, so a vendor that bills the same amount twice in a row, with counting invoice numbers, matches. These are normal invoices in a sequence. On synthetic data from synthbiz (large, 12 months, rate 0.1, seed 42) the rule gives 87 flags and 41 of them are false alarms. On synthetic data, report seeds 101-130, it gives 2,647 flags and 1,288 false alarms.

ADR 0016 skips pairs inside a recurring series by payment date. This ADR looks at the invoice numbers instead. The two settings are independent.

## Options

1. Skip a pair when the invoice numbers have the same text before their final digits and those digits differ by 1 up to N. Opt-in setting.
2. Skip any pair whose numbers differ only in the last digits. A real typo copy (INV-1001 and INV-1011 as a mistyped 1001) would be hidden at any distance.
3. Do nothing.

## Decision

Option 1. The setting is duplicates.sequence_max_step. It is 0 by default, which turns it off, so no measured number changes. Otherwise it is N, at least 1. The check runs on the normalized invoice numbers (lowercased, with punctuation and spaces removed, and cut to the first 100 characters). Each number is split into the text before its final run of digits and the value of those digits. A pair is skipped when both texts are equal and the values differ by 1 to N. Equal numbers (a difference of 0) are never skipped. A number whose final run of digits is empty, or longer than 18 digits, is never skipped. Only the ASCII digits 0 to 9 count as digits. The check is O(L) in the number length and runs only after the similarity tests pass, so the cost is small. The check is also in the reference search fuzzy_pairs_all, so both searches stay equal.

## Consequences

Measured on synthetic data (large, 12 months, rate 0.1) with scripts/measure_sequence.py. Seed 42: at 0 the rule gives 87 flags, 46 true positives, precision 0.5287, recall 0.8679. At 1 it gives 79 flags, precision 0.5823. At 2 it gives 46 flags, no false alarms, precision 1.0000, recall 0.8679. Report seeds 101-130: at 0, 2,647 flags, precision 0.5134, recall 0.8547. At 1, 2,360 flags, precision 0.5758. At 2, 1,359 flags, precision 1.0000, recall 0.8547. Values 3, 5, 10, 20, 100 and 1000 give the same result as 2. Recall does not drop at any value tried on this data. Reproduce with `python scripts/measure_sequence.py --seeds 42 --steps 0,1,2,3,5,10,20,100,1000` and `python scripts/measure_sequence.py --seeds 101-130 --steps 0,1,2,3,5,10,20,100,1000`.

The chosen value is 2, the smallest one with no false alarms here. Do not read the flat recall at large values as safe. In real books an adjacent swap such as 1012 and 1021 is 9 apart and a large N would hide it, and a vendor that skips numbers needs a larger N than 1. Keep N small. A real second payment of the next invoice number in a sequence is hidden too, which is the point of the setting but also its limit. The default stays 0 because the README numbers block and the tuned rows are measured with it off.
