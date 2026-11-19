# 13. The approval limit comes from manifest.json when present

Status: Accepted

## Context

ADR 0011 left the approval limit as a fixed setting of 500,000 cents, the same value synthbiz writes to manifest.json. If synthbiz changes its limit, the split_under_limit rule would use a stale number. ADR 0007 says only evaluate.py reads labels.csv and manifest.json, and a test enforces it.

## Options

1. Read the manifest in rules.py. Breaks ADR 0007 and the rules would depend on a synthbiz file.
2. Read it in evaluate.py with a small function, read_manifest_limit, and let the CLI pass the value into the settings. Keeps the boundary.
3. Keep the fixed default. Simple, but it drifts.

## Decision

Option 2. Precedence is: a value in the --settings file, then the manifest value, then 500,000. A manifest with no approval_limit_cents key, or no manifest, changes nothing. A manifest key that is not a whole number from 1 to 10^15 is an error, not a silent fallback, because a wrong limit would hide or invent split_under_limit items. The rules still do not read any file. Library callers that build Settings themselves are not affected.

## Consequences

On synthbiz 0.2.0 data the manifest value is 500,000, so no measured number changes. The limit in use is not shown in the analysis yet.
