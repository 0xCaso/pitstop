"""What pitstop reads from a Claude Code transcript (JSONL): context size, title, cwd."""
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional, Tuple

from pitstop.core.state import is_safe_session_id

BLOCK_SIZE = 64 * 1024
MAX_SCAN_BYTES = 16 * 1024 * 1024
USAGE_KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


MAX_GAP_SCAN_BYTES = 4 * 1024 * 1024


class TranscriptSchemaError(Exception):
    """Usage data is present but not in a shape pitstop understands."""


def _lines_from_end(path: str, max_bytes: int) -> Iterator[bytes]:
    """Yield lines from the last one backwards, reading at most max_bytes from the end.
    The last line may still be being written: callers must tolerate a partial line."""
    with open(path, "rb") as fh:
        position = os.fstat(fh.fileno()).st_size
        remainder = b""
        scanned = 0
        while position > 0 and scanned < max_bytes:
            step = min(BLOCK_SIZE, position)
            position -= step
            scanned += step
            fh.seek(position)
            lines = (fh.read(step) + remainder).split(b"\n")
            remainder = lines[0]
            for line in reversed(lines[1:]):
                if line.strip():
                    yield line
        if position == 0 and remainder.strip():
            yield remainder


def _int_field(usage: Dict[str, Any], key: str) -> int:
    value = usage.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TranscriptSchemaError("usage.%s missing or not an integer" % key)
    return value


def read_context_tokens(transcript_path: str, max_bytes: int = MAX_SCAN_BYTES,
                        since_compaction: bool = True) -> Optional[int]:
    """Context of the last main-thread assistant message: input + cache read + cache creation tokens.

    Streaming writes one line per content block, all with the same message id and usage, so the
    last valid line already is the deduplicated value. Returns None when there is no assistant
    usage yet, or none since the last compaction: a message from before it measures a context that
    is gone, and a hook can run before the first message after it reaches the file. With
    since_compaction=False the compaction is ignored. Never estimates."""
    for line in _lines_from_end(transcript_path, max_bytes):
        is_boundary = since_compaction and b'"compact_boundary"' in line
        if not is_boundary and b'"usage"' not in line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("isSidechain") is True:
            continue
        if is_boundary and entry.get("type") == "system" and entry.get("subtype") == "compact_boundary":
            return None
        if entry.get("type") != "assistant":
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            raise TranscriptSchemaError("assistant entry without a message object")
        if message.get("model") == "<synthetic>":
            continue
        usage = message.get("usage")
        if not isinstance(usage, dict):
            raise TranscriptSchemaError("assistant message without a usage object")
        return sum(_int_field(usage, key) for key in USAGE_KEYS)
    return None


def read_session_title(transcript_path: str) -> Optional[str]:
    """Latest custom title, else latest AI title. Scans the whole file: call it once per pitstop."""
    custom = None
    generated = None
    with open(transcript_path, "rb") as fh:
        for line in fh:
            if b'-title"' not in line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            if entry.get("type") == "custom-title" and isinstance(entry.get("customTitle"), str):
                custom = entry["customTitle"]
            elif entry.get("type") == "ai-title" and isinstance(entry.get("aiTitle"), str):
                generated = entry["aiTitle"]
    title = (custom or generated or "").strip()
    return title or None


def read_last_cwd(transcript_path: str, max_bytes: int = MAX_SCAN_BYTES) -> Optional[str]:
    for line in _lines_from_end(transcript_path, max_bytes):
        if b'"cwd"' not in line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and entry.get("isSidechain") is not True:
            cwd = entry.get("cwd")
            if isinstance(cwd, str) and cwd:
                return cwd
    return None


def default_projects_dir(env: Optional[Mapping[str, str]] = None) -> Path:
    """Where Claude Code keeps transcripts: $CLAUDE_CONFIG_DIR/projects (set per account), else ~/.claude/projects."""
    config_dir = (os.environ if env is None else env).get("CLAUDE_CONFIG_DIR")
    return (Path(config_dir).expanduser() if config_dir else Path.home() / ".claude") / "projects"


def find_transcript(session_id: str, projects_dir: Path) -> Optional[Path]:
    """Main transcript of a session: <projects_dir>/<project>/<session_id>.jsonl, newest if several."""
    if not is_safe_session_id(session_id):
        return None
    matches = [p for p in projects_dir.glob("*/%s.jsonl" % session_id) if p.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


_REPLY_TOOLS = ("waggle_ask", "waggle_update", "knock_ask", "knock_update")


def _blocks(message: Any) -> list:
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _has_text(blocks: list) -> bool:
    return any(b.get("type") == "text" and str(b.get("text", "")).strip() for b in blocks)


def read_unanswered_messages(transcript_path: str, max_bytes: int = MAX_SCAN_BYTES) -> Optional[int]:
    """How many user or task messages reached the main thread after its last text to the user, when none
    was answered since: the last one came after any reply sent through an ask tool (Waggle).

    0 means nothing is owed by this measure. None when no text to the user is found since the last
    compaction. Tool results alone do not count: reading files to write a checkpoint is normal."""
    messages_after = 0
    replied = False  # a reply tool was called after the latest message
    for line in _lines_from_end(transcript_path, max_bytes):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("isSidechain") is True:
            continue
        kind = entry.get("type")
        if kind == "system" and entry.get("subtype") == "compact_boundary":
            return None
        blocks = _blocks(entry.get("message"))
        if kind == "assistant":
            if _has_text(blocks):
                return messages_after
            if messages_after == 0 and any(b.get("type") == "tool_use" and str(b.get("name", "")).endswith(_REPLY_TOOLS)
                                           for b in blocks):
                replied = True
        elif kind == "user" and entry.get("isMeta") is not True:
            if any(b.get("type") == "tool_result" for b in blocks) or not _has_text(blocks):
                continue
            if messages_after == 0 and replied:
                return 0
            messages_after += 1
    return None


def read_tool_inputs_naming(transcript_path: str, start: int, needle: str,
                            max_bytes: int = MAX_GAP_SCAN_BYTES) -> Tuple[list, int]:
    """Inputs of main-thread tool calls written from offset start on that contain needle, as compact JSON,
    and the offset to start from next time (after the last complete line). Past max_bytes, older lines
    are skipped."""
    found = []
    with open(transcript_path, "rb") as fh:
        size = os.fstat(fh.fileno()).st_size
        if size <= start:
            return found, size
        start = max(start, size - max_bytes)
        fh.seek(start)
        chunk = fh.read(size - start)
    end = chunk.rfind(b"\n") + 1
    encoded = needle.encode("utf-8")
    for line in chunk[:end].split(b"\n"):
        if encoded not in line or b'"tool_use"' not in line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("type") != "assistant" or entry.get("isSidechain") is True:
            continue
        for block in _blocks(entry.get("message")):
            if block.get("type") != "tool_use":
                continue
            text = json.dumps(block.get("input"), ensure_ascii=False, separators=(",", ":"))
            if needle in text:
                found.append(text)
    return found, start + end
