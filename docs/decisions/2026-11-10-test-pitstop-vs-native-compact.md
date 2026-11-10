# How do we test pitstop against the native compact?

Decided: 2026-11-10 · Case: c_fe969015-4526-49ec-89c8-f2241df023db

## Question and choice
What does a control session do, and which sessions go to the control arm?
- Control arm: "Same time, plain compact". Pitstop triggers at the same threshold and boundary, but restarts with a plain /compact and no checkpoint.
- Split: "1 in 2" was picked, but Matteo then changed the setup: his sessions are not used as control. He always works with pitstop. Claude runs the native-compact arm on its own sessions, built to match his.

## Why
- Matteo: "Ci interessa principalmente se con l'auto compact si perdono dettagli di valore che poi non vengono recuperati - cosa che in teoria Pitstop dovrebbe evitare."
- Matteo: "Il timing non mi interessa molto."
- Matteo: "vorrei evitare di usare le mie sessioni come test [...] per l'autocompact ti consiglio di creare te nuove sessioni simili a quelle che faccio io, se non uguali [...] non voglio lavorare con l'autocompact, preferisco che lo usi te per fare i test."
- Claude: twin sessions can be exact copies. A transcript cut before the pitstop turn, saved under a new session id, resumes with `claude -p --resume <id>` and accepts `/compact`. Checked on 2026-11-10 with a 57-line copy: one `compact_boundary` was written, the copy was then deleted.

## Constraints
- Matteo's working sessions always run with pitstop. No random split on his sessions.
- Twins never write to his repos, push, or call outward tools (Waggle, GitHub, MCP): read-only tools only.
- Pitstop is off in every twin (`pitstop off-here --session <twin id>`), so pitstop data stays clean.
- Twins are deleted after the run. Only the results stay.
- The main measure: details of value lost in the restart and not recovered after it.

## Ruled out
- Full off, native autocompact near the window limit: Matteo does not care about timing, and it needs many more days.
- Three arms: twice the time for the timing question, which is out of scope.
- Random split of Matteo's sessions ("1 in 2"): Matteo does not want to work with autocompact.
- Manual off-here in sessions Matteo chooses: same reason.

## Comments
- "dimmi te se ci sono altre cose interessanti da capire". Added to the design: resume size and cost per arm; how often the native summary recovers details on its own from the transcript; and the same twin harness to test new checkpoint rules (for example the P3 reply fix) before a release.

## Open questions
- Budget for the run (each twin compacts about 200K tokens). Goes in the spec with an estimate.
- Number of cycles in the sample (proposal: 30 recent 0.5.0 cycles, code and other).

## Sources
- Case c_fe969015-4526-49ec-89c8-f2241df023db; design draft sent with the ask ("Test design").
- Scan of `~/.claude*/projects/*/*.jsonl`: 749 manual and 3 auto `compact_boundary` entries, from October 2026.
- `~/.claude/pitstop/reviews/20261110-163603/findings.md` (0.5.0 review).
