# Pitstop: skip the offer when no work is left?

Decided: 2026-11-19 · Case: c_82f6b300-6aff-4a41-a125-427b4842652a

## Question and choice
1. In the soft zone, should the offer be skipped when the next action would be "nothing pending"? Chosen: "Skip when nothing is left": offer mode skips and prints nothing; the hard request at the threshold stays the same.

## Why
- The skill took the offer at "a task done" (`skills/pitstop/SKILL.md:48`), also with no work left: on 2026-11-19 an offer at 183K (0 background tasks) gave a checkpoint whose next action was "Nothing pending".
- With no work left the checkpoint keeps nothing useful and costs a turn plus a compaction.
- If the user writes again, the hard request at 200K still comes, so the context stays safe.
- No earlier decision said "do not pitstop when the task is done" (searched `docs/decisions/`); only the `ending-soon` exception, which applies to requests, not offers.

## Constraints
- Hard mode does not change.

## Ruled out
- Also skip hard requests near the end: the hard limit is the safety net.
- Keep as is: pitstops with nothing to resume.

## Comments
- F1 in `docs/feedback/2026-11-19-offer-when-done.md`.

## Open questions
—

## Sources
- Case c_82f6b300-6aff-4a41-a125-427b4842652a.
- Stop hook message, 2026-11-19 10:56: `mode: offer`, `context: 183540 tokens`.

## Tasks
1. **Offer text and skill.** Criteria: offer hook message says "and more work is left"; SKILL.md offer rule skips when the next action would be "nothing pending" or "wait for the user"; README line updated; test in `tests/claude/test_messages.py` fails before, passes after. From: Question and choice, item 1.
2. **Ships in 0.5.3.** Criteria: merged to main before the release branch `chore/release-0.5.3` is rebased for the check. From: Constraints.
