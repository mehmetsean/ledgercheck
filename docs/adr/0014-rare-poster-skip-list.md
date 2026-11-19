# 14. rare_poster has a skip list for system users

Status: Accepted

## Context

rare_poster flags an entry when its user posts under rare_share of a source type. A system or batch user that posts rarely is a false alarm, because a job is not a person acting out of pattern. In synthbiz data the system ids are SYSTEM_BATCH and SYSTEM_RECURRING. At rare_share 0.05 they are not flagged, but at 0.1 they are.

## Options

1. Hard code names that start with SYSTEM. Wrong for other ledgers.
2. Add a setting, rare_skip_users, a list of user ids. The owner of the data knows which ids are jobs.
3. Do nothing and keep rare_share low. Loses recall on rare posters.

## Decision

Option 2. The list is exact match, default empty. A skipped user is never flagged, but their entries still count toward the source type total, so other users keep the same share. The settings file takes a list of non-empty text ids, at most 10,000 of them. The default stays empty because at the default rare_share the measurement shows no change, so there is no gain to justify a default.

## Consequences

Measured on synthetic data (large, 12 months, rate 0.1, report seeds 101-130): at rare_share 0.05 the allowlist changes nothing (875 flags, precision 0.8286, recall 0.9295). At rare_share 0.1 it lowers flags from 2,340 to 930 and lifts precision from 0.3333 to 0.8387, with recall 1.0000. Run scripts/measure_skip_users.py to repeat it. The tuning step still searches rare_share without the list, so the tuned rows do not use it yet.
