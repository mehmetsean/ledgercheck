# 11. Measure on data with background rows

Status: Accepted. The approval limit part is superseded by ADR 0013.

## Context

With synthbiz 0.1.x the clean ledger had no weekend, holiday, unapproved or odd-period entries. The weekend, holiday, no_approver, period_mismatch and duplicate rules could only hit planted rows, so their precision was 1.0 and said nothing about them. round_amount (0.9667) and split_under_limit (0.5130) already had false alarms. synthbiz 0.2.0 adds legitimate unlabeled background rows by default and a new labeled type, typo_duplicate_payment.

## Decision

ledgercheck pins synthbiz 0.2.0 and measures with the background rows on. Flags that land on a background row count as false positives, because the labels do not point to it. A rule may map to more than one label type, so duplicate_fuzzy scores against near_duplicate_payment and typo_duplicate_payment. Label types that no rule scores are counted and listed, not dropped and not fatal. No new setting or allowlist is added in this change.

## Consequences

Precision now shows false alarms on legitimate synthetic rows. The numbers are on synthetic data and do not predict real books. Only duplicate_exact stays at a precision of 1.0, because no background row repeats an invoice or a vendor, invoice number and amount. Every rule except duplicate_exact and split_under_limit flags at least one kind of background row, so its precision drops. split_under_limit had false alarms before and has them now, from ordinary invoice pairs, and its precision moved from 0.5130 to 0.4319. The numbers block in the README has the rates and the clean ledger counts. Tuning now keeps rare_share at its default and lowers invoice_threshold to 0.6 for duplicate_fuzzy. That reaches a recall of 1.0 on near and typo duplicates together, with more flags and a precision of 0.5286 against 0.5134 at the defaults.

rare_poster recall rose from 0.2402 to 0.9295 at the same rare_share of 0.05. rare_poster flags an entry when its user's share of the entries with the same source type is under rare_share, for source types with at least rare_min_entries (20) entries and a non-empty created_by (src/ledgercheck/rules.py). The background rows add many manual entries by other users (src/synthbiz/background.py in synthbiz), so the share of the planted users IT_ADMIN_1 and TEMP_USER_1 gets smaller and more of their entries fall under the threshold. CFO_1 and TAX_ACCOUNTANT_1 are the new false alarms. Tuning keeps the default of 0.05 unless another value has a strictly lower cost, and none does.

The cost of a miss for typo_duplicate_payment is a placeholder equal to near_duplicate_payment. The approval limit stays a fixed setting of 500,000 cents, the same value synthbiz writes to manifest.json.
