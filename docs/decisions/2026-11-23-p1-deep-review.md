# What keeps pitstop from perfect, and what changes in 0.5.4

Decided: 2026-11-23 · Case: c_88978c47-76e8-41b7-8d19-4c991f62b1d5 (task P1 of `2026-11-23-release-0-5-3.md`)

## Question and choice
Which of four changes to apply after the P1 review of the 56 graded twin cycles of 2026-11-23? Chosen: all four.
- A · "Sì, controlla": the resume text drops "Do not re-explore". Before the first reply the session reads the files
  the next action depends on (a ledger with open ids, state files, the pending case). It never calls something
  missing or confirmed after a single failed search.
- B · "Sì, nuova regola": each count or status under Current state names its source and time and says when it is
  partial; two runs are never merged into one line.
- C · "Sì, avviso": `mark-pending` prints a warning (it does not refuse) when a `docs/feedback/*.md` under Re-read is
  older than the last user message.
- D · "Sì, cambio il grader": a missing detail counts only if the real session used it in its next steps and the
  arm neither states it nor shows it has it. The 0.5.2 baseline is graded again with the new rubric.

## Why
Causes of P's errors (full table, per cycle, kept outside the repo because it quotes private sessions:
`~/.claude/pitstop/twin/p1-20261123/analysis.md`):
- Wrong claims, 35: 19 from the harness (15 reads of files written after the cut, 2 grader, 2 missing snapshot
  folder), 5 from checkpoint content (merged runs, stale PR states, partial counts), 11 from the resume (claims on
  one search, guesses).
- N wins, 21: 8 from the harness (leak 4, turn limit 2, grader 1, snapshot 1), 13 because P read 0–2 files and
  trusted the checkpoint while N checked.
- Missing details, 118: 54 were in the checkpoint but not in the first reply, which is all the grader reads.
- Next action not "yes", 27: most say "read-only tools, I cannot run it"; owed replies dropped, 3: all harness.

## Constraints
- Each change ships with a test (A: resume text test; B: SKILL.md text test; C: CLI test) or a twin check (D).
- The next twin run must not be worse under the threshold in `2026-11-13-review-policy.md`.
- The harness fixes (P2) come before the next twin run, else the leak hides the effect of A–C.

## Ruled out
- A rule to copy standing account rules (gh account, commit identity) into the checkpoint: CLAUDE.md loads after
  every resume, so they were missing only inside the test.
- Keeping the grader as is: "missing details toward zero" would then reward longer first replies, not better resumes.

## Comments
—

## Open questions
- Whether the 0.5.3 arm received the checkpoint in two cycles where P gave no banner (H6): P2 checks it.

## Sources
- Case c_88978c47-76e8-41b7-8d19-4c991f62b1d5.
- `~/.claude/pitstop/twin/check-052-20261123/`, `check-053-20261123/`, `p1-20261123/`.
- Ledger `docs/feedback/2026-11-23-pitstop-verso-perfetto.md` (G1–G6).

## Tasks
### P2 · fix the twin harness
From: Why (harness causes), Constraints item 3.
- `twin.py` lives in a durable place (in the repo under `docs/superpowers/research/` or `scripts/`), with the
  version filter, main-session filter and account override.
- Arms cannot read outside the snapshot (a test cycle that asks for a live-repo path gets a refusal).
- Arms have write tools inside the snapshot and a stub Waggle server that records asks; no network, no push.
- Turn limit raised; a cycle with no final reply grades the last text.
- The grader prompt gets the cut time and "facts that appear only after the cut count neither for nor against".
- The snapshot includes the folders named in the checkpoint and the last 50 tool calls.
- Each arm's resume input matches a real resume of its version (H6 checked on 951aa4, 9617f0).

### P3a · resume checks before it states (A)
From: Question and choice, A.
- `resume_context` no longer says "Do not re-explore" and says to read the files the next action depends on and
  not to claim missing or confirmed after one failed search; test in `tests/claude/test_messages.py`.

### P3b · counts carry their source (B)
From: Question and choice, B.
- SKILL.md "Checkpoint content" has the rule; `tests/test_plugin.py` checks the text.

### P3c · ledger older than the last message (C)
From: Question and choice, C.
- `mark-pending` prints `warning: feedback ledger <path> older than the last user message` and exits 0; test in
  `tests/test_cli.py` for both cases (older, newer).

### P3d · grader rubric (D)
From: Question and choice, D.
- The grader prompt in `twin.py` uses the new rule for missing details; the 0.5.2 baseline is graded again on the
  same cycles and the new numbers go in `docs/twin-tests.md` as the baseline.

### TW · twin run of 0.5.4
From: Constraints item 2.
- Twin run on the same cycles, second account; not worse than the new baseline under the TH threshold.
