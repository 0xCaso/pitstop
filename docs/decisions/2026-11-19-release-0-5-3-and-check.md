# Pitstop: publish 0.5.3 now, and when do we do the 0.5.2 check?

Decided: 2026-11-19 · Case: c_a63ede1e-d31f-4f03-a550-058cdfe6cb1c

## Question and choice
1. Publish 0.5.3 (gap count fix, T3 delegate line, ledger rule) now? Chosen: "Wait for the check": keep 0.5.3 local and publish it with the changes from the 0.5.2 check.
2. When do the 0.5.2 check and the 30-cycle twin test (~120 USD, estimate)? Chosen: "Wait until the new sessions line shows about 30 main-session cycles, then check only if main is still below 0.5.1 (95%)".

## Why
- Old data mixes main sessions and T3 delegates; the `sessions:` line in `pitstop report` (PR #24) separates them from now on.
- If main sessions reach 95% again, the check and its ~120 USD are not needed (`docs/decisions/2026-11-19-check-0-5-2-numbers.md`).
- Matteo's machine already runs main from the repo (skill link to the checkout), so waiting only delays other users.

## Constraints
- Every check and twin test runs with the wer-team account: `CLAUDE_CONFIG_DIR=~/.claude-wer-team` (Matteo: «facciamo i check sempre con account wer-team»). Written in `.claude/CLAUDE.md`.
- Branch `chore/release-0.5.3` (version bump, tests pass) stays local until the check ends.
- Trigger: about 30 cycles counted as `main` on the `sessions:` line.

## Ruled out
- Publish now: Matteo prefers one release with the check changes.
- Check now: old data mixes session kinds, and the money may measure the mix.
- Skip the check: the 2026-11-13 review policy asks for one check of 0.5.2.

## Comments
- «facciamo i check sempre con account wer-team» → rule in `.claude/CLAUDE.md` (Twin tests) and in this record.

## Open questions
- Exact "gets worse" threshold for later reviews: set at the check (from `2026-11-13-review-policy.md`).

## Sources
- Case c_a63ede1e-d31f-4f03-a550-058cdfe6cb1c.
- `pitstop report` (2026-11-19): 0.5.2, 233 cycles, resumed 75%.
- `docs/decisions/2026-11-13-review-policy.md`, `docs/decisions/2026-11-19-check-0-5-2-numbers.md`.

## Tasks
1. **Watch for the trigger.** Criteria: the nightly review reads the `sessions:` line each night and, when main reaches ~30 cycles, says so in its report and opens the Waggle ask for the check. From: Question and choice, item 2.
2. **The check, when triggered.** Criteria: only if main resumed < 95%; R-MARK, R-LANG, R-CMD, R-GAP and W1 checked; 30-cycle twin test with `CLAUDE_CONFIG_DIR=~/.claude-wer-team`; results in `docs/twin-tests.md` and the README table. From: Constraints, lines 1 and 3.
3. **Release 0.5.3 after the check.** Criteria: release PR from `chore/release-0.5.3` plus the check changes; after merge `npm publish`, tag `v0.5.3`, GitHub release as 0xCaso. From: Question and choice, item 1.
