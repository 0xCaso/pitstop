# Is this README text about pitstop vs auto-compact correct?

Decided: 2026-11-13 · Case: c_e72af5aa-e933-4721-b2e2-6b0f645b6e32

## Question and choice
Three points on the new README text that says why to use pitstop instead of Claude Code auto-compact, with the
twin test results.
1. Text: "Approve the text. I add it to the README, add docs/twin-tests.md, and open a PR."
2. Where results go: "A short table in the README, and all runs per session in docs/twin-tests.md. A line in the
   project CLAUDE.md says: after each twin run, update both."
3. Safety-net line: "Keep the line. Also make pitstop status show a warning when the auto-compact limit is below
   the pitstop threshold."

## Why
- Matteo wants the README to state the positioning of pitstop and all its pros over auto-compact, and to report
  the twin tests already run, kept up to date after new ones.
- Public posts (Oct 2026) made `/autocompact 400k` the common tip: the README must say what pitstop adds beyond a
  lower limit. Each number in the text has a source; the text also says where both are equal (restart size).
- A user who follows the tip with `/autocompact 200k` sets native compact below the pitstop threshold, so it can
  run before the checkpoint.

## Constraints
- Every number in the README links to its source or to `docs/twin-tests.md`.
- The README states the limits of the tests: 15 sessions, all from the author, a model as grader, read-only twins.
- The README table shows the latest run; `docs/twin-tests.md` keeps every run.
- The context chart is not changed here (it needs a pen.dev mockup first, project CLAUDE.md).

## Ruled out
- Request changes on the text: not chosen.
- README only for results: history of runs and per-session reasons would be lost.
- Safety-net line as text only, or removed: a warning in `pitstop status` catches the conflict where users look.

## Comments
none

## Open questions
none

## Sources
- Case c_e72af5aa-e933-4721-b2e2-6b0f645b6e32; draft sent as artifact "README draft".
- `~/.claude/pitstop/twin/pilot-20261110/summary.md`, `cont-20261110/summary.md`, `cont2-20261110/summary.md`.
- https://x.com/lydiahallie/status/2108624109538291901, https://x.com/rohit3a/status/2108277836285161798.
- Claude Code 2.1.323 settings schema: `autoCompactWindow`, tokens 100000 to 1000000 or "auto"; `/autocompact` saves it.

## Tasks
1. README sections. Criteria: "pitstop vs auto-compact" after "Why", "Tested against native compact" after
   "Limits", text as in the approved draft; links resolve. From: "Approve the text. I add it to the README…"
2. `docs/twin-tests.md`. Criteria: method; one section per run (pilot, continuation 5, continuation 10 with
   snapshot) with date, version, sessions, totals, per-session winner and reason. From: "all runs per session in
   docs/twin-tests.md".
3. Project `.claude/CLAUDE.md` line. Criteria: "After a twin test run, add it to docs/twin-tests.md and update the
   README table." From: "A line in the project CLAUDE.md says: after each twin run, update both."
4. Status warning. Criteria: `pitstop status` prints a warning line when an `autoCompactWindow` number in the
   user or project settings is below `threshold_tokens`; nothing when unset or "auto"; unit tests. From: "make
   pitstop status show a warning when the auto-compact limit is below the pitstop threshold."
5. PR as 0xCaso with the README text as proof (docs) and test output (status).
