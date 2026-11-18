# 6. Measured rates ship in the package, at the run defaults

Status: Accepted

## Context

A list of flags is hard to act on without knowing how often each rule is right. Rates measured on tuned settings look better than the rates a user gets by running the tool with its defaults. Rates that are not in the package cannot be shown in the analysis a user opens.

## Decision

src/ledgercheck/measured.json holds the measured rates and the analysis prints them, labeled "measured on synthetic data (synthbiz)". The rows named after a rule are measured at the run defaults, with no tuning. For the two rules that have a setting to tune (duplicate_fuzzy and rare_poster) the tuned rows are shown apart, with settings picked on separate tuning seeds, and a tie keeps the default. Intervals are 95 percent percentile bootstrap intervals over seeds. scripts/make_measured.py rebuilds the file and `--check` fails CI when it is out of date.

## Consequences

The default rare_poster row shows a recall far below the tuned one, and that is the honest number for a user who does not tune. A change to a rule or to the data generator needs a rebuild of measured.json. A rate of 1.0 on synthbiz reflects how synthbiz plants anomalies and is not accuracy on real books, which the README says next to the numbers.
