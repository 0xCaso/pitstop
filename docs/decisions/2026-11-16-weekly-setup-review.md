# Weekly setup review 2026-11-16: which of the 6 changes to apply?

Decided: 2026-11-16 · Case: c_77858165-51d7-4afe-a979-f8aceb027ddf

## Question and choice
Six changes from the weekly setup review, each approve or reject. Matteo chose:
1. c1 · "Estimates: remove the rule 'at stage idea, move the size up one class'" — **approve**.
2. c2 · "Pitstop R-MARK: let --reply-checked pass only when a new reply to the user comes after the last event (delegate results count as events)" — **approve**.
3. c3 · "Pitstop: make mark-pending refuse a checkpoint with a Waggle id that is not complete (c_ plus a full uuid)" — **approve**.
4. c4 · "Pitstop: skip the automatic pitstop when the work is done (Next action empty, or a sub-agent already sent its final report)" — **approve**.
5. c5 · "Pitstop R-LANG: make the resume message name the language (for example Italian) for chat and for every ask" — **approve**.
6. c6 · "Pitstop P1 (deferred on 2026-11-13): add the rule 'environment facts and who does each step'" — **reject**.

## Why
Matteo gave no comment; he followed the recommendation on every item. Reasons from the ask:
1. c1: the idea-stage bump made estimates too high: calibration rows 25, 48, 51, 96 came out ×2,0 ×0,2 ×3,4 ×4,2 (median ×2,7) (`~/.claude/estimates/calibration.md`).
2. c2: 8 cycles passed `--reply-checked` with a reply still owed and 4 more where the check did not fire; in 2bca4847a27a a sub-agent report and 3 decisions never reached Matteo.
3. c3: Waggle ids cut to 8 chars or lost in 5 cycles; in 0a0764523882 the session told Matteo a false fact.
4. c4: 4 pitstops ran after the work was done, two of them in place of a sub-agent's final report.
5. c5: 6 cycles wrote chat or Waggle asks in English after an Italian session.
6. c6: only 2 minor new cases against ~12 cycles where the facts were kept.

## Constraints
- pitstop rule changes (c2–c5) take effect only when they ship in a pitstop release; nothing changes in the installed skill before that.
- `mark-pending` must still accept every valid checkpoint: the new checks refuse only an incomplete Waggle id, an empty Next action, or a reply owed after the last event.
- The resume message falls back to the current wording when no language is known.
- The stime SKILL.md keeps its other idea-stage rule (calendar not divided at stage `idea`).

## Ruled out
- c6 "environment facts and who does each step": not enough evidence (2 minor cases vs ~12 counter-examples); not deferred again.
- Defer c2–c5 again: they were already deferred on 2026-11-13 and the new week added 15+ cycles of evidence.

## Comments
none

## Open questions
none

## Sources
- Case c_77858165-51d7-4afe-a979-f8aceb027ddf
- `~/.claude/setup-review/runs/2026-11-16/report.md`, `brief.json`
- `~/.claude/pitstop/reviews/20261116-030554/findings.md` (per-cycle verdicts), `review.md` (Approved rules, Rejected)
- `~/.claude/estimates/calibration.md` rows 25, 48, 51, 96

## Applied already
- c1: `~/.claude/skills/stime/SKILL.md` step 2, the rule is now "Stage `idea`: use the size you pick, as at the other stages." Backup `SKILL.md.bak-2026-11-16`.
- c6: written under "Rejected" in `review.md`. `review-done` run: 71 cycles · 4 approved · 1 rejected.

## Tasks
c2–c5 are code in this repo. Each task ships with tests and a line in the next release notes.

### T1 · R-MARK counts delegate results as events
From: Question and choice, line 2 — "let --reply-checked pass only when a new reply to the user comes after the last event (delegate results count as events)".
Criteria:
- `pitstop/cli.py:160`: with `--reply-checked`, mark-pending exits non-zero with `owed reply:` when the last user-facing assistant text comes before the last user message or tool result (Agent, `delegate_task`, `task_status`, subagent result).
- A transcript with a reply after the last event passes, with or without `--reply-checked`.
- Refusal text (`pitstop/claude/messages.py:149`) names the event that came after the last text.
- SKILL.md "Checkpoint procedure" step 2 no longer tells the agent to re-run with `--reply-checked` without a reply.
- New tests in `tests/test_cli.py` cover the 3 cases (delegate result after text, user message after text, reply after both); `test_cli.py:217` still passes or is updated to the new rule.

### T2 · mark-pending refuses incomplete Waggle ids
From: Question and choice, line 3 — "refuse a checkpoint with a Waggle id that is not complete (c_ plus a full uuid)".
Criteria:
- A checkpoint with a token `c_[0-9a-f]+` that is not `c_` + 36-char uuid (8-4-4-4-12) makes mark-pending exit non-zero and print the bad token.
- A checkpoint with full ids, or none, passes.
- SKILL.md "Checkpoint content" exact-strings bullet names Waggle case ids in full.
- Tests: `c_ab953168` refused; `c_77858165-51d7-4afe-a979-f8aceb027ddf` accepted.

### T3 · no automatic pitstop when the work is done
From: Question and choice, line 4 — "skip the automatic pitstop when the work is done (Next action empty, or a sub-agent already sent its final report)".
Criteria:
- SKILL.md "Automatic pitstop" step 2 has a new exception category `done`; the sub-agent case says to write the final report, not a skip line in its place.
- mark-pending exits non-zero when the "Next action" section is empty or `—`.
- `report_scan` counts the new `done` category; `tests/test_plugin.py:88` lists it.
- Tests for the empty Next action refusal.

### T4 · resume message names the language
From: Question and choice, line 5 — "make the resume message name the language (for example Italian) for chat and for every ask".
Criteria:
- `resume_context` (`pitstop/claude/messages.py:176-177`) writes "in <Language> (the language used before the restart), in chat and in every ask." when the checkpoint's User preferences name a language (e.g. "Reply in Italian.").
- With no language found, the current wording stays.
- `tests/claude/test_messages.py:79` updated; a new test with an Italian preference checks the word "Italian" in steps 3 and 4.
