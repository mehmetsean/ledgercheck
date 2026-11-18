# 3. Flags are items to check, with reasons, never verdicts

Status: Accepted

## Context

A rule hit on a journal entry or a payment is a reason to look, not proof of an error or of fraud. A list of flags with no reason is hard to act on, and a flag worded as a verdict could be read as a claim about a person.

## Decision

Every flag has a rule name, the table, the unit id, the row ids and a plain reason, for example "Posted on Saturday 2025-03-08". The output is called an analysis, never an audit, review or compilation. Every output file carries the disclaimer: decision support only, not legal, tax, accounting or assurance advice, with no guarantee of compliance. A rare_poster reason says only that a user id posts rarely. Rules never read labels or the memo column. Output text cells that start with =, +, - or @ are escaped so a spreadsheet does not run them.

## Consequences

The tool does not rank flags as more or less guilty, and it has no score per person. Precision and recall are shown next to the rules so a reader knows how often a flag is right on labeled data. Reasons must be written for every new rule.
