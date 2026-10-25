---
name: pitstop
description: Use when the user types /pitstop (on, off, off here, now, status, notify on, notify off, metrics on, metrics off, report, gap) or when a "[pitstop]" hook message asks for a pitstop. Saves a checkpoint, then restarts from it: after /clear in the terminal, after /compact in T3 Code and other SDK hosts.
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
| `/pitstop gap <what was missing>` | `pitstop gap "<what was missing>"` | Show the output line. |
| `/pitstop now` | Follow "Manual pitstop". | |

A command that exits non-zero prints `🔋 pitstop · <reason>`: show that line to the user and stop.

## Automatic pitstop

A `[pitstop]` hook message gives you: mode, context, cwd, background tasks, and the step before the next request.

1. **When.** Mode `conversation`: now. Mode `superpowers`: finish the current step up to the boundary named in
   the message, then come back here before starting anything new.
2. **Exceptions.** Skip the pitstop when any of these applies (its category in brackets):
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
     `mcp__t3-code__t3_thread_configuration` and `mcp__t3-code__t3_thread_send` exist (load them with ToolSearch
     if they are deferred):
     1. Call `t3_thread_configuration` without `threadId`: it returns this thread's id.
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
## Next action
<one precise action>
## Chat-only text
<word for word, or the path of a support file, or —>
## Decisions made
- <decision> — <reason>
## User preferences
- "<exact quote>"
## Discarded
- <option> — <why>
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
