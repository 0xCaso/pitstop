# The twin pilot shows almost no loss with native compact. What next?

Decided: 2026-11-10 · Case: c_cbd486eb-95bf-4d53-9929-b20dc4bcbfeb

## Question and choice
Pilot (5 cycles, 40 probes): native compact lost 1/40, pitstop 0/40; both restart at about 61K. Next step?
Choice: "Continuation test: on the same 5 cycles, give both twins the real next message with read-only tools. A blind grader compares the first reply and next action with what really happened. About USD 10-15 (estimate)."

## Why
- The failures found in the reviews are silent: the resumed session does not know a reply is owed or a detail is missing, and nobody asks. Probes cannot see this.
- It is the cheapest next run.

## Constraints
- Same 5 cycles as the pilot: d96ecc2b5662, 0b376ba52169, 4c6e709d6a37, b0e04a5d3fb6, d6ce053a8f44.
- Twins as before: no hooks, no MCP servers, read-only tools, deleted after the run.
- Message to the twin: the first real user message after the resume. After an automatic pitstop that message is "Resume from the pitstop checkpoint."; for N the twin gets the same text without the checkpoint.

## Ruled out
- 25 more cycles with probes (about USD 105): it would most likely confirm "about equal when asked".
- Stop here: silent failures are not measured yet.

## Comments
none

## Open questions
- After the continuation test: run more cycles, or simplify pitstop.

## Sources
- Case c_cbd486eb-95bf-4d53-9929-b20dc4bcbfeb.
- `~/.claude/pitstop/twin/pilot-20261110/pilot-report.md`, `summary.md`.
