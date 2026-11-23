# Weekly setup review 2026-11-23: 4 changes

Decided: 2026-11-23 · Case: c_67448f93-474b-4488-b30a-27e948691afe

## Question and choice
Four changes from the weekly setup review (`~/.claude/setup-review/runs/2026-11-23/report.md`). All four approved:
1. c4 · "Pitstop: do the 0.5.2 check now (twin test, 30 cycles, wer-team account, about 120 USD), then release 0.5.3 with T1–T4 (and c2, c3 if you approve them)" → approve.
2. c2 · "Pitstop rule: the checkpoint must write the absolute path or the exact command of each script, command, draft or data that the session made. Copy what is only in chat or in a temp folder." → approve.
3. c3 · "Pitstop rule: when the work follows an approved mockup or feedback, the checkpoint must name the mockup file with its Waggle case id and the docs/feedback file with its open ids." → approve.
4. c1 · "Estimates: use one query in classes.py and backtest.py that removes units without start or hours, and add a test with such a unit." → approve.

## Why
- c4: the trigger in `2026-11-19-check-0-5-2-numbers.md` is reached; T1–T4 (approved 2026-11-16, `2026-11-16-weekly-setup-review.md`) wait for this check.
- c2: N1 in `~/.claude/pitstop/reviews/20261123-030147/findings.md`: resumed sessions lost scripts, drafts and data that lived only in chat or /tmp.
- c3: N2 in the same findings: resumed sessions lost which mockup was approved and which feedback ids were open.
- c1: the `start: null` crash of 2026-11-13 was fixed with a guard in one place only; `backtest.py` reads units with its own query.

## Constraints
- Review policy (`2026-11-13-review-policy.md`): a change to the request or skill text ships only if the twin test does not get worse.
- The twin test runs on the wer-team account (decision of 2026-11-19).
- 0.5.3 is released only after the 0.5.2 check; c2 and c3 ship as "Checkpoint content" edits in SKILL.md within 0.5.3.
- c1 changes `~/.claude/estimates/pipeline/` only; `RUN.md` step 4 runs the test.
- Pitstop must not start when it can break work in progress (Matteo's comment, F1–F3).

## Ruled out
- Wait another week for the 0.5.2 check: the trigger is already reached and T1–T4 are blocked on it.
- Keep the two guards in `classes.py` only: `backtest.py` can still crash on the next truncated digest.

## Comments
- Matteo: "vorrei che ci assicurassimo che un pitstop non parta se dei sub agents stanno lavorando … oppure se c'è una scelta in waggle e poi non la va a riprendere … Capiamo se effettivamente questo è il caso e se è il caso cerchiamo di capire come gestirlo al meglio." → copied word for word to `docs/feedback/2026-11-23-pitstop-quando-non-partire.md` (F1–F3); task S1 below investigates, task S2 fixes only if S1 finds real cases.

## Open questions
- If S1 finds real cases: the fix (hook check, skill rule, or both) goes to Matteo only if it changes what he sees; otherwise it ships in 0.5.3 with the twin-test gate.

## Sources
- Case c_67448f93-474b-4488-b30a-27e948691afe.
- `~/.claude/setup-review/runs/2026-11-23/report.md`, `brief.json`.
- `~/.claude/pitstop/reviews/20261123-030147/findings.md`.
- `docs/decisions/2026-11-16-weekly-setup-review.md` (T1–T4), `docs/decisions/2026-11-19-check-0-5-2-numbers.md`, `docs/twin-tests.md`.

## Tasks
Order: E1 (independent), S1 → S2, then C1 → T1–T4 + R1 + R2 → REL.

### E1 · one measured-units query in the estimates pipeline
From: Question 4, "use one query in classes.py and backtest.py that removes units without start or hours, and add a test".
- A single query or view (e.g. `units_measured`) in `~/.claude/estimates/pipeline/` drops units with `start` null or hours null; `classes.py` and `backtest.py` both read it.
- The local guard added on 2026-11-13 at `classes.py:184` is removed or reduced to the shared query.
- A test with a fixture unit with `start: null` passes, and fails on the old code.
- `RUN.md` step 4 runs the test; one full step 4 runs with no error.

### S1 · did pitstop start during subagent work or an open Waggle choice?
From: Comments, F1–F2.
- Search the cycle files of the last two review bundles and `~/.claude/pitstop/log.jsonl` for checkpoints written while an `Agent`/`delegate_task` was running, or while a `waggle_ask` was pending.
- For each case found: cycle id, what broke (lost result, lost answer, duplicate work) or "no harm".
- Findings written to `docs/feedback/2026-11-23-pitstop-quando-non-partire.md` under F1 and F2, with status.

### S2 · stop pitstop when work is in progress (only if S1 finds cases)
From: Comments, F3; Constraints, last line.
- The hook or `mark-pending` refuses (or the skill skips with `background-tasks`) when a subagent or background task is running, and when a Waggle case is open without a recorded answer path in the checkpoint.
- A unit test per case.
- If S1 finds no case: F3 closed as "not needed" with the evidence.

### C1 · 0.5.2 check with the twin test
From: Question 1 (c4).
- 30-cycle twin test run as in `docs/twin-tests.md`, on the wer-team account; cost logged (estimate ~120 USD).
- Result vs 0.5.1 written in a new `docs/decisions/` record, with the report lines.

### T1–T4 · as written in `2026-11-16-weekly-setup-review.md`
From: Question 1 (c4). Acceptance criteria: those in that record.

### R1 · checkpoint rule for artifacts (c2)
From: Question 2.
- "Checkpoint content" in `skills/pitstop/SKILL.md` gets: "Exact strings: absolute path or exact command of every script, command, draft or data the work made or relies on; copy what exists only in chat, an attachment or a temp folder."

### R2 · checkpoint rule for mockup and feedback ledger (c3)
From: Question 3.
- "Checkpoint content" gets: "Name the approved mockup (path + Waggle case id) and the feedback ledger file with its open ids when the work follows them."

### REL · release 0.5.3
From: Question 1, "then release 0.5.3 with T1–T4 (and c2, c3)".
- Twin test on the 0.5.3 text is not worse than 0.5.2 (Constraints, line 1).
- Tests pass (`/usr/bin/python3 -m unittest discover -s tests -t .`).
- Publish and push need Matteo's go-ahead in Waggle (outward-facing).
