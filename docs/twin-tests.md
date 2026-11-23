# Twin tests: pitstop vs native compact

Every run that restarts the same real sessions both ways, with native `/compact` (N) and with the pitstop
checkpoint (P). The README shows the latest totals; this file keeps every run. Add each new run on top.

## Method

- **Sessions.** Real pitstop cycles from the author's log. Each transcript is cut just before the turn that wrote
  the checkpoint.
- **Twins.** Two copies of the cut session. N runs native `/compact`; P gets the checkpoint pitstop wrote at that
  point. Twins run with `claude -p`, no hooks, no MCP servers and read-only tools, and are deleted after the run.
- **Probe test.** Questions about the work before the restart, on details the real session used later (`used`)
  or that had value (`value`). An answer is correct, partly, wrong or unknown; lost = wrong + unknown.
- **Continuation test.** Both twins get the message that really came next. A grader (a model) sees the two first
  replies as X and Y, in random order, next to what the real session did, and picks the better one. It also
  checks whether an owed reply was sent, whether the next action is right (yes, partly, no), and counts wrong
  claims and missing details.
- **Snapshot.** From the second continuation run on, twins read the repo as it was at the cut (git archive plus
  untracked files under 1 MB older than the cut). Known leak: a twin can still read absolute paths of the live
  repo, and then may take a later state as the current one.
- **Limits.** Few sessions, all from the author; a model grades; tools are read-only, so a twin cannot redo work.
  The test script is not published yet.

## 2026-11-23 · continuation with snapshot · pitstop 0.5.3 (pre-release) · 27 sessions

The same cycles as the 0.5.2 check below, with the 0.5.3 resume message (reply language named, no banner for
delegates). 2 grader replies could not be parsed (18488bafbe98, 06afa47748c9), so 27. Per-cycle reasons:
`~/.claude/pitstop/twin/check-053-20261123/summary.md`.

| | N | P |
|---|---|---|
| Better first reply | 10 | **15** (2 ties) |
| Next action yes / partly / no | 10 / 15 / 2 | **15 / 10 / 2** |
| Owed replies dropped | **1 of 21** | 2 of 21 |
| Wrong claims | 24 | **16** |
| Missing details | 58 | **54** |
| Cost | USD 57.84 | USD 55.93 |

Total USD 118.62. On the same 27 cycles, P on 0.5.2 had: next action yes 14, no 2; owed replies dropped 1 of 22;
wrong claims 15; missing details 57. N changed more between the two runs (next action yes 7 → 10) than P did.

| Session | Kind | Context at pitstop | Winner | Next action N / P |
|---|---|---|---|---|
| 00f29c561d6d | code | 204K | P | partly / yes |
| 0cd23dc33b15 | code | 216K | N | yes / yes |
| 0d57eb504060 | code | 203K | P | partly / yes |
| 1c76ae642515 | code | 213K | P | yes / yes |
| 1ca7102838bc | code | 273K | P | partly / yes |
| 2bd3d04ebbde | other | 283K | N | partly / no |
| 382cb2050464 | code | 202K | P | partly / yes |
| 4338cf45596a | other | 204K | P | partly / yes |
| 4ee042c1fe55 | code | 204K | P | partly / yes |
| 4f5eb91defa0 | code | 209K | N | partly / partly |
| 50430f02b816 | code | 239K | N | partly / partly |
| 5f2ee0c10c52 | code | 230K | tie | yes / yes |
| 6d1adf8b029d | other | 222K | N | yes / yes |
| 8ec1e94bd8e5 | code | 184K | tie | partly / partly |
| 8ed4590401fd | code | 219K | P | yes / yes |
| 909c023c6ba1 | code | 207K | P | yes / yes |
| 951aa4a5589d | code | 190K | N | yes / yes |
| 9617f0c1098e | code | 210K | N | yes / partly |
| acc10a738547 | code | 220K | P | partly / partly |
| b0f51d24c649 | code | 223K | P | no / partly |
| b98700370b1d | other | 203K | N | yes / no |
| c8f28a50b7f8 | code | 181K | P | partly / partly |
| d9264f6258b9 | code | 205K | P | partly / yes |
| e1a094d07f2e | code | 209K | P | partly / partly |
| f2ccff5251ae | other | 202K | P | no / yes |
| f70a6f127d67 | code | 205K | N | yes / partly |
| f79f10e940c3 | code | 207K | N | partly / partly |

## 2026-11-23 · continuation with snapshot · pitstop 0.5.2 · 29 sessions (0.5.2 check)

Main sessions only (no T3 delegates), the 30 latest resumed 0.5.2 cycles (24 code, 6 other); one failed in the
snapshot copy (558be1dfb513, a missing file), so 29. Run with the wer-team account. Per-cycle reasons:
`~/.claude/pitstop/twin/check-052-20261123/summary.md`.

| | N | P |
|---|---|---|
| Better first reply | 11 | **18** |
| Next action yes / partly / no | 8 / 15 / 6 | **14 / 13 / 2** |
| Owed replies dropped | 6 of 23 | **1 of 23** |
| Wrong claims | 35 | **19** |
| Missing details | 77 | **64** |
| Cost | USD 60.26 | USD 57.72 |

Grading cost USD 5.24; total USD 123.22. Two N wins come from the snapshot leak (2bd3d04ebbde, e1a094d07f2e:
P read files written after the cut and took them as the current state).

| Session | Kind | Context at pitstop | Winner | Next action N / P |
|---|---|---|---|---|
| 00f29c561d6d | code | 204K | P | partly / yes |
| 06afa47748c9 | code | 189K | N | partly / partly |
| 0cd23dc33b15 | code | 216K | P | yes / yes |
| 0d57eb504060 | code | 203K | N | yes / partly |
| 18488bafbe98 | other | 287K | N | yes / partly |
| 1c76ae642515 | code | 213K | N | partly / partly |
| 1ca7102838bc | code | 273K | P | partly / yes |
| 2bd3d04ebbde | other | 283K | N | partly / no |
| 382cb2050464 | code | 202K | P | yes / yes |
| 4338cf45596a | other | 204K | P | partly / yes |
| 4ee042c1fe55 | code | 204K | P | no / yes |
| 4f5eb91defa0 | code | 209K | N | yes / yes |
| 50430f02b816 | code | 239K | P | partly / yes |
| 5f2ee0c10c52 | code | 230K | N | partly / partly |
| 6d1adf8b029d | other | 222K | N | yes / yes |
| 8ec1e94bd8e5 | code | 184K | P | partly / partly |
| 8ed4590401fd | code | 219K | P | no / partly |
| 909c023c6ba1 | code | 207K | P | yes / yes |
| 951aa4a5589d | code | 190K | P | no / yes |
| 9617f0c1098e | code | 210K | P | partly / yes |
| acc10a738547 | code | 220K | P | partly / partly |
| b0f51d24c649 | code | 223K | P | no / partly |
| b98700370b1d | other | 203K | P | no / yes |
| c8f28a50b7f8 | code | 181K | P | no / yes |
| d9264f6258b9 | code | 205K | N | partly / partly |
| e1a094d07f2e | code | 209K | N | yes / no |
| f2ccff5251ae | other | 202K | P | partly / partly |
| f70a6f127d67 | code | 205K | N | partly / partly |
| f79f10e940c3 | code | 207K | P | partly / partly |

## 2026-11-10 · continuation with snapshot · pitstop 0.5.0 · 10 sessions

| | N | P |
|---|---|---|
| Better first reply | 2 | **8** |
| Next action yes / partly / no | 3 / 6 / 1 | **7 / 2 / 1** |
| Owed replies dropped | 2 of 8 | **1 of 8** |
| Wrong claims | 9 | **7** |
| Missing details | 29 | **19** |
| Cost | USD 22.60 | USD 17.82 |

| Session | Kind | Context at pitstop | Winner | Next action N / P | Why |
|---|---|---|---|---|---|
| 077a91b7b371 | code | 283K | P | partly / yes | P resumed in a few lines with the two right next steps; N repeated a summary already sent. |
| 31f871e460a4 | code | 209K | P | partly / yes | P named the real next step and what it needed; N presented again a plan already delivered. |
| 47bb94167c91 | other | 188K | P | partly / yes | N proposed writing a plan that already existed. |
| 48a4890dcc22 | other | 232K | N | yes / yes | N kept more earlier context: mockup variants and an estimate already logged. |
| 547dbf70bfd7 | code | 212K | P | no / yes | N picked the wrong next task. |
| 5813dc857b7b | code | 208K | P | yes / yes | P recovered the exact edits the user had asked for. |
| 8c4e15a2a21b | code | 206K | P | partly / partly | P checked the real worktree and found an uncommitted record; N cited commits it had not checked. |
| 9581c0f6eb5f | code | 205K | P | yes / yes | Only P answered the two questions the user had left open. |
| cd475f610f47 | code | 183K | P | partly / partly | Both sent the owed report; P also kept the data limits, the mockup differences and the rest of the plan. |
| d1e270b83511 | code | 211K | N | partly / no | P read the live repo, took its later state as current and declared the work finished (snapshot leak). |

## 2026-11-10 · continuation · pitstop 0.5.0 · 5 sessions

| | N | P |
|---|---|---|
| Better first reply | 1 | **4** |
| Next action yes / partly / no | 0 / 3 / 2 | **2 / 2 / 1** |
| Owed replies dropped | 1 of 4 | **0 of 4** |
| Wrong claims | 11 | **5** |
| Missing details | 12 | **11** |
| Cost | USD 8.86 | USD 10.49 |

| Session | Kind | Context at pitstop | Winner | Next action N / P | Why |
|---|---|---|---|---|---|
| 0b376ba52169 | code | 205K | P | partly / yes | N took a later file state as current and would skip an owed decision record. |
| 4c6e709d6a37 | code | 284K | P | partly / yes | N misstated what an earlier draft covered and planned work already done. |
| b0e04a5d3fb6 | code | 172K | P | no / partly | N ended in an error during its tool calls and sent no reply. |
| d6ce053a8f44 | other | 186K | P | partly / partly | N invented files and claimed a message was sent without checking; P kept the real next steps. |
| d96ecc2b5662 | code | 272K | N | no / no | Both treated unfinished work as done; N recovered more of the real state. |

## 2026-11-10 · probes · pitstop 0.5.0 · 5 sessions, 40 questions

| | N | P |
|---|---|---|
| Lost (wrong + unknown) | 1 / 40 | **0 / 40** |
| Partly right | 3 | **2** |
| Answered by looking it up | 6 | 6 |
| Context after the restart (median) | 61K | 62K |
| Cost (restart + answers) | USD 10.02 | USD 10.05 |

| Session | Kind | Context at pitstop | Lost N / P | Context after restart N / P |
|---|---|---|---|---|
| 0b376ba52169 | code | 205K | 0 / 0 | 58K / 60K |
| 4c6e709d6a37 | code | 284K | 0 / 0 | 66K / 71K |
| b0e04a5d3fb6 | code | 172K | 1 / 0 | 61K / 62K |
| d6ce053a8f44 | other | 186K | 0 / 0 | 56K / 58K |
| d96ecc2b5662 | code | 272K | 0 / 0 | 62K / 65K |
