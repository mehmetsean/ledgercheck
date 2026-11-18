# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | yes |

## Report a problem

Report privately with GitHub private vulnerability reporting. Open the Security tab of this repo and choose "Report a vulnerability". Please do not open a public issue for a security problem.

## In scope

- Reading CSV files from a folder you point ledgercheck at, and the input caps that guard it.
- Reading the settings file, the column map file and the costs file.
- The output folder and the `--force` option: which files `--force` may replace.
- The report writers: items_to_check.csv, analysis.md, analysis.html and README.txt, including how spreadsheet formulas and control characters in cells are handled.

## Out of scope

- The synthetic data. It has no real secrets.
- Problems in Python or in third-party tools. Report those to their own projects.

Decision support only, not legal, tax, accounting or assurance advice. No guarantee of compliance.
