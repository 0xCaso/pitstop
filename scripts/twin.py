"""Twin test: pitstop checkpoint vs native /compact, on copies of real sessions.

Records: docs/decisions/2026-11-10-twin-pilot-next-step.md, docs/decisions/2026-11-23-p1-deep-review.md (task P2).
Usage:
    python3 scripts/twin.py run --out DIR [--n 5] [--other 1] [--cycles id,id] [--jobs 5]
    python3 scripts/twin.py summary --out DIR
    python3 scripts/twin.py continue --out DIR (--cycles id,id | --versions 0.5.2) [--main-only] [--jobs 5]
        [--pitstop-root DIR] [--config-dir DIR]
    python3 scripts/twin.py continue-summary --out DIR

Options of every command: --pitstop-root is the pitstop checkout whose resume text the P arm gets (default: this
repo), so one script tests any version; --config-dir is the Claude account the twins run on (default: the account
of the source session).

Per cycle: cut the transcript before the pitstop turn, copy it to two twin sessions, restart one with a plain
/compact (N) and one with pitstop's compact + resume message (P), ask both the same probes with read-only tools,
grade the answers blind, delete the twins. Twins run with no hooks and no MCP servers.

`continue`: same cut and restart, then each twin gets the first real user message after the resume (P with
pitstop's resume context) and works in a snapshot of the repo at the cut. A blind grader compares both first replies
with what was owed before the cut and what really happened after the resume. The arms (P2, 2026-11-23):
- run with `--restricted`: no user settings or hooks, file tools confined to the snapshot; `twin_guard.py` refuses
  any Bash path outside it, network commands and pushes (H1);
- have write tools inside the snapshot and a stub Waggle server that records asks (H2);
- get 40 turns; a twin with no final reply is graded on its last text (H3);
- the snapshot holds the repo at the cut plus the outside folders named in the checkpoint and in the last 50 tool
  calls, under `_ext/` with the paths rewritten (H5).
The grader gets the cut time and does not count facts that appear only after it (H4).
"""
import argparse
import concurrent.futures
import json
import os
import random
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent


def _pitstop_root(argv: List[str]) -> Path:
    """--pitstop-root from the command line, read before the imports below pick a pitstop version."""
    for i, arg in enumerate(argv):
        if arg == "--pitstop-root" and i + 1 < len(argv):
            return Path(argv[i + 1]).expanduser().resolve()
        if arg.startswith("--pitstop-root="):
            return Path(arg.split("=", 1)[1]).expanduser().resolve()
    return HERE.parent


ROOT = _pitstop_root(sys.argv)
sys.path.insert(0, str(ROOT))

from pitstop.claude.messages import resume_context  # noqa: E402
from pitstop.claude.report_scan import projects_dirs  # noqa: E402
from pitstop.claude.review_scan import chat_excerpt  # noqa: E402
from pitstop.claude.transcript import find_transcript  # noqa: E402
from pitstop.core.cycles import Cycle, build_cycles, next_start  # noqa: E402
from pitstop.core.log import read_events  # noqa: E402
from pitstop.core.paths import Layout, pitstop_home  # noqa: E402
from pitstop.core.store import PendingRecord  # noqa: E402

try:  # 0.5.3+: a T3 delegate's resume asks for no banner
    from pitstop.claude.transcript import read_is_t3_delegate  # noqa: E402
except ImportError:
    read_is_t3_delegate = None

CLI = str(ROOT / "bin" / "pitstop")
P_COMPACT = '/compact One-line summary: "Resume from the pitstop checkpoint."'
TWIN_FLAGS = ["--settings", '{"disableAllHooks": true}', "--strict-mcp-config", "--output-format", "json"]
READ_ONLY = ["--tools", "Read,Grep,Glob", "--allowedTools", "Read,Grep,Glob"]
ARM_TOOLS = "Read,Grep,Glob,Edit,Write,Bash,ToolSearch"
WAGGLE_SERVER = "plugin_waggle_waggle"  # the real plugin's server name, so the tool names match
GUARD = HERE / "twin_guard.py"
WAGGLE_STUB = HERE / "twin_waggle_stub.py"
CONFIG_DIR: Optional[str] = None  # --config-dir
CALL_TIMEOUT = 1200
BEFORE_PROBE_CHARS = 160000  # ipotesi: about 40K tokens of chat before the cut
AFTER_PROBE_CHARS = 20000
PROBES = 8

PROBE_PROMPT = """You write test questions for a context-restart experiment. Below is the chat of a coding session
BEFORE a restart, and the chat AFTER the restart (what the work then needed). Write exactly {n} questions whose
answers are in the BEFORE chat (prefer facts that live only in the chat, not in repo files):
- 4 with "type": "used": facts that the AFTER chat used or needed (it re-read, searched, asked, or relied on them);
- 4 with "type": "value": other details of value for the remaining work: exact strings (commands that worked,
  ids, option texts), decisions with their reason, the user's preferences in their words, a reply still owed to
  the user, open waits (e.g. a Waggle case), checked vs assumed facts.
Each question must have one short, checkable answer. Do not ask about things that happen only in the AFTER chat.
Reply ONLY with JSON: {{"probes": [{{"id": "q1", "type": "used|value", "q": "...", "key": "...",
"source": "short exact quote from BEFORE"}}]}}

=== BEFORE ===
{before}

=== AFTER ===
{after}
"""

ANSWER_PROMPT = """TEST RUN. Do not continue the work, do not change any file, do not call any tool except Read,
Grep and Glob. Answer each question below from what you know about this session. If you need to, you may look
things up with Read, Grep or Glob (also in the transcript of the session before the restart). If you do not know,
answer "unknown". Reply ONLY with JSON:
{{"answers": [{{"id": "q1", "answer": "...", "source": "context|lookup", "looked_in": "path or empty"}}]}}

Questions:
{questions}
"""

GRADE_PROMPT = """Grade two answer sets, X and Y, against the answer key. For each question give each set one
grade: "correct" (same fact; wording may differ), "partly" (right but missing a needed part, e.g. an exact string
paraphrased), "wrong" (a different or false fact), "unknown" (no answer). Judge only the facts.
Reply ONLY with JSON: {{"grades": [{{"id": "q1", "x": "...", "y": "...", "note": "few words"}}]}}

Key:
{key}

X:
{x}

Y:
{y}
"""


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def parse_json(text: str) -> Dict[str, Any]:
    """The first JSON object in a model reply (it may sit in a code fence)."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON in reply: %r" % text[:300])
    return json.loads(text[start:end + 1])


def claude(args: List[str], cwd: str, config_dir: Optional[str], prompt: str,
           extra_env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    env = dict(os.environ)
    config_dir = CONFIG_DIR or config_dir
    if config_dir:
        env["CLAUDE_CONFIG_DIR"] = config_dir
    env.update(extra_env or {})
    # The prompt goes on stdin: --tools and --allowedTools take several values and would swallow it.
    try:
        out = subprocess.run(["claude", "-p"] + args, cwd=cwd, env=env, input=prompt,
                             capture_output=True, text=True, timeout=CALL_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError("claude -p timeout after %ds" % CALL_TIMEOUT)
    try:
        data = json.loads(out.stdout)
    except ValueError:
        raise RuntimeError("claude -p failed (%d): %s %s" % (out.returncode, out.stdout[-500:], out.stderr[-500:]))
    if data.get("is_error"):
        raise RuntimeError("claude -p error (%s): %s %s" % (data.get("subtype"), str(data.get("result"))[:400],
                                                          json.dumps(data.get("errors"))[:400]))
    return data


# --- cycles and the cut -------------------------------------------------------------------------------------

def load_cycles() -> List[Cycle]:
    layout = Layout(pitstop_home())
    return build_cycles(read_events(layout), time.time())


def find(session: Optional[str]) -> Optional[Path]:
    if not session:
        return None
    for d in projects_dirs(os.environ, Path.home()):
        path = find_transcript(session, d)
        if path is not None:
            return path
    return None


def _entries(path: Path) -> List[Tuple[bytes, Dict[str, Any]]]:
    rows = []
    with open(path, "rb") as fh:
        for raw in fh:
            try:
                entry = json.loads(raw)
            except ValueError:
                continue
            if isinstance(entry, dict):
                rows.append((raw, entry))
    return rows


def _utc(value: str) -> Optional[float]:
    import calendar
    try:
        return calendar.timegm(time.strptime(value[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return None


def _blocks(entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _is_mark_pending(entry: Dict[str, Any]) -> bool:
    return entry.get("type") == "assistant" and any(
        b.get("type") == "tool_use" and "mark-pending" in json.dumps(b.get("input")) and "pitstop" in json.dumps(
            b.get("input")) for b in _blocks(entry))


def _stops_walk(raw: bytes, entry: Dict[str, Any]) -> bool:
    """True for an entry that belongs to the work, not to the pitstop turn: the cut keeps it."""
    if b"pitstop" in raw.lower():
        return False
    kind = entry.get("type")
    blocks = _blocks(entry)
    if kind == "assistant":
        return any(b.get("type") in ("text", "tool_use") for b in blocks)
    if kind == "user" and not entry.get("isMeta"):
        return bool(blocks)
    return False


def cut_index(rows: List[Tuple[bytes, Dict[str, Any]]], cycle: Cycle) -> int:
    """Index of the first line the twin leaves out: the start of the pitstop turn."""
    lo = (cycle.first_request_ts or cycle.done_ts or 0) - 120
    hi = (cycle.done_ts or 0) + 120
    hits = [i for i, (_, e) in enumerate(rows) if _is_mark_pending(e)
            and lo <= (_utc(e.get("timestamp", "")) or 0) <= hi]
    if not hits:
        raise RuntimeError("no mark-pending call near the checkpoint time")
    i = hits[-1]
    while i > 0 and not _stops_walk(*rows[i - 1]):
        i -= 1
    return i


def last_boundary_ts(rows: List[Tuple[bytes, Dict[str, Any]]], end: int) -> Optional[float]:
    for raw, entry in reversed(rows[:end]):
        if entry.get("subtype") == "compact_boundary":
            return _utc(entry.get("timestamp", ""))
    return None


def write_twin(rows: List[Tuple[bytes, Dict[str, Any]]], end: int, project_dir: Path) -> Tuple[str, Path]:
    twin = str(uuid.uuid4())
    path = project_dir / ("%s.jsonl" % twin)
    with open(path, "w", encoding="utf-8") as fh:
        for _, entry in rows[:end]:
            if entry.get("type") == "cost-state":  # else total_cost_usd starts from the source session's total
                continue
            if "sessionId" in entry:
                entry = dict(entry, sessionId=twin)
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        # a title of its own: a twin shows in /resume and in usage monitors, and the copied title passes for the
        # real session; the newest custom-title wins
        fh.write(json.dumps({"type": "custom-title", "customTitle": twin_title(rows[:end]), "sessionId": twin},
                            ensure_ascii=False) + "\n")
    return twin, path


def twin_title(rows: List[Tuple[bytes, Dict[str, Any]]]) -> str:
    """"twin · <the source's title>", from its newest custom or AI title."""
    for key, field in (("custom-title", "customTitle"), ("ai-title", "aiTitle")):
        title = next((e.get(field) for _, e in reversed(rows) if e.get("type") == key and e.get(field)), None)
        if title:
            return "twin · %s" % title
    return "twin"


def remove_twin(path: Path) -> None:
    if path.suffix == ".jsonl" and path.is_file():
        path.unlink()
    side = path.with_suffix("")
    if side.is_dir() and len(side.name) == 36:
        subprocess.run(["rm", "-r", "--", str(side)], check=False)


def resume_tokens(path: Path) -> Optional[int]:
    """Context of the first model call after the last compact boundary in a twin transcript."""
    rows = _entries(path)
    start = max((i for i, (_, e) in enumerate(rows) if e.get("subtype") == "compact_boundary"), default=None)
    if start is None:
        return None
    for _, entry in rows[start:]:
        usage = (entry.get("message") or {}).get("usage") if entry.get("type") == "assistant" else None
        if isinstance(usage, dict):
            return sum(int(usage.get(k) or 0) for k in
                       ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return None


# --- one cycle ----------------------------------------------------------------------------------------------

def run_cycle(cycle: Cycle, cycles: List[Cycle], out: Path) -> Dict[str, Any]:
    result_path = out / ("%s.json" % cycle.cycle_id)
    if result_path.exists():
        return json.loads(result_path.read_text())
    src = find(cycle.session)
    if src is None or not cycle.checkpoint_path or not Path(cycle.checkpoint_path).is_file():
        raise RuntimeError("transcript or checkpoint not found")
    rows = _entries(src)
    end = cut_index(rows, cycle)
    cwd = next((e.get("cwd") for _, e in reversed(rows[:end]) if isinstance(e.get("cwd"), str)), None)
    if not cwd or not os.path.isdir(cwd):
        raise RuntimeError("cwd not found: %s" % cwd)
    config_dir = str(src.parents[2])
    cost: Dict[str, float] = {"probe": 0.0, "N": 0.0, "P": 0.0, "grade": 0.0}

    # Probes, from the chat since the previous restart and the real chat after the resume (never the checkpoint).
    cut_ts = _utc(rows[end - 1][1].get("timestamp", "")) if end else None
    before = chat_excerpt(src, last_boundary_ts(rows, end), cut_ts, BEFORE_PROBE_CHARS, "tail")
    resumed = find(cycle.resume_session)
    after = chat_excerpt(resumed, cycle.resume_ts, next_start(cycles, cycle.resume_session, cycle.resume_ts),
                         AFTER_PROBE_CHARS, "head") if resumed else ""
    probe_run = claude(["--tools", "", "--no-session-persistence", "--output-format", "json", "--settings", '{"disableAllHooks": true}',
                        "--strict-mcp-config"], str(out), None,
                       PROBE_PROMPT.format(n=PROBES, before=before, after=after))
    cost["probe"] += probe_run.get("total_cost_usd") or 0
    probes = parse_json(probe_run["result"])["probes"]
    questions = "\n".join("%s. %s" % (p["id"], p["q"]) for p in probes)

    checkpoint_text = Path(cycle.checkpoint_path).read_text(encoding="utf-8")
    arms: Dict[str, Dict[str, Any]] = {}
    twins: List[Path] = []
    try:
        for arm in ("N", "P"):
            twin, path = write_twin(rows, end, src.parent)
            twins.append(path)
            compact = claude(["--resume", twin] + TWIN_FLAGS, cwd, config_dir, "/compact" if arm == "N" else P_COMPACT)
            cost[arm] += compact.get("total_cost_usd") or 0
            prompt = ANSWER_PROMPT.format(questions=questions)
            if arm == "P":
                record = PendingRecord(checkpoint=cycle.checkpoint_path, session_id=twin, cwd=cwd,
                                       context_tokens=cycle.done_tokens or 0, created_at=time.time(),
                                       project_dir=str(src.parent), restart="compact")
                prompt = resume_context(record, checkpoint_text, CLI) + "\n\n---\n\n" + prompt
            answer = claude(["--resume", twin] + TWIN_FLAGS + READ_ONLY, cwd, config_dir, prompt)
            cost[arm] += answer.get("total_cost_usd") or 0
            arms[arm] = {"answers": parse_json(answer["result"])["answers"], "turns": answer.get("num_turns"),
                         "resume_tokens": resume_tokens(path)}
    finally:
        for path in twins:
            remove_twin(path)

    # Blind grading: the grader sees X and Y in random order.
    order = ["N", "P"]
    random.shuffle(order)
    key = json.dumps([{k: p[k] for k in ("id", "q", "key")} for p in probes], ensure_ascii=False, indent=1)
    show = {a: json.dumps([{k: x.get(k) for k in ("id", "answer")} for x in arms[a]["answers"]],
                          ensure_ascii=False, indent=1) for a in order}
    grade_run = claude(["--tools", "", "--no-session-persistence", "--output-format", "json", "--settings", '{"disableAllHooks": true}',
                        "--strict-mcp-config"], str(out), None,
                       GRADE_PROMPT.format(key=key, x=show[order[0]], y=show[order[1]]))
    cost["grade"] += grade_run.get("total_cost_usd") or 0
    grades = parse_json(grade_run["result"])["grades"]
    for g in grades:
        g[order[0]] = g.pop("x", None)
        g[order[1]] = g.pop("y", None)

    result = {"cycle": cycle.cycle_id, "kind": cycle.kind, "v": cycle.v, "done_tokens": cycle.done_tokens,
              "cut_line": end, "probes": probes, "arms": arms, "grades": grades, "order": order, "cost": cost}
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    return result


# --- continuation test --------------------------------------------------------------------------------------

CONT_BEFORE_CHARS = 15000
CONT_AFTER_CHARS = 8000
CONT_TURNS = ["--max-turns", "40"]

CONT_GRADE_PROMPT = """A coding session was restarted to free context at {cut} (UTC). Two restarted copies, X and Y,
received the same first user message and replied. Judge which copy continued the work better.

You get: the end of the chat BEFORE the restart (what was owed to the user and what came next), the REAL chat AFTER
the restart (what the work then needed; a user correction there shows what the real session got wrong), and the
first reply and tool calls of X and Y. The copies worked in a copy of the files as they were at the restart, with
write tools, no network and no human: their Waggle asks were recorded and never answered, and calls outside their
files were refused. Judge what they did and what they claimed.

Facts that appear only after the restart (in REAL AFTER, or work done there) count neither for nor against a copy:
a copy is not wrong because it does not know them, and not right because it guesses them. Use REAL AFTER for what
the work needed next, not for the state of the files at the restart.

For each copy give:
- "owed_reply": "yes" if a reply owed to the user before the restart (an answer, a result, a question) was given or
  is clearly acted on, "no" if it was dropped, "n.a." if nothing was owed;
- "next_action": "yes" / "partly" / "no": the copy goes for the right next step;
- "wrong_claims": false statements about the state of the work at the restart (short list, may be empty);
- "missing_details": details from BEFORE that the copy lost (short list). List a detail only if the real session
  used it in its next steps (REAL AFTER) and the copy neither states it nor shows it has it (in its reply or its tool
  calls). A detail the copy did not need yet, or a detail it acts on without restating it, is not missing.
Then "winner": "X", "Y" or "tie", and "why" in one sentence.
Reply ONLY with JSON: {{"x": {{"owed_reply": "...", "next_action": "...", "wrong_claims": [], "missing_details": []}},
"y": {{...}}, "winner": "...", "why": "..."}}

=== BEFORE (end) ===
{before}

=== REAL AFTER ===
{after}

=== FIRST USER MESSAGE AFTER THE RESTART ===
{message}

=== X ===
{x}

=== Y ===
{y}
"""


SNAP_BASE = "/tmp/pitstop-twin"
SNAP_SKIP = ("node_modules", ".venv", "venv", "dist", "build", ".next", ".git", "__pycache__", ".turbo")
SNAP_MAX_BYTES = 1_000_000
EXT_MAX_FILES = 2000  # per cycle, over all outside folders
EXT_TOOL_CALLS = 50
# Outside paths never copied: system folders, other sessions' transcripts, whole home or Desktop folders.
EXT_NEVER = ("/usr/", "/bin/", "/sbin/", "/System/", "/Library/", "/Applications/", "/opt/", "/dev/", "/etc/",
             "/var/folders/", "/private/etc/", "/private/var/")
PATH_TOKEN = re.compile(r"(?:~|/)(?:Users|private|tmp|Volumes|home|~)?[\w.@~+/-]*")


def _sanitize(path: str) -> str:
    """Claude Code's folder name for a project path."""
    return "".join(ch if ch.isalnum() else "-" for ch in path)


def _copy_file(src: Path, target: Path, cut_ts: float) -> bool:
    """Copy one regular file last changed before the cut and under the size limit."""
    try:
        st = src.stat()
    except OSError:
        return False
    if not stat.S_ISREG(st.st_mode) or st.st_size > SNAP_MAX_BYTES or st.st_mtime > cut_ts:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_bytes(src.read_bytes())
    except OSError:
        return False
    return True


def _copy_tree(src: Path, dest: Path, cut_ts: float, budget: List[int], recursive: bool = True) -> None:
    """Files under `src` (skipping build folders) changed before the cut, while `budget[0]` files are left."""
    walk = os.walk(src) if recursive else [(str(src), [], [p.name for p in src.iterdir() if p.is_file()])]
    for folder, dirs, files in walk:
        dirs[:] = [d for d in dirs if d not in SNAP_SKIP]
        for name in files:
            if budget[0] <= 0:
                return
            rel = os.path.relpath(os.path.join(folder, name), src)
            if _copy_file(Path(folder) / name, dest / rel, cut_ts):
                budget[0] -= 1


def snapshot(cwd: str, cut_ts: float, dest: Path) -> Tuple[str, str]:
    """The project at `cwd` as it was at `cut_ts`, copied to `dest`; returns (copied top folder, cwd inside it).
    In a git repo: tracked files from the last commit before the cut (git archive, the live repo is not touched),
    plus untracked or ignored files under 1 MB last changed before the cut (specs, plans, ledgers). Elsewhere, or
    with no commit before the cut: the files under `cwd` last changed before the cut (newer files are missing)."""
    dest.mkdir(parents=True, exist_ok=True)
    top = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    top_dir = top.stdout.strip() if top.returncode == 0 else ""
    sha = subprocess.run(["git", "-C", top_dir, "log", "--all", "-1", "--format=%H", "--before=@%d" % int(cut_ts)],
                         capture_output=True, text=True).stdout.strip() if top_dir else ""
    archive = subprocess.run(["git", "-C", top_dir, "archive", sha], capture_output=True) if sha else None
    if archive is None or archive.returncode != 0:
        _copy_tree(Path(cwd), dest, cut_ts, [EXT_MAX_FILES * 5])
        return cwd, str(dest)
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout, check=True)
    others = subprocess.run(["git", "-C", top_dir, "ls-files", "-o", "-z"], capture_output=True, text=True).stdout
    for rel in filter(None, others.split("\0")):
        if not any(part in SNAP_SKIP for part in Path(rel).parts):
            _copy_file(Path(top_dir) / rel, dest / rel, cut_ts)
    return top_dir, str(dest / os.path.relpath(cwd, top_dir))


def outside_paths(texts: List[str], top: str, home: str, keep_out: List[str]) -> List[str]:
    """Existing absolute paths named in `texts` that lie outside the project folder `top` and are worth copying:
    not system folders, not `keep_out` (transcript folders), not the home folder or one of its direct children."""
    found = set()
    for text in texts:
        for token in PATH_TOKEN.findall(text):
            path = os.path.expanduser(token.rstrip(".,:)/"))
            if not os.path.isabs(path) or len(Path(path).parts) < 4:
                continue
            real = os.path.realpath(path)
            if real == top or real.startswith(top.rstrip("/") + "/") or real.startswith(EXT_NEVER):
                continue
            if any(real == k or real.startswith(k.rstrip("/") + "/") for k in keep_out):
                continue
            if Path(real).parent == Path(home) or real == home or real.endswith("/bin/pitstop"):
                continue  # the CLI the work called: the snapshot has its own copy
            if os.path.exists(real):
                found.add(real)
    # A path inside another found path is copied with it.
    ordered = sorted(found, key=len)
    return [p for i, p in enumerate(ordered) if not any(p.startswith(q.rstrip("/") + "/") for q in ordered[:i])]


def copy_outside(paths: List[str], ext_root: Path, cut_ts: float) -> Dict[str, str]:
    """Copy each outside path under `ext_root` (a folder whole, a file with the files next to it, or alone when it
    sits in a top folder such as ~/.claude); returns the map from each real path to its copy."""
    budget = [EXT_MAX_FILES]
    mapping: Dict[str, str] = {}
    for path in paths:
        src = Path(path)
        target = ext_root / path.lstrip("/")
        if src.is_dir():
            _copy_tree(src, target, cut_ts, budget)
        elif src.is_file() and len(src.parent.parts) > 4:
            _copy_tree(src.parent, target.parent, cut_ts, budget, recursive=False)
        elif src.is_file():
            if _copy_file(src, target, cut_ts):
                budget[0] -= 1
        else:
            continue
        mapping[path] = str(target)
    return mapping


def aliases(path: str, home: str) -> List[str]:
    """The ways a session may write the real path `path`: as is, with /tmp or /var for macOS's /private/..., and
    with ~ for the home folder."""
    forms = [path]
    for short in ("/tmp/", "/var/"):
        if path.startswith("/private" + short):
            forms.append(path[len("/private"):])
    for form in list(forms):
        if form.startswith(home.rstrip("/") + "/"):
            forms.append("~" + form[len(home.rstrip("/")):])
    return forms


def rewrite(text: str, mapping: Dict[str, str]) -> str:
    """Every mapped path in `text` replaced by its copy, in one pass (longest path first), so a replacement is
    never rewritten again. Paths appear as written and JSON-escaped, and match only whole path parts."""
    if not mapping:
        return text
    pairs: Dict[str, str] = {}
    for old, new in mapping.items():
        pairs[old] = new
        pairs[json.dumps(old)[1:-1]] = json.dumps(new)[1:-1]
    pattern = re.compile(r"(?:(?<=\\[ntr])|(?<![\w.~/-]))(?:%s)(?![\w@+-]|\.\w)"
                         % "|".join(re.escape(k) for k in sorted(pairs, key=len, reverse=True)))
    return pattern.sub(lambda m: pairs[m.group(0)], text)


def recent_tool_inputs(rows: List[Tuple[bytes, Dict[str, Any]]], end: int, n: int) -> List[str]:
    """The inputs of the last `n` tool calls before the cut, as JSON text."""
    calls: List[str] = []
    for _, entry in reversed(rows[:end]):
        if entry.get("type") != "assistant":
            continue
        for b in reversed(_blocks(entry)):
            if b.get("type") == "tool_use":
                calls.append(json.dumps(b.get("input"), ensure_ascii=False))
                if len(calls) >= n:
                    return calls
    return calls


def first_user_message(path: Path, since: Optional[float]) -> Optional[str]:
    """Text of the first real user message at or after `since` (no meta, tool results, commands or summaries)."""
    for _, entry in _entries(path):
        if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isCompactSummary") \
                or entry.get("isSidechain"):
            continue
        ts = _utc(entry.get("timestamp", ""))
        if since is not None and (ts is None or ts < since - 5):
            continue
        texts = [b.get("text", "") for b in _blocks(entry) if b.get("type") == "text"]
        text = "\n".join(t for t in texts if t).strip()
        if not text or text.startswith("<command-") or text.startswith("<local-command") \
                or "<pitstop-checkpoint>" in text:
            continue
        return text
    return None


def tool_calls(path: Path) -> List[str]:
    """Tool calls after the last compact boundary of a twin, as short lines."""
    rows = _entries(path)
    start = max((i for i, (_, e) in enumerate(rows) if e.get("subtype") == "compact_boundary"), default=0)
    calls = []
    for _, entry in rows[start:]:
        if entry.get("type") != "assistant":
            continue
        for b in _blocks(entry):
            if b.get("type") == "tool_use":
                calls.append("%s %s" % (b.get("name"), json.dumps(b.get("input"), ensure_ascii=False)[:200]))
    return calls


def last_text(path: Path) -> str:
    """The last assistant text after the last compact boundary of a twin: what a twin with no final reply wrote."""
    rows = _entries(path)
    start = max((i for i, (_, e) in enumerate(rows) if e.get("subtype") == "compact_boundary"), default=0)
    for _, entry in reversed(rows[start:]):
        if entry.get("type") == "assistant":
            texts = [b.get("text", "") for b in _blocks(entry) if b.get("type") == "text" and b.get("text")]
            if texts:
                return "\n".join(texts)
    return ""


def _jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def arm_settings() -> str:
    """--settings for an arm: the guard hook on every tool, Bash in the sandbox with no network, the arm's tools
    allowed without a prompt (`--restricted` ignores every other settings file)."""
    return json.dumps({
        "hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
            {"type": "command", "command": "/usr/bin/python3 %s" % GUARD}]}]},
        "sandbox": {"enabled": True, "allowUnsandboxedCommands": False, "network": {"allowedDomains": []}},
        "permissions": {"defaultMode": "acceptEdits",
                        "allow": ARM_TOOLS.split(",") + ["mcp__%s__*" % WAGGLE_SERVER]},
    })


def arm_mcp(path: Path) -> str:
    """A --mcp-config file with only the stub Waggle server."""
    path.write_text(json.dumps({"mcpServers": {WAGGLE_SERVER: {
        "type": "stdio", "command": "/usr/bin/python3", "args": [str(WAGGLE_STUB)]}}}))
    return str(path)


def pitstop_cli_copy(dest: Path) -> str:
    """A copy of the tested pitstop's CLI inside the snapshot, so the arm can run it without reaching outside."""
    for part in ("bin", "pitstop"):
        shutil.copytree(ROOT / part, dest / part, ignore=shutil.ignore_patterns("__pycache__"))
    return str(dest / "bin" / "pitstop")


def continue_cycle(cycle: Cycle, cycles: List[Cycle], out: Path) -> Dict[str, Any]:
    result_path = out / ("%s.json" % cycle.cycle_id)
    if result_path.exists():
        return json.loads(result_path.read_text())
    src = find(cycle.session)
    resumed = find(cycle.resume_session)
    if src is None or resumed is None or not cycle.checkpoint_path or not Path(cycle.checkpoint_path).is_file():
        raise RuntimeError("transcript or checkpoint not found")
    rows = _entries(src)
    end = cut_index(rows, cycle)
    cwd = next((e.get("cwd") for _, e in reversed(rows[:end]) if isinstance(e.get("cwd"), str)), None)
    if not cwd or not os.path.isdir(cwd):
        raise RuntimeError("cwd not found: %s" % cwd)
    cut_ts = _utc(rows[end - 1][1].get("timestamp", "")) if end else None
    if not cut_ts:
        raise RuntimeError("no cut time")
    message = first_user_message(resumed, cycle.resume_ts)
    if not message:
        raise RuntimeError("no user message after the resume")
    config_dir = CONFIG_DIR or str(src.parents[2])
    checkpoint_text = Path(cycle.checkpoint_path).read_text(encoding="utf-8")

    # The snapshot: the project at the cut, the outside folders the work named, a copy of the checkpoint and of
    # the tested CLI. Every path the twin sees is rewritten to its copy.
    # Not under ~/.claude: Claude Code treats files there as sensitive and refuses writes to them.
    snap_root = Path(os.path.realpath(SNAP_BASE)) / cycle.cycle_id
    pristine = snap_root.with_name(cycle.cycle_id + ".pristine")  # the snapshot again for P, without N's edits
    logs_root = snap_root.with_name(cycle.cycle_id + ".logs")  # outside what the arms can read
    for folder in (snap_root, pristine, logs_root):
        if folder.exists():
            shutil.rmtree(folder)
    top, snap_cwd = snapshot(cwd, cut_ts, snap_root / "repo")
    run_cwd = os.path.realpath(snap_cwd)
    home = str(Path.home())
    keep_out = [str(Path(d)) for d in projects_dirs(os.environ, Path.home())] + [str(ROOT)]
    named = outside_paths([checkpoint_text] + recent_tool_inputs(rows, end, EXT_TOOL_CALLS), top, home, keep_out)
    copies = copy_outside(named, snap_root / "_ext", cut_ts)
    copies[os.path.realpath(top)] = os.path.realpath(snap_root / "repo")
    mapping = {form: copy for real, copy in copies.items() for form in aliases(real, home)}
    if top != os.path.realpath(top):
        mapping[top] = copies[os.path.realpath(top)]
    checkpoint_copy = snap_root / "_ext" / "checkpoint.md"
    checkpoint_copy.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_text = rewrite(checkpoint_text, mapping)
    checkpoint_copy.write_text(checkpoint_text, encoding="utf-8")
    cli = pitstop_cli_copy(snap_root / "_pitstop")
    twin_rows = [(raw, json.loads(rewrite(raw.decode("utf-8"), mapping))) for raw, _ in rows[:end]]
    shutil.copytree(snap_root, pristine, symlinks=True)

    cost: Dict[str, float] = {"N": 0.0, "P": 0.0, "grade": 0.0}
    project_dir = Path(config_dir) / "projects" / _sanitize(run_cwd)
    project_dir.mkdir(parents=True, exist_ok=True)
    arms: Dict[str, Dict[str, Any]] = {}
    twins: List[Path] = []
    try:
        # The twin's own scratchpad and task output live under /tmp/claude-<uid>/<project folder>.
        scratch = Path(os.path.realpath("/tmp")) / ("claude-%d" % os.getuid()) / _sanitize(run_cwd)
        for arm in ("N", "P"):
            if arm == "P":  # P starts from the same files as N: N's edits, scratchpad and twin are gone
                for path in twins:
                    remove_twin(path)
                shutil.rmtree(snap_root)
                shutil.copytree(pristine, snap_root, symlinks=True)
            shutil.rmtree(scratch, ignore_errors=True)
            scratch.mkdir(parents=True)
            twin, path = write_twin(twin_rows, end, project_dir)
            twins.append(path)
            logs = logs_root / arm
            logs.mkdir(parents=True, exist_ok=True)
            env = {"TWIN_ALLOW": os.pathsep.join([str(snap_root), str(project_dir), str(scratch)]),
                   "TWIN_GUARD_LOG": str(logs / "refused.jsonl"), "TWIN_WAGGLE_LOG": str(logs / "asks.jsonl"),
                   "PITSTOP_HOME": str(logs / "pitstop-home")}
            flags = ["--restricted", "--strict-mcp-config", "--mcp-config", arm_mcp(logs / "mcp.json"),
                     "--settings", arm_settings(), "--output-format", "json",
                     "--add-dir", str(snap_root), "--add-dir", str(project_dir), "--add-dir", str(scratch)]
            compact = claude(["--resume", twin] + flags, run_cwd, config_dir,
                             "/compact" if arm == "N" else P_COMPACT, env)
            cost[arm] += compact.get("total_cost_usd") or 0
            prompt = message
            resume_input = None
            if arm == "P":
                record = PendingRecord(checkpoint=str(checkpoint_copy), session_id=twin, cwd=run_cwd,
                                       context_tokens=cycle.done_tokens or 0, created_at=time.time(),
                                       project_dir=str(project_dir), restart="compact")  # transcript = twin
                delegate = bool(read_is_t3_delegate and read_is_t3_delegate(str(src)))
                context = (resume_context(record, checkpoint_text, cli, delegate=delegate) if read_is_t3_delegate
                           else resume_context(record, checkpoint_text, cli))
                # H6: the P arm gets the resume text this version's hook builds (as a user message, not as
                # additional context; no plan: the cycle log does not keep it).
                resume_input = {"chars": len(context), "checkpoint_in_input": checkpoint_text.strip() in context,
                                "delegate": delegate, "pitstop_root": str(ROOT)}
                prompt = context + "\n\n---\n\n" + message
            try:
                reply = claude(["--resume", twin] + flags + ["--tools", ARM_TOOLS] + CONT_TURNS, run_cwd,
                               config_dir, prompt, env)
                cost[arm] += reply.get("total_cost_usd") or 0
                text, turns, final, stop = reply.get("result") or "", reply.get("num_turns"), True, None
                if not text:
                    text, final, stop = last_text(path) or "(no reply)", False, reply.get("subtype") or "no result"
            except RuntimeError as exc:  # max turns, timeout, API error: grade the twin's last text (H3)
                text, turns, final, stop = last_text(path) or "(no reply)", None, False, str(exc)[:200]
            arms[arm] = {"reply": text, "final_reply": final, "stopped": stop, "turns": turns, "tools": tool_calls(path),
                         "resume_tokens": resume_tokens(path), "asks": _jsonl(logs / "asks.jsonl"),
                         "refused": _jsonl(logs / "refused.jsonl"), "resume_input": resume_input}
    finally:
        for path in twins:
            remove_twin(path)
        for folder in (snap_root, pristine, logs_root, scratch):
            shutil.rmtree(folder, ignore_errors=True)
        if project_dir != src.parent and not any(project_dir.iterdir()):
            project_dir.rmdir()  # the twin's own folder, once empty

    before = chat_excerpt(src, last_boundary_ts(rows, end), cut_ts, CONT_BEFORE_CHARS, "tail")
    after = chat_excerpt(resumed, cycle.resume_ts, next_start(cycles, cycle.resume_session, cycle.resume_ts),
                         CONT_AFTER_CHARS, "head")
    order = ["N", "P"]
    random.shuffle(order)
    show = {a: "Reply%s:\n%s\n\nTool calls:\n%s\n\nWaggle asks recorded: %d · calls refused: %d" % (
        "" if arms[a]["final_reply"] else " (no final reply, %s: last text)" % arms[a]["stopped"], arms[a]["reply"],
        "\n".join(arms[a]["tools"]) or "none", len(arms[a]["asks"]), len(arms[a]["refused"])) for a in order}
    grade_run = claude(["--tools", "", "--no-session-persistence", "--output-format", "json", "--settings",
                        '{"disableAllHooks": true}', "--strict-mcp-config"], str(out), None,
                       CONT_GRADE_PROMPT.format(cut=time.strftime("%Y-%m-%d %H:%M", time.gmtime(cut_ts)),
                                                before=before, after=after, message=message,
                                                x=show[order[0]], y=show[order[1]]))
    cost["grade"] += grade_run.get("total_cost_usd") or 0
    raw = parse_json(grade_run["result"])
    grade = {order[0]: raw.get("x"), order[1]: raw.get("y"),
             "winner": {"X": order[0], "Y": order[1]}.get(raw.get("winner"), "tie"), "why": raw.get("why")}

    result = {"cycle": cycle.cycle_id, "kind": cycle.kind, "v": cycle.v, "done_tokens": cycle.done_tokens,
              "cut_line": end, "cut_ts": cut_ts, "snapshot": True, "outside": sorted(mapping),
              "message": message, "arms": arms, "grade": grade, "order": order, "cost": cost}
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    return result


def set_account(args: argparse.Namespace) -> None:
    global CONFIG_DIR
    if getattr(args, "config_dir", None):
        CONFIG_DIR = str(Path(args.config_dir).expanduser().resolve())


def cmd_continue(args: argparse.Namespace) -> None:
    if not args.cycles and not args.versions:
        raise SystemExit("continue: give --cycles or --versions")
    set_account(args)
    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    cycles = load_cycles()
    chosen = pick(cycles, args.n, args.other, args.cycles.split(",") if args.cycles else None,
                  args.versions.split(",") if args.versions else None, args.main_only)
    log("cycles: %s" % " ".join("%s(%s)" % (c.cycle_id, c.kind) for c in chosen))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(continue_cycle, c, cycles, out): c for c in chosen}
        for future in concurrent.futures.as_completed(futures):
            c = futures[future]
            try:
                r = future.result()
                log("done %s · cost %.2f" % (c.cycle_id, sum(r["cost"].values())))
            except Exception as exc:
                log("FAILED %s: %s" % (c.cycle_id, exc))
                (out / ("%s.error.txt" % c.cycle_id)).write_text(str(exc))
    cmd_continue_summary(out)


def cmd_continue_summary(out: Path) -> None:
    results = [json.loads(p.read_text()) for p in sorted(out.glob("*.json"))]
    if not results:
        print("no results")
        return
    lines = ["# Continuation test: pitstop (P) vs native compact (N)", "", "Cycles: %d" % len(results), ""]
    wins = {k: sum(1 for r in results if r["grade"]["winner"] == k) for k in ("N", "P", "tie")}
    lines.append("- Winner: P %d · N %d · tie %d" % (wins["P"], wins["N"], wins["tie"]))
    for arm in ("N", "P"):
        g = [r["grade"].get(arm) or {} for r in results]
        lines.append("- **%s**: owed reply dropped %d (of %d owed) · next action yes %d / partly %d / no %d · "
                     "wrong claims %d · missing details %d · cost USD %.2f" % (
                         arm, sum(1 for x in g if x.get("owed_reply") == "no"),
                         sum(1 for x in g if x.get("owed_reply") in ("yes", "no")),
                         sum(1 for x in g if x.get("next_action") == "yes"),
                         sum(1 for x in g if x.get("next_action") == "partly"),
                         sum(1 for x in g if x.get("next_action") == "no"),
                         sum(len(x.get("wrong_claims") or []) for x in g),
                         sum(len(x.get("missing_details") or []) for x in g),
                         sum(r["cost"][arm] for r in results)))
    lines += ["", "## Per cycle"]
    for r in results:
        lines.append("- %s (%s%s) · message %r · winner %s — %s" % (
            r["cycle"], r["kind"], ", snapshot" if r.get("snapshot") else "", r["message"][:60], r["grade"]["winner"], r["grade"].get("why")))
        for arm in ("N", "P"):
            x = r["grade"].get(arm) or {}
            lines.append("  - %s: owed %s · next %s · tools %d · wrong %s · missing %s" % (
                arm, x.get("owed_reply"), x.get("next_action"), len(r["arms"][arm]["tools"]),
                x.get("wrong_claims") or "—", x.get("missing_details") or "—"))
    lines += ["", "Total cost: USD %.2f" % sum(sum(r["cost"].values()) for r in results)]
    text = "\n".join(lines) + "\n"
    (out / "summary.md").write_text(text)
    print(text)


# --- commands -----------------------------------------------------------------------------------------------

def is_main_session(session: Optional[str]) -> bool:
    """False for a subagent's transcript (a `subagents/` folder or sidechain entries): its resume has no user."""
    path = find(session)
    if path is None or "subagents" in path.parts:
        return False
    for _, entry in _entries(path)[:20]:
        if entry.get("isSidechain"):
            return False
    return True


def pick(cycles: List[Cycle], n: int, other: int, ids: Optional[List[str]],
         versions: Optional[List[str]] = None, main_only: bool = False) -> List[Cycle]:
    """Resumed cycles with a checkpoint: the given ids, or the newest `n` (`other` of them kind other) of the
    given pitstop versions (default 0.5.0, the version of the first runs)."""
    ok = [c for c in cycles if c.outcome == "resumed" and c.checkpoint_path and c.resume_ts]
    if ids:
        return [c for c in ok if c.cycle_id in ids]
    ok = [c for c in ok if c.v in (versions or ["0.5.0"])]
    if main_only:
        ok = [c for c in ok if is_main_session(c.session) and is_main_session(c.resume_session)]
    ok.sort(key=lambda c: c.resume_ts, reverse=True)
    others = [c for c in ok if c.kind == "other"][:other]
    code = [c for c in ok if c.kind != "other"][:n - len(others)]
    return code + others


def cmd_run(args: argparse.Namespace) -> None:
    set_account(args)
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    cycles = load_cycles()
    chosen = pick(cycles, args.n, args.other, args.cycles.split(",") if args.cycles else None)
    log("cycles: %s" % " ".join("%s(%s)" % (c.cycle_id, c.kind) for c in chosen))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(run_cycle, c, cycles, out): c for c in chosen}
        for future in concurrent.futures.as_completed(futures):
            c = futures[future]
            try:
                r = future.result()
                log("done %s · cost %.2f" % (c.cycle_id, sum(r["cost"].values())))
            except Exception as exc:  # one failed cycle does not stop the others
                log("FAILED %s: %s" % (c.cycle_id, exc))
                (out / ("%s.error.txt" % c.cycle_id)).write_text(str(exc))
    cmd_summary(args)


def cmd_summary(args: argparse.Namespace) -> None:
    out = Path(args.out).expanduser()
    results = [json.loads(p.read_text()) for p in sorted(out.glob("*.json"))]
    if not results:
        print("no results")
        return
    lines = ["# Twin test: pitstop (P) vs native compact (N)", "",
             "Cycles: %d · probes: %d" % (len(results), sum(len(r["probes"]) for r in results)), ""]
    for arm in ("N", "P"):
        grades = [g.get(arm) for r in results for g in r["grades"]]
        n = len(grades) or 1
        lost = sum(1 for g in grades if g in ("wrong", "unknown"))
        partly = sum(1 for g in grades if g == "partly")
        lookups = sum(1 for r in results for a in r["arms"][arm]["answers"] if a.get("source") == "lookup")
        tokens = [r["arms"][arm]["resume_tokens"] for r in results if r["arms"][arm].get("resume_tokens")]
        cost = sum(r["cost"][arm] for r in results)
        lines.append("- **%s**: lost (wrong + unknown) %d/%d (%.0f%%) · partly %d · answered by lookup %d · "
                     "resume tokens median %s · restart + answers cost USD %.2f" % (
                         arm, lost, n, 100.0 * lost / n, partly, lookups,
                         sorted(tokens)[len(tokens) // 2] if tokens else "—", cost))
    for kind in ("used", "value"):
        ids = [(r, g) for r in results for g in r["grades"]
               if next((p["type"] for p in r["probes"] if p["id"] == g["id"]), None) == kind]
        lines.append("- probes `%s` (%d): lost N %d · P %d" % (
            kind, len(ids), sum(1 for _, g in ids if g.get("N") in ("wrong", "unknown")),
            sum(1 for _, g in ids if g.get("P") in ("wrong", "unknown"))))
    lines += ["", "## Per cycle"]
    for r in results:
        lost = {a: sum(1 for g in r["grades"] if g.get(a) in ("wrong", "unknown")) for a in ("N", "P")}
        lines.append("- %s (%s): lost N %d · P %d · resume tokens N %s · P %s" % (
            r["cycle"], r["kind"], lost["N"], lost["P"], r["arms"]["N"].get("resume_tokens"),
            r["arms"]["P"].get("resume_tokens")))
        for g in r["grades"]:
            if g.get("N") != g.get("P"):
                p = next(p for p in r["probes"] if p["id"] == g["id"])
                lines.append("  - %s [%s] N %s · P %s — %s (%s)" % (g["id"], p["type"], g.get("N"), g.get("P"),
                                                                 p["q"], g.get("note", "")))
    lines.append("")
    lines.append("Total cost: USD %.2f" % sum(sum(r["cost"].values()) for r in results))
    text = "\n".join(lines) + "\n"
    (out / "summary.md").write_text(text)
    print(text)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--out", required=True)
    run.add_argument("--n", type=int, default=5)
    run.add_argument("--other", type=int, default=1)
    run.add_argument("--cycles")
    run.add_argument("--jobs", type=int, default=5)
    summary = sub.add_parser("summary")
    summary.add_argument("--out", required=True)
    cont = sub.add_parser("continue")
    cont.add_argument("--out", required=True)
    cont.add_argument("--cycles", help="cycle ids, comma-separated")
    cont.add_argument("--versions", help="pick the newest cycles of these pitstop versions, comma-separated")
    cont.add_argument("--n", type=int, default=30, help="with --versions: how many cycles")
    cont.add_argument("--other", type=int, default=5, help="with --versions: how many of kind other")
    cont.add_argument("--main-only", action="store_true", help="leave out subagent sessions")
    cont.add_argument("--jobs", type=int, default=5)
    cont_sum = sub.add_parser("continue-summary")
    cont_sum.add_argument("--out", required=True)
    for command in (run, cont):
        command.add_argument("--pitstop-root", help="pitstop checkout whose resume text P gets (read at start)")
        command.add_argument("--config-dir", help="Claude account the twins run on")
    args = parser.parse_args()
    {"run": cmd_run, "summary": cmd_summary, "continue": cmd_continue,
     "continue-summary": lambda a: cmd_continue_summary(Path(a.out).expanduser())}[args.command](args)


if __name__ == "__main__":
    main()
