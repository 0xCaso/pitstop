# The continuation test favors pitstop 4 to 1. What next?

Decided: 2026-11-10 · Case: c_65e6b427-5193-4080-b87b-9176ab9c5d0e

## Question and choice
Continuation test on the 5 pilot cycles: pitstop won 4, native compact 1; wrong claims P 5, N 11. Next step?
Choice: "Make the R-P3 release first. Then run the fixed continuation test on the 5 R-P3 cycles and 5 new cycles, to test the new rule and pitstop vs native compact together."

## Why
- The result already favors pitstop, and R-P3 must be tested anyway: one run does both jobs.

## Constraints
- Release: rule R-P3 (exact edits in `~/.claude/pitstop/reviews/20261110-163603/review.md`) plus the 7 deferred minors of https://github.com/0xCaso/pitstop/pull/17.
- Fixed test: each twin reads the repo at the commit of the cut (git worktree), so it does not see later files.
- Cycles: the 5 R-P3 cycles (31f871e460a4, 47bb94167c91, 5813dc857b7b, 077a91b7b371, cd475f610f47) and 5 new ones. About USD 40 (estimate: USD 4 per cycle in this run).

## Ruled out
- Fix the test and run 10 more cycles before the release: it costs the same and does not test R-P3.
- Stop the tests and only release: 5 cycles alone can be chance.

## Comments
The user asked what R-P3 is; answered in the case (the owed-reply rule of `2026-11-10-lost-reply-after-restart.md`).

## Open questions
none

## Sources
- Case c_65e6b427-5193-4080-b87b-9176ab9c5d0e.
- `~/.claude/pitstop/twin/cont-20261110/summary.md`, `report.md`.
