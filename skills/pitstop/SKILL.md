---
name: pitstop
description: Use when the user types /pitstop (on, off, off here, now, status, notify on, notify off, metrics on, metrics off, report, review, gap) or when a "[pitstop]" hook message asks for a pitstop. Saves a checkpoint, then restarts from it: after /clear in the terminal, after /compact in T3 Code and other SDK hosts.
---

# pitstop

pitstop keeps the context small but complete. Past the threshold it saves a checkpoint at a clean point, then
restarts from it. In the terminal it tells you to run `/clear`, and the first message after that resumes from the
checkpoint. In T3 Code and other SDK hosts, where `/clear` does not exist, it compacts the conversation at the end
of the turn and queues a resume message right after it, so the compacted session resumes from the checkpoint by
itself.

CLI, always with this interpreter and this path:

```bash
/usr/bin/python3 "${CLAUDE_PLUGIN_ROOT}/bin/pitstop" <command>
```

Below, `pitstop <command>` means that full command. A `[pitstop]` hook message also names the CLI path on its
`cli:` line; when it does, use that one.

In the `/` menu this skill appears as `/pitstop:pitstop`. Below, `/pitstop <cmd>` also means `/pitstop:pitstop <cmd>`.

## Commands

| User types | Run | Then |
|---|---|---|
| `/pitstop` or `/pitstop status` | `pitstop status` | Show the output as is. |
| `/pitstop on` | `pitstop on` | Show the output line. |
| `/pitstop off` | `pitstop off` | Show the output line. |
| `/pitstop off here` | `pitstop off-here` | Show the output line. |
| `/pitstop notify on` · `/pitstop notify off` | `pitstop notify on` · `pitstop notify off` | Show the output line. |
| `/pitstop metrics on` · `/pitstop metrics off` | `pitstop metrics on` · `pitstop metrics off` | Show the output line. |
| `/pitstop report` | `pitstop report` | Show the output as is. |
| `/pitstop review` | Follow "Review". | |
| `/pitstop gap <what was missing>` | `pitstop gap "<what was missing>"` | Show the output line. |
| `/pitstop now` | Follow "Manual pitstop". | |

A command that exits non-zero prints `🔋 pitstop · <reason>`: show that line to the user and stop.

## Automatic pitstop

A `[pitstop]` hook message gives you: mode, context, cwd, background tasks, and when the next request comes.

1. **When.** Mode `conversation`: now. Mode `superpowers`: finish the current step up to the boundary named in
   the message, then come back here before starting anything new.
   - `mode: offer` (the soft zone, before the threshold): Pitstop only at a natural boundary (a task done, a commit made, an answer finished). Otherwise carry on and print nothing: an offer is not a request and needs no skip line.
   - `mode: hard` (past the hard limit): No exceptions except [background-tasks]. Run the "Checkpoint procedure" now.
     If subagents or background tasks are running, skip with category `background-tasks`; the request comes back.
2. **Exceptions** (modes `conversation` and `superpowers`). Skip the pitstop when any of these applies (its
   category in brackets):
   - a debugging session is half-way (discarded hypotheses and observed output live only in this context)
     [`debugging`];
   - you are fine-editing a long text you already read (you need the exact text) [`fine-editing`];
   - the work ends within about ten exchanges [`ending-soon`];
   - subagents or background tasks are still running [`background-tasks`];
   - a brainstorming or grilling session is half-way [`brainstorming`];
   - another reason [`other`].

   When in doubt, skip. To skip, print exactly this line and carry on normally:
   `🔋 **pitstop** · skipped: <category> — <reason>`
   `<category>` is one of the six above, as written; `<reason>` is a few words of your own.
3. Otherwise run the "Checkpoint procedure" with `--cwd <cwd from the message>`.

## Manual pitstop

`/pitstop now`: no exceptions, the user asked. Run the "Checkpoint procedure" now, without `--cwd`.

## Checkpoint procedure

1. Write and register the checkpoint (see "Checkpoint content") in one Bash call, with the text in a quoted
   heredoc so the shell leaves it untouched:

   ```bash
   pitstop mark-pending --stdin --kind <code|other> [--cwd <cwd>] [--plan <plan path>] <<'PITSTOP_EOF'
   <the checkpoint>
   PITSTOP_EOF
   ```

   - `--kind code` when the state of the work lives in the repo's files; `--kind other` for research, writing
     and strategy.
   - `--cwd <cwd>` for an automatic pitstop; `--plan <plan path>` when a superpowers plan is being executed.
   - If it exits non-zero because files under "Re-read" were not found, fix those entries and run it once more.
     A `warning: not checked under Re-read` line is only a notice: carry on.
   - Any other non-zero exit, or a second failure: print `🔋 **pitstop** · failed: <its reason> → continuing here`
     and stop the procedure.

   Fallback, if the heredoc is refused or a support file must sit next to the checkpoint: run
   `pitstop new-checkpoint` (it prints the path P), write any support file as `<P without .md>-chat.md`, write
   the checkpoint to P with the Write tool, then run `pitstop mark-pending --checkpoint P` with the same flags.
   If the write fails or is refused, print `🔋 **pitstop** · failed: checkpoint not written → continuing here`
   and stop the procedure.
2. Print the last line of its output (`🔋 **pitstop** · done at …`) as a line of its own.
3. Restart, following mark-pending's `restart:` output line. N is the window from its `resume window: N minutes`
   line.
   - **`restart: clear`** (terminal). Print, as the last line of your reply:
     `Run /clear, then send any message (for example "resume"): I'll pick up from the checkpoint within N minutes.`
     Then end your turn. Do not call `mcp__ccd_session_mgmt__clear_session`: the desktop app drops the clear it
     queues.
   - **`restart: auto`** (terminal or `claude -p`, where Claude Code has loaded pitstop's hooks module). Print, as the last
     line of your reply:
     `Compacting the conversation at the end of this turn, then resuming from the checkpoint on my own.`
     Then end your turn. Queue nothing and do not run `/compact` yourself: the module does both when the turn
     ends.
   - **`restart: compact`** (T3 Code and other SDK hosts: `/clear` does not work there). If the tools
     `mcp__t3-code__t3_thread_configure` (older T3 Code: `t3_thread_configuration`) and
     `mcp__t3-code__t3_thread_send` exist (load them with ToolSearch if they are deferred; search `t3_thread_config`
     to match either name):
     1. Call whichever of `t3_thread_configure` / `t3_thread_configuration` exists, without `threadId`: it returns
        this thread's id.
     2. Call `t3_thread_send` with that `threadId`, `mode: "queue"` and, as `message`, exactly the text after
        `queue 1: ` in mark-pending's output (today `/compact One-line summary: "Resume from the pitstop checkpoint."`).
        T3 Code runs it as soon as this turn ends; the compacted session receives the checkpoint by itself.
     3. Only if step 2 succeeded, call `t3_thread_send` again with the same `threadId`, `mode: "queue"` and, as
        `message`, exactly the text after `queue 2: ` (today `Resume from the pitstop checkpoint.`).
        T3 Code delivers queued messages in order, so this one starts the first turn after the compaction and
        the session resumes without the user typing anything. Never skip it: without it the session waits for
        the user.
     4. Print, as the last line of your reply:
        `Compacting the conversation at the end of this turn, then resuming from the checkpoint on my own.`
        If step 3 failed, print instead:
        `Compacting the conversation at the end of this turn: then send any message (for example "resume") and I'll pick up from the checkpoint.`
        Then end your turn.

     Never queue this `/compact` outside this step: a hook refuses it when the session has no registered
     checkpoint. If those tools do not exist or a call fails, print instead, as the last line of your reply:
     `Press Compact context (or type /compact One-line summary: "Resume from the pitstop checkpoint."): I'll pick up from the checkpoint within N minutes.`
     Then end your turn.

   The restarted session receives the checkpoint by itself: do not paste it anywhere else.

## Checkpoint content

Markdown, at most about 4K tokens. The section titles stay in English, whatever the language of the conversation
(pitstop checks and measures them); what you write under them follows the conversation. It points to files and
artifacts and never summarizes them. Text that exists only in the conversation is the exception: it goes under
"Chat-only text".

```markdown
# pitstop checkpoint — <session topic>

## Goal
## Current state
Last reply to the user: SENT | NOT SENT (if NOT SENT, it goes word for word under Chat-only text)
## Next action
<one precise action>
## Chat-only text
<word for word, or the path of a support file, or —>
## Decisions made
- <decision> — <reason> (over <option>, when that option may come back)
## User preferences
- "<exact quote>"
## Re-read
- `path/to/file:line` — <why the next action needs it>
## Unsaved or uncommitted work
## Open questions
## Suggested skills
```

- Quote user preferences word for word.
- Cite files as `path:line`; name specs, plans, ledgers and PRs by path or URL.
- Superpowers: point to spec, plan, ledger and workspace; name the current task and the open decisions. Do not restate them.
- Chat-only text, never left out: text the next action needs that no file holds (a table or list the user
  pasted, figures, sources or examples given in chat, your last answer when the next action builds on it) goes
  in word for word. If it is too long, save it to a support file next to the checkpoint (see the fallback in
  "Checkpoint procedure") and cite that file. Never replace it with a description. Write `—` only when there is
  none. With `--kind other` (research, writing, strategy) most of the state lives here: fill it first.
- For --kind other the state lives in the chat: put the tables, lists, figures and sources the next action needs under "Chat-only text" word for word, and when they pass about 1K tokens save them to a support file and cite it.
- Exact strings the remaining work needs (commands that worked, ids, model names, paths, error text, the option
  texts of a choice the user made) go word for word, never as a description.
- Mark with `(assumed)` a fact you did not check in a file, a command output or the user's words.
- Leave out secrets, tokens, passwords and personal data.
- Write `—` under an empty section.

## Resuming

The first message after `/clear` (any text), or the compacted session after `/compact`, arrives with a
`[pitstop]` checkpoint; follow the steps in that message: re-read only the cited files the next action needs,
print `🔋 **pitstop** · resumed from <K> · Where we were:` with three short lines (goal, state, next action), then
continue. If something is missing, look for it in the transcript the message names ("Transcript before the
restart": Grep it, then Read around the match with an offset), recover it, then run
`pitstop gap "<what was missing>"`.

If the checkpoint had already expired (past the resume window but under 24 hours old), that first message
instead carries a one-line notice with its path; answer normally and, only if the user later asks to resume from
the checkpoint, read that file and follow these same steps.

## Review

`/pitstop review`: check whether past checkpoints kept what the resumed sessions needed, and propose changes.
This is the only pitstop command that spends tokens.

1. Run `pitstop review-bundle` (it refreshes the report first) with a Bash timeout of 600000 ms: the first
   report, without `metrics.jsonl`, reads every transcript and can take minutes. Show the report lines as is.
   If it exits non-zero, show its `🔋 pitstop · <reason>` line and stop.
2. Read each cycle file it lists. Each holds the chat before the restart, the checkpoint, and the chat after the
   resume. For each cycle, judge what the work after the resume needed that the checkpoint did not keep.
   Evidence counts only when it is in the file: the resumed session re-reads the old transcript, asks the user
   for something already said, redoes work, or contradicts a decision made before the restart. Also note the
   checkpoint parts that the resume never used. A cycle with no problem gets "nothing missing".
3. Write proposals. Each says what to change (a checkpoint content rule, or a number in `config.json`), the
   cycles that show it (cycle ids and a short quote), and the expected effect. No proposal without evidence from
   at least one cycle; a number proposal also cites the report lines. A content rule must be general: it names a
   failure seen in at least 3 cycles, or in 1 cycle with real harm (wrong data, lost work). A rule that fits one
   project or one wording is not proposed: write it as one line under "Not proposed" in `review.md`.
   No proposals: skip to step 6.
4. Ask; each proposal gets its own answer. With Waggle tools: one `waggle_ask`, one item per proposal, options
   approve and reject, with a markdown artifact holding the per-cycle findings. Without Waggle: list the
   proposals in chat and ask for a yes or no on each. Change nothing before the answer.
5. Apply only the approved ones. A number: `pitstop config <key> <value>` (if it exits non-zero, show its line
   and treat the proposal as not applied). A content rule: write it, with its evidence and the exact edit to
   "Checkpoint content" in this SKILL.md, to `review.md` in the bundle folder (the `bundle:` line) under
   "Approved rules"; it takes effect when that edit ships in a pitstop release. Write the rejected ones under
   "Rejected", with the reason given.
6. Run `pitstop review-done --bundle <bundle> --cycles <N> --approved <A> --rejected <R>` (N = cycles read,
   A and R = proposals approved and rejected; 0 when there were none) and print its output line:
   `🔋 **pitstop** · review: <N> cycles · <A> approved · <R> rejected`
