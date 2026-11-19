# 15. period_mismatch has a close window

Status: Accepted

## Context

period_mismatch flags an entry whose period differs from the month of its posting date. Books close in the first days of the next month, so accruals posted then carry the previous period on purpose. These are false alarms. In synthbiz data the background accruals are posted on business days 1 to 3, which is calendar day 1 to 5 depending on weekends. The planted out-of-period entries are posted after that window.

## Options

1. Use business days. Needs a calendar per ledger and the holiday list, and adds rules that are hard to explain.
2. Add a setting, close_window_days, in calendar days of the month. Simple, and the owner of the data knows how long the close lasts.
3. Do nothing. Keeps recall but leaves the false alarms.

## Decision

Option 2. An entry is not flagged when its period is the month before its posting date (December for January) and its posting day of the month is at most close_window_days. Any other mismatch is still flagged. The value is a whole number from 0 to 31 and the default is 0, which turns the window off, so no measured number changes. The rule is O(1) per entry.

## Consequences

Measured on synthetic data (large, 12 months, rate 0.1). Seed 42: at 0 the rule gives 48 flags at precision 0.5417 and recall 1.0000. At 3 it gives precision 0.8125, at 5 it gives precision 1.0000 and recall 1.0000. Report seeds 101-130: at 0 precision 0.5417, recall 1.0000. At 3 precision 0.7761, recall 1.0000. At 4 precision 0.8783, recall 0.9897. At 5 precision 1.0000, recall 0.9718. A wider window also hides planted entries posted early in the month, so recall drops from 5 days on. Pick the window from the real close calendar. Run scripts/measure_close_window.py to repeat it. The tuning step does not use the setting.
