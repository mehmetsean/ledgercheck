# ledgercheck
Local-first journal entry and duplicate payment checks. Every flag is an item to check, not a finding of fraud or error. The output is an analysis.

Decision support only, not legal, tax, accounting or assurance advice. No guarantee of compliance, and no guarantee that all errors or duplicate payments are found. False positives and misses are expected; the measured rates are shown.

## Run

```
pip install -e .
ledgercheck run data/ --out results/
```

The analysis includes a table of precision and recall per rule, read from src/ledgercheck/measured.json. Those rates are measured on synthetic data (synthbiz) and do not predict results on real books.

## Evaluate

The evaluate command scores the rules against the labeled anomalies in synthbiz data. It needs the eval extra.

```
pip install -e ".[eval]"
ledgercheck evaluate data/
ledgercheck evaluate --size large --months 12 --tune-seeds 1-10 --seeds 101-130 --rate 0.1 --out eval/
```

The first form scores one labeled folder. The second generates each seed in memory and reports at the run defaults on the report seeds. For the two rules that have a setting to tune (duplicate_fuzzy and rare_poster) it also picks the fuzzy thresholds and the rare_share with the lowest placeholder cost on the tuning seeds, keeps the default on a tie, and shows the tuned rows next to the default rows. It writes evaluation.md, evaluation.html, metrics.json and README.txt. Intervals are 95 percent percentile bootstrap intervals over seeds (2,000 draws, fixed RNG seed). Costs are placeholders; pass your own with --costs. Limits: 50 tuning seeds, 200 report seeds, and (tuning seeds + report seeds) times months at most 6,000.

### How to read the numbers

- Recall and precision of 1.0 for weekend_posting, holiday_posting, no_approver, period_mismatch, duplicate_exact and duplicate_fuzzy are expected. synthbiz's clean ledger has no weekend, holiday, unapproved or odd-period entries, and its near duplicates keep the amount and the invoice number. These numbers show that the rules match how synthbiz plants anomalies. They do not show how well the rules work on real books.
- A zero-width interval means every report seed scored the same. It is not high certainty.
- Only round_amount and split_under_limit show false alarms, because ordinary entries and invoices overlap them. The split precision comes from normal in-band invoices of one vendor, not from the planted rate.
- rare_poster at the default rare_share (0.05) misses most planted anomalies on synthbiz data. The tuned row shows a higher rare_share.
- Limit: synthbiz near duplicates differ only in vendor suffix or punctuation and keep the invoice number, so measured fuzzy recall says nothing about typos. The generator is `_near_duplicate` in src/synthbiz/anomalies.py of synthbiz at commit 47a763a79681805e7dcb992c7d47e5166a83aa09, the commit pinned in pyproject.toml.
- "Caught by any scored rule" counts a labeled unit as caught when a flag from any of the nine scored rules lands on it. entry_number_gap and benford_first_digit are not scored.

To see which rules flag anything on a clean ledger (synthbiz with a planted rate of 0), run these two commands. With the default seed, only round_amount (1 item) and split_under_limit (2 items) show items in the table; every other rule shows 0.

```
synthbiz generate --anomaly-rate 0 --out /tmp/clean_ledger
ledgercheck run /tmp/clean_ledger --out /tmp/clean_ledger_out
```

Then open /tmp/clean_ledger_out/analysis.md and read the "Items to check per rule" table.

To rebuild or check the shipped rates: `python scripts/make_measured.py` and `python scripts/make_measured.py --check`.

Work in progress. The plan is in docs/spec.md.

## Contributions

Outside code contributions are not accepted. Bug reports by issue are fine.

## License

All rights reserved. You may view the code and run it to evaluate it. Commercial use needs a paid license from Mehmet Tuzunkan: https://www.linkedin.com/in/mstuzunkan
