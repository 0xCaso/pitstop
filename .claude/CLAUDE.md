# Visual work

- Designs live in `design/claude-pitstop.pen` (pen.dev).
- Mock it there first, before changing it in the repo: the README chart (`assets/context-*.svg`).

# Twin tests

- Run every twin test on the account the author names for it (`scripts/twin.py --config-dir`; default: the current
  account, from 2026-11-23).
- After a twin test run, add it to `docs/twin-tests.md` and update the README table ("Tested against native compact").

# Releases

- After each `npm publish`: tag `v<version>` on the published commit and a GitHub release with notes (as 0xCaso).

# Reviews

- Rule in `docs/decisions/2026-11-13-review-policy.md`: one check of 0.5.2 at ~30 cycles with a 30-cycle twin test, then a review only when a `pitstop report` number gets worse.

# Privacy

- The repo is public. Files, commits, PR text and issues never name clients, outside work, account names, local
  paths (`/Users/...`), thread titles or other personal details; scrawl captures stay out of the repo.
- Before each push, scan the diff and the commit messages for them
  (`docs/decisions/2026-11-23-history-rewrite-privacy.md`).
