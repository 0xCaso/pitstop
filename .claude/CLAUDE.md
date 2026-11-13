# Visual work

- Designs live in `design/claude-pitstop.pen` (pen.dev).
- Mock it there first, before changing it in the repo: the README chart (`assets/context-*.svg`).

# Twin tests

- After a twin test run, add it to `docs/twin-tests.md` and update the README table ("Tested against native compact").

# Releases

- After each `npm publish`: tag `v<version>` on the published commit and a GitHub release with notes (as 0xCaso).

# Reviews

- Rule in `docs/decisions/2026-11-13-review-policy.md`: one check of 0.5.2 at ~30 cycles with a 30-cycle twin test, then a review only when a `pitstop report` number gets worse.
