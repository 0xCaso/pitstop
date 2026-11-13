# Two new checkpoint rules from the twin test: now or at the next review?

Decided: 2026-11-10 · Case: c_6126e7d1-84bc-4caa-a2ef-a9d906b91925

## Question and choice
The 10-cycle continuation test (P 8 · N 2) found 19 "missing details" for pitstop. Most are in the checkpoint; the twin did not name them in its first reply. Two rules were proposed:
1. Constraints on how to do the work (where files go, one PR at the end) go word for word under User preferences or Decisions made.
2. On resume, the 3-line recap names the checkpoint details the next action needs, not only the goal.

Choice for both: "Wait for review". User comment: "sia per la domanda 1 che per la 2 segniamocene e vediamo se ricompare il problema per la prossima review".

## Why
- Rule 1 has 2 cycles (547dbf70bfd7, plus "one PR at the end") and no real harm: below the 3-cycle bar of the review rules.
- Rule 2: the probe pilot found P lost 0/40 when asked; the gap may be only in the grader score.

## Constraints
- Nothing changes in SKILL.md or messages.py now.
- At the next /pitstop review, check both failures on 0.5.1 cycles: (1) a work constraint said in chat and lost after the restart; (2) the resumed session misses a detail that was in the checkpoint.

## Ruled out
- Apply now in 0.5.2 with a twin test on 10 cycles (about USD 40, estimate).
- Reject.

## Comments
—

## Open questions
none

## Sources
- `~/.claude/pitstop/twin/cont2-20261110/summary.md`
- Case c_6126e7d1-84bc-4caa-a2ef-a9d906b91925.
