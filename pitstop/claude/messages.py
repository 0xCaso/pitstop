"""Everything pitstop says. All of it is English."""
import os
import re
import time
from typing import List, Optional

from pitstop.core.checkpoint import section
from pitstop.core.store import PendingRecord

NOTIFY_TITLE = "pitstop"
# The /compact the skill queues on its own thread in SDK hosts (T3 Code); the PreToolUse guard recognises it.
COMPACT_SUMMARY = "Resume from the pitstop checkpoint."
COMPACT_COMMAND = '/compact One-line summary: "%s"' % COMPACT_SUMMARY


def compact_queue_lines() -> list:
    """What the skill queues, in order, on its own thread in SDK hosts: the /compact, then the message that starts
    the first turn after it. Printed by mark-pending, because a session keeps the skill text it loaded first."""
    return [
        'queue: with t3_thread_send (mode "queue"), in this order:',
        "queue 1: %s" % COMPACT_COMMAND,
        "queue 2: %s" % COMPACT_SUMMARY,
    ]
BADGE = "🔋"


def k(tokens: int) -> str:
    return "%dK" % (tokens // 1000)


def banner_triggered(tokens: int) -> str:
    return "🔋 pitstop · %s → pitting at the next clean point" % k(tokens)


def banner_hard(tokens: int) -> str:
    return "🔋 pitstop · %s → past the hard limit, pitstop now" % k(tokens)


def banner_resumed(tokens: int) -> str:
    return "🔋 pitstop · resumed from %s" % k(tokens)


def banner_config_invalid(error: str) -> str:
    return "🔋 pitstop · off: invalid config.json → %s" % error


def banner_checkpoint_missing() -> str:
    return "🔋 pitstop · checkpoint not found, starting without it"


def banner_checkpoint_expired() -> str:
    return "🔋 pitstop · checkpoint expired, starting without it"


def review_reminder(cycles: int, gaps: int) -> str:
    return "🔋 pitstop · %d closed cycles and %d gaps since the last review → run /pitstop review" % (cycles, gaps)


def notify_triggered(tokens: int) -> str:
    return "Pitting at %s: checkpoint at the next clean point" % k(tokens)


def notify_resumed(tokens: int) -> str:
    return "Resumed from %s" % k(tokens)


def done_line(tokens: int) -> str:
    return "🔋 **pitstop** · done at %s → back on track with a clean context" % k(tokens)


def resumed_line(tokens: int) -> str:
    return "🔋 **pitstop** · resumed from %s · Where we were:" % k(tokens)


def badge_title(title: Optional[str]) -> Optional[str]:
    if not title or not title.strip():
        return None
    title = title.strip()
    return title if title.startswith(BADGE) else "%s %s" % (BADGE, title)


_SKILL_POINTER = (
    "Invoke the `pitstop` skill with the Skill tool (it may be listed as `pitstop:pitstop`; if it is not "
    "available, Read `{skill}`) and follow \"Automatic pitstop\" with these values:\n"
    "- mode: {mode}\n"
    "- context: {tokens} tokens ({k})\n"
    "- cwd: {cwd}\n"
    "- cli: /usr/bin/python3 {cli}\n"
    "- background tasks running: {background}\n"
    "- {skip}\n"
)


def _request_context(head: str, mode: str, tokens: int, threshold: int, step: int, cwd: str, cli: str,
                     skill: str, background_tasks: Optional[int],
                     skip: str = "if you skip, the next request comes at the {hard} hard limit", hard: int = 0,
                     soft: int = 0) -> str:
    background = "unknown, check yourself" if background_tasks is None else str(background_tasks)
    values = dict(k=k(tokens), threshold=k(threshold), hard=k(hard), soft=k(soft), tokens=tokens, step=step,
                  cwd=cwd, cli=cli, skill=skill, background=background, mode=mode)
    return (head + _SKILL_POINTER.replace("{skip}", skip)).format(**values)


def offer_context(tokens: int, soft: int, threshold: int, cwd: str, cli: str, skill: str,
                  background_tasks: Optional[int] = None) -> str:
    head = ("[pitstop] Main-thread context is {k}, in the soft zone ({soft}–{threshold}). Pitstop only if the work "
            "is at a natural boundary right now and more work is left; otherwise carry on and print nothing.\n")
    return _request_context(head, "offer", tokens, threshold, 0, cwd, cli, skill, background_tasks,
                            skip="if you carry on, the request comes at the {threshold} threshold", soft=soft)


def hard_request_context(tokens: int, hard: int, step: int, cwd: str, cli: str, skill: str,
                         background_tasks: Optional[int]) -> str:
    head = ("[pitstop] Main-thread context is {k}, past the {hard} hard limit. Pitstop now. Skip only if subagents "
            "or background tasks are running (category background-tasks), or the work is done (category done).\n")
    return _request_context(head, "hard", tokens, hard, step, cwd, cli, skill, background_tasks,
                            skip="if you skip, the request comes again at the end of this turn, and after +{step} "
                                 "tokens during it", hard=hard)


def stop_request_context(tokens: int, threshold: int, step: int, cwd: str, cli: str, skill: str,
                         background_tasks: Optional[int], *, hard: int) -> str:
    head = "[pitstop] Main-thread context is {k}, over the {threshold} threshold. Pitstop now, at this clean point.\n"
    return _request_context(head, "conversation", tokens, threshold, step, cwd, cli, skill, background_tasks,
                            hard=hard)


def batch_request_context(tokens: int, threshold: int, step: int, cwd: str, cli: str, skill: str,
                          background_tasks: Optional[int], *, hard: int) -> str:
    head = (
        "[pitstop] Main-thread context is {k}, over the {threshold} threshold. Pitstop at the next clean boundary, "
        "not in the middle of a step.\n"
        "Boundaries: subagent-driven-development = current task reviewed and ledger updated; brainstorming = spec "
        "written; writing-plans = plan written; before the final review; outside superpowers = end of the current "
        "step. At the boundary, do the pitstop before starting anything new.\n"
    )
    mode = "superpowers if a superpowers spec, plan or ledger is in use, otherwise conversation"
    return _request_context(head, mode, tokens, threshold, step, cwd, cli, skill, background_tasks, hard=hard)


def auto_compact_warning(window: int, path: str, threshold: int, hard: int) -> str:
    return ("warning: auto-compact window %s (%s) is below the pitstop threshold %s, so native compact can run "
            "before the checkpoint. Set it above the hard limit %s, for example /autocompact %dk." % (
                k(window), path, k(threshold), k(hard), max(400, (hard // 1000 + 99) // 100 * 100)))


def incomplete_case_ids_reason(ids: List[str]) -> str:
    return ("Waggle case id not complete: %s. Write each case id in full (c_ plus the whole uuid, as waggle_ask "
            "returned it), then run mark-pending again." % ", ".join(ids))


NEXT_ACTION_EMPTY = ("Next action is empty: the work is done, so there is nothing to resume. Skip the pitstop with "
                     "category `done` (send your final report, not a skip line, if you are a sub-agent), or write the "
                     "next action and run mark-pending again.")


def owed_reply_reason(event: str) -> str:
    return ("owed reply: %s reached you after your last text to the user and got no reply. Send the reply now "
            "(for a result, one line on what it says is enough), or set `Last reply to the user: NOT SENT` with "
            "the text under Chat-only text, then run mark-pending again." % event)


def previous_transcript(record: PendingRecord) -> Optional[str]:
    """The transcript of the session that wrote the checkpoint, where whatever it left out still is."""
    if not record.project_dir:
        return None
    return os.path.join(record.project_dir, "%s.jsonl" % record.session_id)


_LANGUAGES = {"italian": "Italian", "italiano": "Italian", "english": "English", "inglese": "English",
              "spanish": "Spanish", "spagnolo": "Spanish", "french": "French", "francese": "French",
              "german": "German", "tedesco": "German", "portuguese": "Portuguese", "portoghese": "Portuguese"}
# A rule on the language of replies: "Reply in Italian.", "rispondi sempre in italiano", "Italiano in chat". Rules
# for asks ("Waggle in italiano") count only when no chat rule is found. Code-language rules ("commits always in
# English") name no reply, chat or ask, so they do not match.
_LANG = "(%s)" % "|".join(_LANGUAGES)
_CHAT_LANGUAGE = re.compile(
    r"\b(?:repl\w*|answer\w*|chat|rispond\w*|rispost\w*|conversa\w*|scriv\w*)\b[^.\n]{0,40}?\bin\s+%s\b"
    r"|\b%s\b[^.\n;]{0,20}?\bin\s+chat\b" % (_LANG, _LANG), re.IGNORECASE)
_ASK_LANGUAGE = re.compile(r"\b(?:waggle|asks?)\b[^.\n]{0,40}?\bin\s+%s\b" % _LANG, re.IGNORECASE)


def reply_language(checkpoint_text: str) -> Optional[str]:
    """The language the checkpoint's User preferences ask replies in, in English (e.g. "Italian"), or None."""
    preferences = section(checkpoint_text, "User preferences")
    match = _CHAT_LANGUAGE.search(preferences) or _ASK_LANGUAGE.search(preferences)
    return _LANGUAGES[next(g for g in match.groups() if g).lower()] if match else None


def resume_context(record: PendingRecord, checkpoint_text: str, cli: str, delegate: bool = False) -> str:
    transcript = previous_transcript(record)
    gap = "`/usr/bin/python3 {cli} gap \"<what was missing>\"`".format(cli=cli)
    if transcript is None:
        missing = "5. If something you need is missing from the checkpoint, run %s, then recover it.\n" % gap
    else:
        missing = ("5. If something you need is missing from the checkpoint, look for it in the transcript before "
                   "the restart, %s (Grep it, then Read around the match with an offset), recover it, then run "
                   "%s.\n" % (transcript, gap))
    language = reply_language(checkpoint_text)
    if language:
        where = "in %s (the language used before the restart), in chat and in every ask" % language
        step4 = "4. Continue from the next action. Write %s, not in the language of this message.\n" % where
    else:
        where = "in the language used before the restart"
        step4 = ("4. Continue from the next action. Write to the user, and in any ask, in the language used before "
                 "the restart, not the language of this message.\n")
    if delegate:
        # F4: a T3 delegate's reply is its parent's result, so a banner there replaces the report.
        step3 = ("3. You are a sub-agent: print no resume banner and no summary of where you were. Your final reply "
                 "goes back to the thread that delegated you as its result: make it the report your task asks for, "
                 "%s.\n" % where)
    else:
        step3 = ("3. Print exactly `%s` followed by three short lines %s: goal, current state, next action.\n"
                 % (resumed_line(record.context_tokens), where))
    base = (
        "[pitstop] This session restarts from a pitstop checkpoint taken at {k}. Checkpoint file: {path}\n"
        "{transcript_line}\n"
        "<pitstop-checkpoint>\n{text}\n</pitstop-checkpoint>\n\n"
        "Resume:\n"
        "1. Re-read only the files the checkpoint cites that the next action needs. Do not re-explore.\n"
        "2. If the checkpoint says `Last reply to the user: NOT SENT`, send that reply first, from Chat-only text, "
        "before the next action. Never tell the user it was already sent.\n"
        "{step3}"
        "{step4}"
    ).format(k=k(record.context_tokens), path=record.checkpoint, text=checkpoint_text.strip(),
             step3=step3, step4=step4,
             transcript_line="Transcript before the restart: %s\n" % transcript if transcript else "")
    base += missing
    if record.plan:
        base += "6. A superpowers plan is being executed: resume the plan `%s` from its ledger with superpowers:subagent-driven-development.\n" % record.plan
    return base


def expired_line(hhmm: str, checkpoint: str) -> str:
    return ("🔋 **pitstop** · checkpoint expired (taken at %s): %s — say “resume from the checkpoint” "
            "to pick up from there" % (hhmm, checkpoint))


def expired_context(record: PendingRecord) -> str:
    hhmm = time.strftime("%H:%M", time.localtime(record.created_at))
    return (
        "[pitstop] pitstop found a checkpoint matching this session that expired, created at {hhmm} local "
        "time. Checkpoint file: {path}\n\n"
        "As the first line of your reply, print exactly `{line}`, then answer the user's message normally. "
        "If the user later asks to resume from it, Read {path} and follow the \"Resuming\" steps of the "
        "pitstop skill.\n"
    ).format(hhmm=hhmm, path=record.checkpoint, line=expired_line(hhmm, record.checkpoint))


def compact_blocked_reason() -> str:
    return ("[pitstop] Blocked: this session has no registered pitstop checkpoint, so pitstop must not compact it. "
            "If you skipped the pitstop, carry on normally; if mark-pending failed, report it and continue here.")
