"""What the report reads from Claude Code transcripts: skip lines by category and calls after a resume.
Files are read line by line, never whole; broken or partial lines are skipped."""
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional

from pitstop.core.metrics import SKIP_CATEGORIES

SKIP_MARK = "🔋 **pitstop** · skipped:"
_SKIP_LINE = re.compile(r"🔋 \*\*pitstop\*\* · skipped: ([a-z-]+) —")
_SKIP_MARK_BYTES = b"skipped:"  # ASCII: transcripts may escape the emoji (\\ud83d...)


def projects_dirs(env: Mapping[str, str], home: Path) -> List[Path]:
    """$CLAUDE_CONFIG_DIR/projects first, then every ~/.claude*/projects, each folder once."""
    candidates: List[Path] = []
    config_dir = env.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        candidates.append(Path(config_dir).expanduser() / "projects")
    candidates.extend(sorted(home.glob(".claude*/projects")))
    found: List[Path] = []
    seen = set()
    for path in candidates:
        if not path.is_dir():
            continue
        real = os.path.realpath(str(path))
        if real not in seen:
            seen.add(real)
            found.append(path)
    return found


def _timestamp(entry: Dict[str, Any]) -> Optional[float]:
    value = entry.get("timestamp")
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _main_assistant(path: Path, start: float, end: Optional[float], needle: bytes) -> Iterator[Dict[str, Any]]:
    """Main-thread assistant entries inside [start, end] whose raw line contains needle."""
    try:
        fh = open(path, "rb")
    except OSError:
        return
    with fh:
        for line in fh:
            if needle not in line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict) or entry.get("type") != "assistant" or entry.get("isSidechain") is True:
                continue
            ts = _timestamp(entry)
            if ts is None or ts < start or (end is not None and ts > end):
                continue
            if isinstance(entry.get("message"), dict):
                yield entry


def _texts(message: Dict[str, Any]) -> Iterator[str]:
    content = message.get("content")
    if isinstance(content, str):
        yield content
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                yield block["text"]


def skip_categories(path: Path, start: float, end: Optional[float]) -> Dict[str, int]:
    """Skip lines printed by the skill, counted by category. An unknown category counts as `other`; a line in
    the format before 0.2.0 (no category) as `unparsed`. Only the category is kept, never the reason."""
    counts: Dict[str, int] = {}
    for entry in _main_assistant(path, start, end, _SKIP_MARK_BYTES):
        for text in _texts(entry["message"]):
            for line in text.splitlines():
                if SKIP_MARK not in line:
                    continue
                match = _SKIP_LINE.search(line)
                if match is None:
                    category = "unparsed"
                else:
                    category = match.group(1) if match.group(1) in SKIP_CATEGORIES else "other"
                counts[category] = counts.get(category, 0) + 1
    return counts


def calls_after(path: Path, start: float, end: Optional[float]) -> int:
    """Model calls in the window: distinct ids of main-thread assistant messages with usage."""
    ids = set()
    for entry in _main_assistant(path, start, end, b'"usage"'):
        message = entry["message"]
        if isinstance(message.get("usage"), dict) and message.get("model") != "<synthetic>":
            ids.add(message.get("id"))
    return len(ids)
