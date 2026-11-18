# 7. Only the evaluate module reads labels

Status: Accepted

## Context

If a rule could read labels, or any synthbiz id or role name, a measured rate would test the leak and not the rule.

## Decision

evaluate is the only module that reads labels.csv and manifest.json, and the only one that imports synthbiz, which comes from the optional eval extra. rules, duplicates and benford never import evaluate. The rules never read the memo column. A test checks that blanking memo and label details changes no flag, and a test checks the import boundary.

## Consequences

The run command works without synthbiz installed. Rules can be tested on small hand-built ledgers. Any new rule gets its label type mapped inside evaluate, not in the rule.
