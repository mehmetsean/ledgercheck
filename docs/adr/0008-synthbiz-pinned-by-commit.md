# 8. synthbiz is pinned by commit SHA

Status: Accepted

## Context

The measured rates, the benchmark and the examples depend on exactly how synthbiz plants anomalies. A tag can be moved to another commit, so a tag pin does not guarantee the same data.

## Decision

The eval and dev extras in pyproject.toml point at synthbiz by commit SHA (47a763a79681805e7dcb992c7d47e5166a83aa09). Bumping the pin is its own change. It must rebuild src/ledgercheck/measured.json, docs/benchmark.md, the examples and the README numbers block in the same pull request.

## Consequences

CI fails if measured.json, the examples or the README numbers no longer match the pinned data. The pin is a direct reference, so pyproject.toml sets allow-direct-references for the build. The README names the pinned commit where it describes the typo limit.
