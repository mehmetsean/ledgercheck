# 11. Measure on data with background rows

Status: Accepted

## Context

With synthbiz 0.1.x the clean ledger had no weekend, holiday, unapproved, round or odd-period entries. A rule that flags those could only hit planted rows, so its precision was 1.0 and said nothing about the rule. synthbiz 0.2.0 adds legitimate unlabeled background rows by default and a new labeled type, typo_duplicate_payment.

## Decision

ledgercheck pins synthbiz 0.2.0 and measures with the background rows on. Flags that land on a background row count as false positives, because the labels do not point to it. A rule may map to more than one label type, so duplicate_fuzzy scores against near_duplicate_payment and typo_duplicate_payment. Label types that no rule scores are counted and listed, not dropped and not fatal. No new setting or allowlist is added in this change.

## Consequences

Precision now shows false alarms on legitimate synthetic rows. The numbers are on synthetic data and do not predict real books. PRECISION_NOTE

The cost of a miss for typo_duplicate_payment is a placeholder equal to near_duplicate_payment. The approval limit stays a fixed setting of 500,000 cents, the same value synthbiz writes to manifest.json.
