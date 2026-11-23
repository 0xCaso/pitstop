# Personal and outside-work details removed from the public history

Decided: 2026-11-23 · Case: c_70b46aa8-69c3-4d09-82f0-040f5b85d238

## Question and choice
The public repo held a scrawl capture whose summary named an outside project, and an account name of the author's
second Claude account in files and commit messages. What to remove, and how? Chosen:
- Commit author email: keep as it is.
- PR #26 text: edit it (done: "In one session").
- Scrawl folder and account name: remove from the whole history and force push ("sarebbe da togliere e riscrivere
  la storia").
- A repo rule: "in generale non dovremmo mai includere dettagli personali o di lavori esterni".

## Why
Deleting the files in a new commit leaves them in every older commit. Only a rewrite takes them out of the clones
and archives GitHub serves from the branches and tags.

## Constraints
- The rewrite changes every commit id: open branches and local checkouts must be reset onto the new history.
- The released tags (v0.5.2, v0.5.3) move with it; the npm packages are unchanged.

## Ruled out
- A request to GitHub support to purge the cached views, refs/pull and the one fork: not chosen.

## Comments
—

## Open questions
- The one fork and the refs/pull refs of merged PRs still hold the old history.

## Sources
- Case c_70b46aa8-69c3-4d09-82f0-040f5b85d238.

## Tasks
### Done
- `git filter-repo` on a mirror clone: removed `docs/feedback/scrawl/`, replaced the account name with "second
  account" in files and commit messages; force-pushed main, 5 branches and tags v0.5.2, v0.5.3 (main 129f212 →
  6b68d34). A scan of every commit on a fresh clone found none of the names.
- `.claude/CLAUDE.md` "Privacy": the rule and the scan before each push.
- `docs/feedback/2026-11-23-skip-folds-reply.md` no longer points to the removed folder.
