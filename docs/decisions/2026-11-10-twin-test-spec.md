# Do you approve the twin test spec?

Decided: 2026-11-10 · Case: c_fdb661a1-1cd7-4e82-8c0c-3d7b70350085

## Question and choice
Spec: `docs/superpowers/specs/2026-11-10-twin-compact-test.md`.
- Method: "Approve". Both arms start from the same cut of the session and differ only in the checkpoint.
- Measure: "Approve". 8 probes per cycle, a blind grader, and the main number is details lost and not recovered.
- Sample and budget: "5-cycle pilot first". Run 5 cycles (about USD 17, estimate), check the harness, then the other 25.
- Code location: "Approve". A research script in `docs/superpowers/research/twin.py`, not shipped.

## Why
- The arms differ only in what pitstop adds, so the test is fair.
- The probes measure Matteo's question: a detail of value lost and not recovered.
- The cut and the twin restart are new code. A cheap pilot protects the full run.

## Constraints
- Stop after the pilot and show the results before the other 25 cycles.
- Twins run without hooks or MCP servers, with read-only tools, and are deleted after the run.

## Ruled out
- Changes to the method or the measure: not asked.
- 30 cycles at once: the pilot comes first.
- 15 cycles: shows only large differences.
- A command in the pitstop package: first we learn if the harness is useful.

## Comments
none

## Open questions
- Whether to run the other 25 cycles: decided after the pilot.

## Sources
- Case c_fdb661a1-1cd7-4e82-8c0c-3d7b70350085.
- `docs/superpowers/specs/2026-11-10-twin-compact-test.md`.
- `docs/decisions/2026-11-10-test-pitstop-vs-native-compact.md`.
