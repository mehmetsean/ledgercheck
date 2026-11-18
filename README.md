# ledgercheck
Local-first journal entry and duplicate payment checks. Every flag is an item to check, not a finding of fraud or error. The output is an analysis.

Decision support only, not legal, tax, accounting or assurance advice. No guarantee of compliance, and no guarantee that all errors or duplicate payments are found. False positives and misses are expected; the measured rates are shown.

## Run

```
pip install -e .
ledgercheck run data/ --out results/
```

The analysis includes a table of precision and recall per rule, read from src/ledgercheck/measured.json. Those rates are measured on synthetic data (synthbiz) and will differ on real books.

## Evaluate

The evaluate command scores the rules against the labeled anomalies in synthbiz data. It needs the eval extra.

```
pip install -e ".[eval]"
ledgercheck evaluate data/
ledgercheck evaluate --size large --months 12 --tune-seeds 1-10 --seeds 101-130 --rate 0.1 --out eval/
```

The first form scores one labeled folder. The second generates each seed in memory, picks the fuzzy duplicate thresholds and the rare_poster share with the lowest cost on the tuning seeds, then reports on the separate report seeds. It writes evaluation.md, evaluation.html, metrics.json and README.txt. Intervals are 95 percent percentile bootstrap intervals over seeds (2,000 draws, fixed RNG seed). Costs are placeholders; pass your own with --costs.

Limit: synthbiz near duplicates differ only in vendor suffix or punctuation and keep the invoice number, so measured fuzzy recall says nothing about typos.

To rebuild or check the shipped rates: `python scripts/make_measured.py` and `python scripts/make_measured.py --check`.

Work in progress. The plan is in docs/spec.md.

## Contributions

Outside code contributions are not accepted. Bug reports by issue are fine.

## License

All rights reserved. You may view the code and run it to evaluate it. Commercial use needs a paid license from Mehmet Tuzunkan: https://www.linkedin.com/in/mstuzunkan
