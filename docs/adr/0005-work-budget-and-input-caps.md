# 5. A work budget for the fuzzy search and caps on input

Status: Accepted

## Context

The worst case of the blocked search is one amount on one day, which is O(n^2 x c). A crafted or odd file can also be very large or have huge fields. In a browser tab, a long run freezes the page. The first idea was a cap on the number of compares, but one compare can cost from a few steps to 10,000 steps depending on name length, so a compare cap does not bound the time.

## Decision

The fuzzy search counts work in Levenshtein cell steps, plus 16 steps per compare for call overhead, and stops with a clear error when the count passes max_cell_steps (400,000,000 by default, a setting). Pairs whose name lengths already rule out the threshold skip the edit distance. The edit distance rate in docs/benchmark.md is about 21 million cell steps per second, so the default budget is under 20 seconds on that machine.

Input is capped in src/ledgercheck/io.py: 3,000,000 rows per file, 5,000,000 rows in the folder, 500,000,000 bytes per file, 1,000,000,000 bytes in the folder, 128 characters in a field and 256 characters in a vendor name. Settings, column map and costs files are capped at 1,000,000 bytes. Integer columns take an optional minus sign and 1 to 18 ASCII digits. A file over a cap is refused with a one-line message. `--force` replaces only the four known output files and refuses a folder that holds other files.

## Consequences

A run on a very large or crafted file fails early and says why, instead of running out of memory. The caps and the budget are settings or constants, so a user with a big folder can raise the budget but not the row caps. Caps bound the rows read, not the memory use. tests/test_readme_facts.py checks that the README quotes the same constants.
