# Do we fix the lost reply after a pitstop restart?

Decided: 2026-11-10 · Case: c_64fc0985-0a3c-4167-9ec3-709419871533

## Question and choice
Do we add this rule: before the checkpoint, write the owed reply in the same turn; after the restart, if the checkpoint says NOT SENT, send that reply first?
Choice: "Approve. Change the skill (checkpoint procedure) and the resume steps in messages.py. A label that mixes SENT and not sent counts as NOT SENT."

## Why
- Review of 36 cycles of 0.5.0: 5 cycles lost the owed reply, all with real harm (`~/.claude/pitstop/reviews/20261110-163603/findings.md`).
- In 3 of them the checkpoint was right (NOT SENT, with the text), but `resume_context` in `pitstop/claude/messages.py` has no step to send it.

## Constraints
- Exact edits are in `~/.claude/pitstop/reviews/20261110-163603/review.md` (R-P3).
- The rule ships in the next pitstop release, together with the 7 deferred minors of PR #17.
- The twin test can check the fix on the 5 failing cycles before the release.

## Ruled out
- Reject (keep 0.5.0 as it is): the failure has real harm and the fix is small.

## Comments
none

## Open questions
none

## Sources
- Case c_64fc0985-0a3c-4167-9ec3-709419871533.
- `~/.claude/pitstop/reviews/20261110-163603/findings.md`, `review.md`.
- `pitstop/claude/messages.py:146-168`.
