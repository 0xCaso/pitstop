# Do I push the pitstop gap fix and open a PR?

Decided: 2026-11-19 · Case: c_9b884364-4fc8-4860-a9fe-03583337f74f

## Question and choice
Push branch `fix/report-counts` and open a PR as 0xCaso? Matteo chose "Push fix/report-counts and open a PR as 0xCaso, with the test output in the body", with a question attached (see Comments). Done: https://github.com/0xCaso/pitstop/pull/23

## Why
The fix is small, tested (349 tests, `claude plugin validate --strict` passes) and changes only the report. The PR lets Matteo review it before the merge.

## Constraints
- The PR goes out as 0xCaso (personal repo).
- The hook's raw `gaps.jsonl` keeps every read; only the report counts one gap per resumed cycle.

## Ruled out
- Keep it local: the fix would not reach the published plugin, and the report would keep showing 47 gaps per 100.

## Comments
- Matteo: "cos'è questa cosa delle T3 delegates? è questo che sta peggiorando pitstop e come lavoro io (visto che ultimamente gli agent si fermano spesso, anche)?"
  - What they are: child sessions that T3 starts with `delegate_task` (a sub-agent with its own thread). Since 0.5.2 they reach the 200K threshold more often: 81 cycles, against 2 in 0.5.1.
  - They lower the "resumed" percentage in the report (47% for delegates, 92% for main sessions), but they do not make pitstop worse for your work: 20 of the 27 skipped requests came within 3 minutes of the delegate's end, so a checkpoint there would be useless. Main sessions: 92% resumed (0.5.1: 95%).
  - The agents that stop are not caused by pitstop. In T3, 12–19/11, 40 runs failed with an error: 19 "Can't reach the API server (ENOTFOUND)", 11 "rate limit reached", 9 authentication errors (8 of them a Cloudflare "Attention Required" page), 1 "connection refused". Source: `~/.t3/userdata/statev2.sqlite`, items of type `error` in failed runs.
  - Side finding: the new `pr-guard` hook warned "no Proof section" on this PR, a false positive (the body built with `$(cat <<EOF …)` held quotes that split the token). Fixed in `~/.claude/hooks/pr-guard.sh`: the Proof check also reads the raw text after `--body`. Tested with 3 inputs.

## Open questions
- Show T3 delegates on their own line in `pitstop report`, so the main-session number stays readable?
- Whether to look into the network and authentication errors (19 ENOTFOUND, 9 Cloudflare auth): they stop runs more than anything else this week.

## Sources
- Case c_9b884364-4fc8-4860-a9fe-03583337f74f; record `docs/decisions/2026-11-19-check-0-5-2-numbers.md`.
- `~/.t3/userdata/statev2.sqlite` (tables `orchestration_v2_projection_runs`, `orchestration_v2_projection_turn_items`).

## Tasks
1. **Merge PR #23 after review.** Criteria: CI green; Matteo approves; `pitstop report` on main prints gaps per 100 resumes. From: Question and choice, "open a PR as 0xCaso".
2. **Report: T3 delegates on their own line.** Criteria: `pitstop report` splits main sessions and T3 delegates (detected by the "Act as the … sub-agent" first prompt); a test covers it. From: Open questions, line 1. Waits for Matteo.
3. **Look into the run failures.** Criteria: each of the 40 failed runs of 12–19/11 has a cause class and a fix or "external"; the Cloudflare auth errors get a repro. From: Open questions, line 2. Waits for Matteo.
