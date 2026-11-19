# 16. duplicate_fuzzy can skip recurring same-amount series

Status: Accepted

## Context

duplicate_fuzzy compares payments with the same amount, paid within window_days, whose vendor names and invoice numbers are alike. A vendor that bills the same amount on a fixed cadence with counting invoice numbers (FR-00101, FR-00102) matches every time. These are false alarms. On synthbiz data (large, 12 months, rate 0.1, seed 42) the rule gives 87 flags and 41 of them are false alarms. 40 of the 41 are the weekly fixed freight invoices that synthbiz marks as background rows, and 1 is the monthly retainer. None of the 46 hits is a background row. On report seeds 101-130 the rule gives 2,647 flags and 1,288 false alarms.

Other rules also hit recurring rows. In seed 42, 12 of the 36 round_amount false alarms are the monthly rent accrual. This ADR does not cover them, see Consequences.

## Options

1. Skip a pair when both payments belong to a series of the same vendor and amount with a regular gap. Opt-in setting.
2. Skip any vendor and amount that repeats, with no check of the gap. A real copy of a payment in the series would be hidden.
3. Do nothing.

## Decision

Option 1. The setting is duplicates.recurring_min_count. It is 0 by default, which turns it off, so no measured number changes. Otherwise it is at least 2. Payments of one vendor with one amount form a series when there are at least that many. The cadence is the median gap in days between consecutive payments of the series, and a series with a cadence under 1 day is ignored. A fuzzy pair of the same vendor is skipped when its days apart is within 1 day of a whole multiple of the cadence. A copy paid a few days after its original is not on the cadence, so it is still flagged. The pass over the payments costs O(n log n) for the sort and adds O(1) to each compare. The 1 day slack covers holiday shifts and is fixed.

## Consequences

Measured on synthetic data (large, 12 months, rate 0.1) with scripts/measure_recurring.py. Seed 42: at 0 the rule gives 87 flags, 46 true positives, precision 0.5287, recall 0.8679. At 3 it gives 50 flags, 4 false alarms, precision 0.9200, recall 0.8679. Report seeds 101-130: at 0, 2,647 flags, precision 0.5134, recall 0.8547. At 3, 1,451 flags, precision 0.9366, recall 0.8547. Values from 3 up to 20 give the same result here. A value of 2 hides planted copies that sit in a two payment series and recall falls to 0.5094, so use 3 or more.

The limit is that a real duplicate that lands on the cadence of a real series is hidden. Planted copies in synthbiz do not, so recall is unchanged here, but real books may differ. The default stays 0 because the README numbers block and the tuned rows are measured with it off. The rent accrual is a monthly same-total entry for round_amount. That needs its own setting and its own test of recall, and is left for a later change.
