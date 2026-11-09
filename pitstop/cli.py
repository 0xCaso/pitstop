"""pitstop command line: the hook entry point and the management commands used by the skill."""
import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, TextIO

from pitstop.claude import messages
from pitstop.claude.hooks import run_hook
from pitstop.claude.report_scan import calls_after, projects_dirs, skip_categories
from pitstop.claude.review_scan import AFTER_CHARS, BEFORE_CHARS, chat_excerpt
from pitstop.claude.transcript import (
    TranscriptSchemaError,
    default_projects_dir,
    find_transcript,
    read_context_tokens,
    read_last_cwd,
    read_session_title,
)
from pitstop.core.build import new_cycle_id
from pitstop.core.checkpoint import analyze_checkpoint
from pitstop.core.config import _INT_RANGES, ConfigError, load_config, update_config
from pitstop.core.cycles import Cycle, build_cycles, next_start
from pitstop.core.fsutil import append_line, atomic_write_text
from pitstop.core.log import log_event, read_events
from pitstop.core.metrics import append_rows, cycle_row, import_audit, load_rows, summary
from pitstop.core.paths import Layout, pitstop_home
from pitstop.core.review import (MAX_SAMPLE, count_resumed_since, pick_sample, sample_size,
                                 since_last_review)
from pitstop.core.reviewlog import append_review, last_review_ts
from pitstop.core.state import load_state, locked_state
from pitstop.core.store import PendingRecord, mark_pending, new_checkpoint_path, prune_old_files, write_checkpoint

SESSION_ENV = "CLAUDE_CODE_SESSION_ID"
ENTRYPOINT_ENV = "CLAUDE_CODE_ENTRYPOINT"
# Set by hooks/register.ts where it will restart the session itself (terminal and `claude -p`, not SDK hosts).
AUTO_RESTART_ENV = "PITSTOP_AUTO_RESTART"
# T3 Code runs Claude Code through the SDK but names itself in the entrypoint instead of "sdk-*".
SDK_HOST_ENTRYPOINTS = ("t3-code",)


def is_sdk_host(entrypoint: str) -> bool:
    return (entrypoint.startswith("sdk") and entrypoint != "sdk-cli") or entrypoint in SDK_HOST_ENTRYPOINTS


class CliError(Exception):
    """Shown to the user as `🔋 pitstop · <message>`, exit code 1. Messages are English."""


def write_text(stream: TextIO, text: str) -> None:
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        buffer.write(text.encode("utf-8"))
        buffer.flush()
    else:
        stream.write(text)


def read_text(stream: TextIO) -> str:
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        return buffer.read().decode("utf-8", "replace")
    return stream.read()


@dataclass
class Ctx:
    layout: Layout
    stdin: TextIO
    stdout: TextIO
    env: Mapping[str, str]
    projects_dir: Path
    now: float
    # Where `report` looks for transcripts: every Claude profile's projects folder.
    report_dirs: List[Path] = field(default_factory=list)

    def say(self, text: str) -> None:
        write_text(self.stdout, text + "\n")


def _session_id(args: argparse.Namespace, ctx: Ctx) -> str:
    session = getattr(args, "session", None) or ctx.env.get(SESSION_ENV)
    if not session:
        raise CliError("unknown session: %s is not set, pass --session" % SESSION_ENV)
    return session


def _transcript(args: argparse.Namespace, ctx: Ctx, session_id: str) -> Path:
    if getattr(args, "transcript", None):
        return Path(args.transcript)
    found = find_transcript(session_id, ctx.projects_dir)
    if found is None:
        raise CliError("transcript of session %s not found" % session_id)
    return found


def cmd_on(args: argparse.Namespace, ctx: Ctx) -> None:
    update_config(ctx.layout, enabled=True)
    ctx.say("🔋 pitstop on")


def cmd_off(args: argparse.Namespace, ctx: Ctx) -> None:
    update_config(ctx.layout, enabled=False)
    ctx.say("🔋 pitstop off in all sessions")


def cmd_off_here(args: argparse.Namespace, ctx: Ctx) -> None:
    with locked_state(ctx.layout, _session_id(args, ctx)) as state:
        state.excluded = True
    ctx.say("🔋 pitstop off in this session")


def cmd_notify(args: argparse.Namespace, ctx: Ctx) -> None:
    update_config(ctx.layout, notify=args.state == "on")
    ctx.say("🔋 pitstop notifications %s" % args.state)


def cmd_metrics(args: argparse.Namespace, ctx: Ctx) -> None:
    update_config(ctx.layout, metrics=args.state == "on")
    ctx.say("🔋 pitstop metrics %s" % args.state)


def cmd_new_checkpoint(args: argparse.Namespace, ctx: Ctx) -> None:
    ctx.say(str(new_checkpoint_path(ctx.layout, _session_id(args, ctx), ctx.now)))


def cmd_mark_pending(args: argparse.Namespace, ctx: Ctx) -> None:
    session = _session_id(args, ctx)
    transcript = _transcript(args, ctx, session)
    try:
        tokens = read_context_tokens(str(transcript))
    except (OSError, TranscriptSchemaError) as exc:
        raise CliError("context not readable from the transcript (%s)" % type(exc).__name__) from None
    if tokens is None:
        raise CliError("context not readable from the transcript (no messages)")
    cwd = args.cwd or read_last_cwd(str(transcript)) or os.getcwd()
    if args.stdin:
        text = read_text(ctx.stdin)
        if not text.strip():
            raise CliError("empty checkpoint")
        checkpoint = None
    else:
        checkpoint = Path(args.checkpoint).expanduser()
        if not checkpoint.is_file():
            raise CliError("checkpoint not found: %s" % checkpoint)
        if checkpoint.stat().st_size == 0:
            raise CliError("empty checkpoint: %s" % checkpoint)
        text = checkpoint.read_text(encoding="utf-8", errors="replace")
    # Checked before anything is written: a checkpoint that cites files the resume cannot find is fixed first.
    stats = analyze_checkpoint(text, cwd, str(ctx.layout.checkpoints_dir))
    if stats.missing:
        raise CliError("files under Re-read not found: %s" % ", ".join(stats.missing))
    if stats.unchecked:
        ctx.say("warning: not checked under Re-read: %d entries" % len(stats.unchecked))
    if checkpoint is None:
        checkpoint = write_checkpoint(ctx.layout, session, text, ctx.now)
    # SDK hosts (T3 Code) have no /clear: there the session compacts and resumes in place.
    # The SDK check wins over the hooks module's flag: an SDK host must queue its own /compact.
    if is_sdk_host(ctx.env.get(ENTRYPOINT_ENV, "")):
        restart = "compact"
    elif ctx.env.get(AUTO_RESTART_ENV) == "1":
        restart = "auto"
    else:
        restart = "clear"
    # The cycle the hook opened with its offer or request; a pitstop nobody asked for (/pitstop now) starts its own.
    state = load_state(ctx.layout, session)
    asked = state.requested_at_tokens is not None or state.offered_at_tokens is not None
    cycle_id = state.cycle_id if asked and state.cycle_id else new_cycle_id()
    record = PendingRecord(
        checkpoint=str(checkpoint.resolve()),
        session_id=session,
        cwd=cwd,
        context_tokens=tokens,
        created_at=ctx.now,
        title=read_session_title(str(transcript)),
        plan=args.plan,
        project_dir=str(transcript.parent),
        restart=restart,
        cycle_id=cycle_id,
    )
    mark_pending(ctx.layout, record)
    prune_old_files(ctx.layout, ctx.now, keep=Path(record.checkpoint))
    log_event(ctx.layout, "cli", "pitstop_done", session_id=session, context_tokens=tokens,
              checkpoint=record.checkpoint, cycle_id=cycle_id, host=ctx.env.get(ENTRYPOINT_ENV, "unknown"),
              restart=restart, kind=args.kind or "unknown", checkpoint_bytes=stats.bytes,
              sections_filled=stats.sections_filled, chat_text_filled=stats.chat_text_filled,
              support_files=stats.support_files, unchecked_entries=len(stats.unchecked))
    config, _ = load_config(ctx.layout)
    ctx.say("checkpoint registered: %s" % record.checkpoint)
    ctx.say("resume window: %d minutes" % config.resume_window_minutes)
    ctx.say("restart: %s" % restart)
    if restart == "compact":
        # Spelled out here and not only in SKILL.md: a session follows the skill text it loaded first (issue #1).
        for line in messages.compact_queue_lines():
            ctx.say(line)
    ctx.say(messages.done_line(tokens))


def cmd_gap(args: argparse.Namespace, ctx: Ctx) -> None:
    session = _session_id(args, ctx)
    entry = {"ts": round(ctx.now, 3), "session_id": session, "text": " ".join(args.text).strip()}
    append_line(ctx.layout.gaps, json.dumps(entry, ensure_ascii=False))
    log_event(ctx.layout, "cli", "gap", session_id=session, cycle_id=load_state(ctx.layout, session).cycle_id)
    ctx.say("🔋 checkpoint gap recorded")


def _current_context(args: argparse.Namespace, ctx: Ctx, session: Optional[str]) -> str:
    if not session:
        return "not available"
    try:
        tokens = read_context_tokens(str(_transcript(args, ctx, session)))
    except (CliError, OSError, TranscriptSchemaError):
        return "not available"
    return messages.k(tokens) if tokens is not None else "not available"


def cmd_status(args: argparse.Namespace, ctx: Ctx) -> None:
    config, config_error = load_config(ctx.layout)
    session = args.session or ctx.env.get(SESSION_ENV)
    if config_error:
        ctx.say("🔋 pitstop: off (invalid config.json → %s)" % config_error)
    elif not config.enabled:
        ctx.say("🔋 pitstop: off in all sessions")
    elif session and load_state(ctx.layout, session).excluded:
        ctx.say("🔋 pitstop: off in this session")
    else:
        ctx.say("🔋 pitstop: on")
    ctx.say("notifications: %s" % ("on" if config.notify else "off"))
    ctx.say("metrics: %s" % ("on" if config.metrics else "off"))
    ctx.say("current context: %s · soft %s · threshold %s · hard %s" % (
        _current_context(args, ctx, session), messages.k(config.soft_threshold_tokens),
        messages.k(config.threshold_tokens), messages.k(config.hard_threshold_tokens)))
    events = read_events(ctx.layout)
    done = sum(1 for e in events if e.get("action") == "pitstop_done")
    gaps = sum(1 for e in events if e.get("action") == "gap")
    bases = [e["resume_base"] for e in events
             if e.get("action") == "resume_base" and isinstance(e.get("resume_base"), int)]
    ctx.say("pitstops: %d · real resumes: %d · gaps: %d" % (done, len(bases), gaps))
    if bases:
        ctx.say("real resume size: last %s · median %s" % (messages.k(bases[-1]),
                                                             messages.k(int(statistics.median(bases)))))
    ctx.say("folder: %s" % ctx.layout.base)


class _Transcripts:
    def __init__(self, dirs: List[Path]) -> None:
        self.dirs = dirs
        self.found: Dict[str, Optional[Path]] = {}

    def get(self, session: Optional[str]) -> Optional[Path]:
        if not session:
            return None
        if session not in self.found:
            self.found[session] = next((path for path in (find_transcript(session, d) for d in self.dirs)
                                        if path is not None), None)
        return self.found[session]


def _report_row(cycle: Cycle, cycles: List[Cycle], transcripts: _Transcripts) -> Dict[str, Any]:
    row = cycle_row(cycle)
    start = cycle.first_request_ts
    asked = transcripts.get(cycle.session)
    if start is not None and asked is not None:
        end = cycle.done_ts if cycle.done_ts is not None else next_start(cycles, cycle.session, start)
        row["skips"] = skip_categories(asked, start, end)
    resumed = transcripts.get(cycle.resume_session)
    if cycle.resume_ts is not None and resumed is not None:
        row["post_calls"] = calls_after(resumed, cycle.resume_ts,
                                        next_start(cycles, cycle.resume_session, cycle.resume_ts))
    return row


def cmd_report(args: argparse.Namespace, ctx: Ctx) -> None:
    added = 0
    if args.import_audit:
        try:
            added += append_rows(ctx.layout, import_audit(Path(args.import_audit).expanduser()))
        except (OSError, ValueError) as exc:
            raise CliError("audit not readable: %s (%s)" % (args.import_audit, type(exc).__name__)) from None
    stored = {row["cycle_id"] for row in load_rows(ctx.layout)}
    cycles = build_cycles(read_events(ctx.layout), ctx.now)
    transcripts = _Transcripts(ctx.report_dirs)
    rows = [_report_row(c, cycles, transcripts) for c in cycles if c.closed and c.cycle_id not in stored]
    added += append_rows(ctx.layout, rows)
    atomic_write_text(ctx.layout.report_stamp, "%d\n" % int(ctx.now))
    if args.quiet:
        return
    all_rows = load_rows(ctx.layout)
    ctx.say("🔋 pitstop report · %d new cycles · %d in metrics.jsonl" % (added, len(all_rows)))
    for line in summary(all_rows):
        ctx.say(line)


def cmd_config(args: argparse.Namespace, ctx: Ctx) -> None:
    """Set one numeric setting. update_config validates it, limit order included, before writing anything."""
    if args.key not in _INT_RANGES:
        raise CliError("unknown key: %s" % args.key)
    try:
        value = int(args.value)
    except ValueError:
        raise CliError("%s must be an integer" % args.key) from None
    update_config(ctx.layout, **{args.key: value})
    ctx.say("🔋 pitstop · %s = %d" % (args.key, value))


BEFORE_WINDOW_SECONDS = 3600  # the chat before the restart starts at least this long before the checkpoint


def _excerpt(path: Optional[Path], start: Optional[float], end: Optional[float], max_chars: int, keep: str) -> str:
    if path is None:
        return "transcript not found"
    try:
        return chat_excerpt(path, start, end, max_chars, keep) or "—"
    except OSError:
        return "transcript not found"


def _number_or_dash(value: Any) -> str:
    return "—" if value is None else str(value)


def _k_or_dash(value: Any) -> str:
    return messages.k(value) if isinstance(value, int) else "—"


def _review_file(cycle: Cycle, cycles: List[Cycle], transcripts: _Transcripts) -> str:
    asked_from = [ts for ts in (cycle.first_offer_ts, cycle.first_request_ts) if ts is not None]
    if cycle.done_ts is not None:
        asked_from.append(cycle.done_ts - BEFORE_WINDOW_SECONDS)
    before = _excerpt(transcripts.get(cycle.session), min(asked_from) if asked_from else None, cycle.done_ts,
                      BEFORE_CHARS, "tail")
    try:
        checkpoint = Path(cycle.checkpoint_path or "").read_text(encoding="utf-8").strip()
    except OSError:
        checkpoint = "checkpoint not found: %s" % cycle.checkpoint_path
    after = _excerpt(transcripts.get(cycle.resume_session), cycle.resume_ts,
                     next_start(cycles, cycle.resume_session, cycle.resume_ts), AFTER_CHARS, "head")
    header = "v %s · host %s · kind %s · restart %s · %s → %s tokens · gaps %d" % (
        cycle.v, _number_or_dash(cycle.host), _number_or_dash(cycle.kind), _number_or_dash(cycle.restart),
        _number_or_dash(cycle.done_tokens), _number_or_dash(cycle.resume_base), cycle.gaps)
    return "# cycle %s\n%s\n\n## Before the restart\n%s\n\n## Checkpoint\n%s\n\n## After the resume\n%s\n" % (
        cycle.cycle_id, header, before, checkpoint, after)


def cmd_review_bundle(args: argparse.Namespace, ctx: Ctx) -> None:
    cmd_report(argparse.Namespace(quiet=False, import_audit=None), ctx)
    config, _ = load_config(ctx.layout)
    events = read_events(ctx.layout)
    cycles = build_cycles(events, ctx.now)
    last = last_review_ts(ctx.layout)
    if args.n is not None:
        n = min(MAX_SAMPLE, max(1, args.n))
    else:
        # No logged review yet: "since the last review" would mean every cycle ever, so read only review_sample.
        n = sample_size(config.review_sample, 0 if last is None else count_resumed_since(cycles, last))
    sample = pick_sample(cycles, n)
    if not sample:
        raise CliError("no resumed cycles to review")
    folder = ctx.layout.reviews_dir / time.strftime("%Y%m%d-%H%M%S", time.localtime(ctx.now))
    transcripts = _Transcripts(ctx.report_dirs)
    ctx.say("bundle: %s" % folder)
    closed, gaps = since_last_review(cycles, events, last)
    ctx.say("last review: %s · %d closed cycles · %d gaps since" % (
        "none" if last is None else time.strftime("%Y-%m-%d", time.localtime(last)), closed, gaps))
    for cycle in sample:
        path = folder / ("%s.md" % cycle.cycle_id)
        atomic_write_text(path, _review_file(cycle, cycles, transcripts))
        ctx.say("cycle %s · v %s · %s · %s → %s · %s" % (cycle.cycle_id, cycle.v, _number_or_dash(cycle.host),
                                                       _k_or_dash(cycle.done_tokens), _k_or_dash(cycle.resume_base),
                                                       path))


def cmd_review_done(args: argparse.Namespace, ctx: Ctx) -> None:
    counts = (args.cycles, args.approved, args.rejected)
    if min(counts) < 0:
        raise CliError("counts must be 0 or more")
    append_review(ctx.layout, round(ctx.now, 3), args.bundle, *counts)
    ctx.say("🔋 **pitstop** · review: %d cycles · %d approved · %d rejected" % counts)


_COMMANDS = {
    "on": cmd_on,
    "off": cmd_off,
    "off-here": cmd_off_here,
    "notify": cmd_notify,
    "metrics": cmd_metrics,
    "status": cmd_status,
    "new-checkpoint": cmd_new_checkpoint,
    "mark-pending": cmd_mark_pending,
    "gap": cmd_gap,
    "report": cmd_report,
    "review-bundle": cmd_review_bundle,
    "review-done": cmd_review_done,
    "config": cmd_config,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pitstop",
                                     description="Checkpoint past a context threshold and resume after /clear or /compact.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("hook", help="run a Claude Code hook (event JSON on stdin)").add_argument("event")
    sub.add_parser("on", help="enable pitstop in all sessions")
    sub.add_parser("off", help="disable pitstop in all sessions")
    sub.add_parser("off-here", help="disable pitstop in the current session").add_argument("--session")
    notify = sub.add_parser("notify", help="macOS notifications")
    notify.add_argument("state", choices=["on", "off"])
    metrics = sub.add_parser("metrics", help="the daily local report and metrics.jsonl (off by default)")
    metrics.add_argument("state", choices=["on", "off"])
    status = sub.add_parser("status", help="state, current context and pilot numbers")
    status.add_argument("--session")
    status.add_argument("--transcript")
    sub.add_parser("new-checkpoint", help="print the path for a new checkpoint").add_argument("--session")
    mark = sub.add_parser("mark-pending", help="register a checkpoint for the resume after /clear or /compact")
    source = mark.add_mutually_exclusive_group(required=True)
    source.add_argument("--checkpoint", help="checkpoint file already written")
    source.add_argument("--stdin", action="store_true", help="read the checkpoint text from stdin")
    mark.add_argument("--cwd")
    mark.add_argument("--plan")
    mark.add_argument("--kind", choices=["code", "other"], help="code: the work lives in the repo's files")
    mark.add_argument("--session")
    mark.add_argument("--transcript")
    gap = sub.add_parser("gap", help="record something the checkpoint was missing")
    gap.add_argument("text", nargs="+")
    gap.add_argument("--session")
    report = sub.add_parser("report", help="rebuild the pitstop cycles, add the closed ones to metrics.jsonl")
    report.add_argument("--quiet", action="store_true", help="update metrics.jsonl, print nothing")
    report.add_argument("--import-audit", metavar="PATH", help="first import the cycles of an audit-data.json")
    bundle = sub.add_parser("review-bundle", help="refresh the report, write the chat around the last resumes")
    bundle.add_argument("--n", type=int, help="how many resumed cycles, 1-100 (default: review_sample in config.json, "
                                              "or all resumed since the last review when more)")
    done = sub.add_parser("review-done", help="log a finished /pitstop review in reviews.jsonl")
    done.add_argument("--bundle", required=True)
    for name in ("--cycles", "--approved", "--rejected"):
        done.add_argument(name, type=int, required=True)
    config = sub.add_parser("config", help="set a numeric setting in config.json (%s)" % ", ".join(_INT_RANGES))
    config.add_argument("key")
    config.add_argument("value")
    return parser


def _hook(args: List[str], stdin: TextIO, stdout: TextIO, layout: Layout) -> int:
    """Hooks never fail: no argparse exit codes, no stderr noise, always exit 0."""
    try:
        raw = read_text(stdin)
    except Exception:
        return 0
    output = run_hook(args[0] if args else "", raw, layout)
    if output:
        write_text(stdout, output)
    return 0


def main(argv: List[str], stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout,
         env: Optional[Mapping[str, str]] = None, layout: Optional[Layout] = None,
         projects_dir: Optional[Path] = None, now: Optional[float] = None) -> int:
    layout = layout or Layout(pitstop_home())
    if argv[:1] == ["hook"]:
        return _hook(argv[1:], stdin, stdout, layout)
    args = build_parser().parse_args(argv)
    env = os.environ if env is None else env
    ctx = Ctx(layout, stdin, stdout, env, projects_dir or default_projects_dir(env),
              time.time() if now is None else now,
              [projects_dir] if projects_dir else projects_dirs(env, Path.home()))
    try:
        _COMMANDS[args.command](args, ctx)
    except (CliError, ConfigError) as exc:
        ctx.say("🔋 pitstop · %s" % exc)
        return 1
    return 0
