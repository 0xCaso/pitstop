"""What /pitstop review reads from a transcript: the chat around a restart, as short plain text.
Files are read line by line, never whole; broken or partial lines are skipped."""
import json
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from pitstop.claude.report_scan import _texts, _timestamp

BEFORE_CHARS = 12000  # ipotesi: about 3K tokens; tune after the first review
AFTER_CHARS = 8000  # ipotesi: about 2K tokens
TOOL_CHARS = 200
CUT_LINE = "[… cut …]"


def _lines(entry: Dict[str, Any]) -> Iterator[str]:
    message = entry.get("message")
    if not isinstance(message, dict):
        return
    if entry.get("type") == "user":
        for text in _texts(message):  # tool_result blocks are not text: left out
            if text.strip():
                yield "[user] " + text.strip()
    elif entry.get("type") == "assistant":
        content = message.get("content")
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and isinstance(block.get("text"), str) and block["text"].strip():
                yield "[assistant] " + block["text"].strip()
            elif block.get("type") == "tool_use":
                call = "%s %s" % (block.get("name"), json.dumps(block.get("input"), ensure_ascii=False))
                yield "[tool] " + call[:TOOL_CHARS]


def chat_excerpt(path: Path, start: Optional[float], end: Optional[float], max_chars: int, keep: str) -> str:
    """Main-thread chat between start and end (None: no bound), one block per entry. keep="tail" keeps the last
    max_chars (before a restart), "head" the first (after a resume); a cut is marked with CUT_LINE.
    Raises FileNotFoundError when the transcript does not exist."""
    blocks = []
    with open(path, "rb") as fh:
        for raw in fh:
            try:
                entry = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(entry, dict) or entry.get("isSidechain") is True or entry.get("isMeta") is True:
                continue
            ts = _timestamp(entry)
            if ts is None or (start is not None and ts < start) or (end is not None and ts > end):
                continue
            blocks.extend(_lines(entry))
    text = "\n".join(blocks)
    if len(text) <= max_chars:
        return text
    if keep == "tail":
        kept = text[-max_chars:]
        newline = kept.find("\n")
        kept = kept[newline + 1:] if newline != -1 else kept
        return CUT_LINE + "\n" + kept
    kept = text[:max_chars]
    newline = kept.rfind("\n")
    kept = kept[:newline] if newline != -1 else kept
    return kept + "\n" + CUT_LINE
