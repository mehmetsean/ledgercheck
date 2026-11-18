# 9. Benford is a status line, not a scored rule

Status: Accepted

## Context

A first digit test does not point to a unit that can be right or wrong, and synthbiz has no label for it. A Benford misfit is also expected on some honest fields: sequential ids, check numbers, and amounts drawn from a uniform range such as synthbiz amounts. Chi-square rejects almost any large sample.

## Decision

benford_first_digit reports one table per amount field and prints a status before the numbers: weak_sample under 5,000 values, not_applicable for id-like or sequential fields, ok otherwise. It reports mean absolute deviation with the first-digit cutoffs from Nigrini (2012), plus chi-square with a note that it rejects almost any large sample. It produces no flags and is not scored. entry_number_gap is also not scored.

## Consequences

The analysis shows the Benford status first and the reader decides. These two rules have no measured precision or recall, and the README says so. A real Benford rule would need labels first.
