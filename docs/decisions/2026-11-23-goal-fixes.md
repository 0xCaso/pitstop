# Which changes bring pitstop toward the goal?

Decided: 2026-11-23 · Case: c_e68f6e0d-3194-40ea-be88-bd52391ae369

## Question and choice
The question: which changes to make after the A1 analysis of the 0.5.4 twin run? Chosen, all six:
- "Copia di prova completa" (env)
- "Chiudo la fuga dei worktree" (leak)
- "Riprovo se claude -p fallisce" (retry)
- "Resume: nomina i dati aperti" (resume)
- "Checkpoint: temi delle domande" (ckpt)
- "Misuro 'P non perde'" (metric)

## Why
The A1 analysis (local, per cycle) found that 17 of 27 0.5.4 cycles were not perfect for P:
- environment of the copy: 12 (other repos, scratchpads, network, preview tools, uncommitted work missing);
- resume did not use the checkpoint: 4;
- checkpoint lacked the fact: 2;
- leak through a copied worktree: 1;
- `claude -p` error: 1.

6 of P's 7 wrong claims came from the environment or the leak. A win rate near 100% is out of reach because two
right replies get a tie. Goal from `docs/feedback/2026-11-23-0-5-4-non-basta.md` (H2–H5).

## Constraints
- Test changes must not give a twin any state from after the cut.
- The pitstop changes go in 0.5.4; there is still no release before an author decision (H1).
- After the changes, 0.5.4 runs again on the same 27 cycles (about USD 120, stima).

## Ruled out
- Not chosen: any subset. All six were picked.

## Comments
none

## Open questions
none

## Sources
- Case c_e68f6e0d-3194-40ea-be88-bd52391ae369.
- `docs/twin-tests.md` (0.5.4 run), `docs/decisions/2026-11-23-no-release-0-5-4.md` (A1, A2).

## Tasks

### E1 · Copy every outside folder read before the cut
- Criteria:
  - the snapshot holds the outside folders from every tool call before the cut, not only the last 50;
  - files newer than the cut stay out;
  - test in `tests/test_twin.py`.
- From: Question and choice, "Copia di prova completa" (env).

### E2 · Close the worktree leak
- Criteria:
  - a copied git worktree or repo in `_ext/` has no `.git` file or link that points outside the snapshot;
  - `git log --all` in the copy shows no commit after the cut;
  - test.
- From: Question and choice, "Chiudo la fuga dei worktree" (leak).

### E3 · Retry a failed arm once
- Criteria:
  - an arm whose `claude -p` exits non-zero with no reply runs once more;
  - the result records `retried`;
  - test.
- From: Question and choice, "Riprovo se claude -p fallisce" (retry).

### E4 · "P does not lose" metric
- Criteria: the summary and `docs/twin-tests.md` show P wins + ties out of the cycles.
- From: Question and choice, "Misuro 'P non perde'" (metric).

### E5 · Resume names open data and checks before "done"
- Criteria:
  - the resume message tells the first reply to name the open Waggle cases and the files still to update from the
    checkpoint;
  - it says not to state that a check passed or a thing is done without a check in this session;
  - test in `tests/claude/test_messages.py`.
- From: Question and choice, "Resume: nomina i dati aperti" (resume).

### E6 · Checkpoint keeps the topic of each open question
- Criteria:
  - a SKILL.md rule under Checkpoint content says each open question or Waggle case gets its topic, and the last
    step gets its exact numbers;
  - plugin test still passes.
- From: Question and choice, "Checkpoint: temi delle domande" (ckpt).

### E7 · Run 0.5.4 again
- Criteria:
  - same 27 cycles, new folder;
  - results in `docs/twin-tests.md` next to the 0.5.2 baseline;
  - report against H2–H5, sent in Waggle.
- From: Constraints, "After the changes, 0.5.4 runs again on the same 27 cycles".
