# 4. Fuzzy duplicates are blocked by amount and a date window

Status: Accepted

## Context

Exact-key matching is O(n) but misses a payment that was re-keyed under another vendor id, which is how synthbiz plants near duplicates (new vendor_id, same invoice number and amount). All-pairs fuzzy matching finds them but needs O(n^2) compares. In docs/benchmark.md, 4,132 payments need 8,534,646 compares and 126.177 s for one all-pairs run, against 176 compares and 0.009 s blocked.

## Decision

duplicate_fuzzy sorts payments by amount and date. It compares each payment only with later payments that have the same amount and fall inside the date window setting. Blocks are by amount, not vendor_id, because a re-keyed vendor changes the vendor id. Cost is O(n log n) for the sort plus O(n x k x c), where k is the most same-amount payments in one window and c is one Levenshtein compare on names capped at 100 characters. The report prints k and the compare count.

Options considered:

- Exact keys only: fast, finds no re-keyed vendor.
- All-pairs fuzzy: finds the most, too slow and too many extra flags.
- Block by vendor_id: misses the re-keyed case.
- Block by amount and date window (chosen).

## Consequences

A near duplicate whose amount was changed is never found. On the 36 month benchmark all-pairs fuzzy found 87 different-amount pairs, and none was planted, so the benchmark cannot say how many of those are real. docs/benchmark.md shows 80 near duplicate false positives for the same run because it scores one flag per later payment, not one per pair. The README states this limit. An amount tolerance band is a possible later change. benchmarks/bench.py checks that blocking never loses a match that shares an amount and falls in the window, and exits non-zero when it does. CI runs a quick form of it.
