# 4. Fuzzy duplicates are blocked by amount and a date window

Status: Accepted

## Context

Exact-key matching is O(n) but misses a payment that was re-keyed under another vendor id, which is how synthbiz plants near duplicates (new vendor_id, same invoice number and amount). All-pairs fuzzy matching finds them but needs O(n^2) compares. In docs/benchmark.md, 4,439 payments need 9,850,141 compares and 146.359 s for one all-pairs run, against 526 compares and 0.016 s blocked.

## Decision

duplicate_fuzzy sorts payments by amount and date. It compares each payment only with later payments that have the same amount and fall inside the date window setting. Blocks are by amount, not vendor_id, because a re-keyed vendor changes the vendor id. Cost is O(n log n) for the sort plus O(n x k x c), where k is the most same-amount payments in one window and c is one Levenshtein compare on names capped at 100 characters. The report prints k and the compare count.

Options considered:

- Exact keys only: fast, finds no re-keyed vendor.
- All-pairs fuzzy: finds the most, too slow and too many extra flags.
- Block by vendor_id: misses the re-keyed case.
- Block by amount and date window (chosen).

## Consequences

A near duplicate whose amount was changed is never found. On the 36 month benchmark all-pairs fuzzy found 91 different-amount pairs, and none was planted, so the benchmark cannot say how many of those are real. docs/benchmark.md shows 263 near duplicate false positives for the same run. That count also holds pairs outside the date window and legitimate background rows, so it is not the same as the 91 pairs. The README states this limit. An amount tolerance band is a possible later change. benchmarks/bench.py checks that blocking never loses a match that shares an amount and falls in the window, and exits non-zero when it does. CI runs a quick form of it.
