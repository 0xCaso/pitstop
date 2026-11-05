# Push the pitstop notification fix and release 0.3.1?

Decided: 2026-11-05 · Case: c_de4a9ebf-dcb0-47cf-b939-844fc889e036

## Question and choice
The fix that keeps a harness notification from dropping the /compact checkpoint was committed on
`fix/system-notification-drops-checkpoint` (d0a7a5c), with all 277 tests passing. What should be published?

Matteo chose: "Push the branch as 0xCaso and open a PR to main. Do not change the version and do not release."

## Why
- Matteo gave no reason beyond the choice.
- Agent's reasons: Matteo can review the PR before merge, then release it alone or together with other fixes.
  An npm publish cannot be undone, so it waits until after review.

## Constraints
- The push and the PR go out as 0xCaso (`GH_TOKEN=$(gh auth token -u 0xCaso)`).
- The version stays 0.3.0 in `package.json` and `.claude-plugin/plugin.json`.
- No `npm publish` and no release tag from this branch.

## Ruled out
- PR plus 0.3.1 release: an npm publish cannot be undone and should come after review.
- Keep it local: the fix is ready and tested; holding it only delays review.

## Comments
none

## Open questions
- When to release 0.3.1, and whether it ships alone or with other fixes.

## Sources
- Case c_de4a9ebf-dcb0-47cf-b939-844fc889e036
- `pitstop/claude/hooks.py` (`_is_harness_notification`, `_handle_user_prompt_submit`)
- `tests/claude/test_hooks.py` (notification tests)
- `~/.claude/pitstop/log.jsonl`, session 27c6f616 (the original bug evidence)
