# 0.5.2 check: twin test on 29 main sessions

Decided: 2026-11-23 · Case: c_67448f93-474b-4488-b30a-27e948691afe (c4, task C1)

## Question and choice
Is 0.5.2 worse than before? Checked with the 30-cycle twin test (`docs/twin-tests.md`, run of 2026-11-23).
Result: pitstop still beats native compact on every line; against the 0.5.0 run (the last one; no twin test ran
on 0.5.1) its lead on the next action is smaller. This run is the baseline that 0.5.3 must not fall below.

## Numbers (P = pitstop, N = native compact)
| | 0.5.0 (10 sessions, 2026-11-10) | 0.5.2 (29 sessions, 2026-11-23) |
|---|---|---|
| P better first reply | 8 / 10 (80%) | 18 / 29 (62%) |
| Next action yes, P / N | 70% / 30% | 48% / 28% |
| Owed replies dropped, P / N | 1 of 8 / 2 of 8 | 1 of 23 / 6 of 23 |
| Wrong claims per session, P / N | 0.7 / 0.9 | 0.66 / 1.21 |
| Missing details per session, P / N | 1.9 / 2.9 | 2.2 / 2.7 |
| Cost | USD 40.42 | USD 123.22 |

## Why
- 2026-11-13 review policy: one check of 0.5.2 at ~30 cycles with a 30-cycle twin test.
- The 0.5.0 run had 10 sessions from one day; the 0.5.2 run has 29 from 2026-11-20 to 23. The drop in "P better"
  (80% → 62%) is within what 10 sessions can show by chance (ipotesi); owed replies and wrong claims improved.

## Constraints
- Run with `CLAUDE_CONFIG_DIR=~/.claude-wer-team` (2026-11-19). Script: an adapted copy of
  `docs/superpowers/research/twin.py` (version filter, main sessions only, account override), not committed.
- Known leak: 2 of the 11 N wins come from P reading files written after the cut.

## 0.5.3 against this baseline (same cycles, 27 graded)
| P | 0.5.2 | 0.5.3 |
|---|---|---|
| Next action yes / no | 14 / 2 | 15 / 2 |
| Owed replies dropped | 1 of 22 | 2 of 21 |
| Wrong claims | 15 | 16 |
| Missing details | 57 | 54 |
| Better than N | 18 | 15 (2 ties) |

Not worse on P's own numbers; the wins move because N also changed (next action yes 7 → 10). Cost USD 118.62.
Release (REL) waits for Matteo's go-ahead in Waggle.

## Open questions
- Threshold for "worse" in later reviews (2026-11-19 record): proposed, P's next-action-yes share not more than
  10 points below this baseline and owed replies dropped not above 2 of 23 (ipotesi, for Matteo).

## Sources
- `~/.claude/pitstop/twin/check-052-20261123/summary.md` and per-cycle JSON; `docs/twin-tests.md`.
