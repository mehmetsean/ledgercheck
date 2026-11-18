# Examples

This is synthetic data made by synthbiz. It is not from any real company.

- synthbiz-seed42-12m: synthbiz seed 42, size small, 12 months, default anomaly rate.
- ledgercheck-seed42-12m: the output of `ledgercheck run` on that folder (items_to_check.csv, analysis.md, analysis.html, README.txt).

To rebuild both folders from a clean clone:

```
pip install -e ".[eval]"
python scripts/make_examples.py
```

To check that the files in this folder are current, byte for byte:

```
python scripts/make_examples.py --check
```

CI runs the check on every pull request.

Every line in items_to_check.csv is an item to check, not a finding of fraud or error. Decision support only, not legal, tax, accounting or assurance advice.

All rights reserved. You may view the code and run it to evaluate it. Commercial use needs a paid license from Mehmet Tuzunkan: https://www.linkedin.com/in/mstuzunkan
