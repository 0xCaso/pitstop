# How do we check pitstop now?

Decided: 2026-11-19 · Case: c_37d44429-780f-41ca-9218-15b849631d51

## Question and choice
`pitstop report` shows worse numbers for 0.5.2: 76% resumed (0.5.1: 92%) and 47 gaps per 100 resumes (0.5.1: 0). How do we check it?
Chosen, with a change: "Fix the count first. Count one gap for each restart. Find why 87 pitstops were skipped. Then run the report again. Do the full check only if a number is still bad."
Change: "Cerchiamo anche di capire perché la percentuale dei ripresi sia calata così tanto - è probabile che le nuove modifiche che abbiamo fatto sulla 0.5.2 abbiano un po' peggiorato oppure volevamo migliorare qualcosa ma abbiamo sbagliato a fare qualcosa nel mentre".

## Why
- Matteo asked whether pitstop works worse than it should, and worse than auto compact.
- The gap number is mostly a counting error: since 0.5.2 (R-GAP) `_record_auto_gaps` writes one gap for each tool call that names the old transcript, so 2 sessions made 56 of the 92 gaps since 13/11. Before 0.5.2 there were no automatic gaps, so 0 is not comparable.
- The resumed drop has a cause to find: 0.5.2 has 29 `skipped` cycles (0.5.1: 1) and 19 `declined` (0.5.1: 2).

## Constraints
- Review policy (`2026-11-13-review-policy.md`) still holds: no new content rules except for real harm.
- A change to the request or skill text ships only if the twin test does not get worse.
- The full 0.5.2 check and the 30-cycle twin test (~120 USD, estimate) only if a number is still worse than 0.5.1 after the fix.

## Ruled out
- Full check and twin test now: the numbers are not yet trustworthy, so the money could measure the counting error.
- Do nothing: the resumed drop may be a real regression from 0.5.2.

## Comments
- Matteo: understand why resumed dropped, a 0.5.2 change may have made it worse. → Task 2 below.

## Findings (2026-11-19)
Source: `~/.claude/pitstop/metrics.jsonl` (last row per cycle), `log.jsonl` (request events → session id), the session transcripts. A session is a "T3 delegate" when its first prompt starts with "Act as the … sub-agent" (T3 `delegate_task`).

| Version | Session kind | Cycles | Resumed | Skipped | Declined | Dropped | Unconsumed |
|---|---|---|---|---|---|---|---|
| 0.5.1 | main | 59 | 56 (95%) | 1 | 0 | 2 | 0 |
| 0.5.1 | T3 delegate | 2 | 0 | 0 | 2 | 0 | 0 |
| 0.5.2 | main | 146 | 135 (92%) | 1 | 5 | 5 | 0 |
| 0.5.2 | T3 delegate | 81 | 38 (47%) | 27 | 14 | 0 | 2 |
| 0.5.2 | scheduled | 2 | 1 | 1 | 0 | 0 | 0 |

- **The resumed drop is a change in the mix, not a 0.5.2 regression.** T3 delegates went from 2 to 81 cycles. Main sessions stay at 92% (0.5.1: 95%, a gap of about 3 cycles).
- **27 of 29 skipped are T3 delegates near their end.** After the request, 20 of them end within 3 minutes and make at most 14 tool calls (e.g. `9b37ec64923b`: 4 calls, 2 minutes). Five print a skip line (`ending-soon`, `other — sono un sub-agente`, `debugging`); the others finish the task without one. Not pitstopping there is correct.
- **14 of 19 declined are T3 delegates.** The other 5 are main-session offers left unused, which is by design.
- **R-MARK ruled out.** Since 0.5.2 mark-pending refused 19 times with `owed reply:`; all 19 then registered the checkpoint (most with `--reply-checked`). No session gave up.
- **Gaps after the fix:** 18 per 100 resumes in 0.5.2. No baseline: before 0.5.2 gaps were only logged by hand.

## Report after the fix
`pitstop report` (worktree `fix/report-counts`): 0.5.2 gaps 18 per 100 resumes (was 47). Resumed stays 76% overall; by session kind, see the table above.

## Open questions
- Whether `declined` offers should count against "resumed" at all (an offer is optional by design).
- Whether the report should show T3 delegates on their own line (they end soon and mostly skip by design).
- Whether to run the full 0.5.2 check and the twin test (~120 USD, estimate): main sessions are 3 points below 0.5.1, and gaps have no baseline.

## Sources
- Case c_37d44429-780f-41ca-9218-15b849631d51.
- `pitstop report` (2026-11-19), `~/.claude/pitstop/gaps.jsonl`, `~/.claude/pitstop/metrics.jsonl`, `~/.claude/pitstop/log.jsonl`.
- `pitstop/claude/hooks.py` (`_record_auto_gaps`), `pitstop/core/cycles.py` (`_settle`), `pitstop/core/metrics.py` (`_summary_line`).

## Tasks
1. **Gaps: one per resumed cycle.** Criteria: a resumed session that reads the old transcript 30 times counts 1 gap; a test covers it; the report prints gaps per 100 resumes from cycles with ≥1 gap. From: Question and choice, "Count one gap for each restart". **Done**.
2. **Find why resumed dropped.** Criteria: each of the 29 `skipped` and 19 `declined` 0.5.2 cycles gets a cause, with transcript evidence; the cause is tied to a 0.5.2 change or ruled out. From: Comments, line 1. **Done** (see Findings).
3. **Report again.** Criteria: `pitstop report` after the fix; numbers compared with 0.5.1 in this record; full check only if one is still worse. From: Question and choice, "Then run the report again". **Done**; the full check waits for Matteo (Open questions).
