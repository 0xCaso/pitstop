"""Append-only JSONL log. Numbers and states only: never prompts, replies, tool output or checkpoints."""
import json
import time
from typing import Any, Dict, List

from pitstop.core import build
from pitstop.core.fsutil import append_line
from pitstop.core.paths import Layout

ALLOWED_FIELDS = frozenset(
    {"session_id", "context_tokens", "threshold", "reason", "error", "checkpoint", "resume_base", "resumed_from",
     "cycle_id", "host", "kind", "restart", "checkpoint_bytes", "sections_filled", "chat_text_filled",
     "support_files", "unchecked_entries"}
)
_SCALARS = (str, int, float, bool)


def log_event(layout: Layout, event: str, action: str, **fields: Any) -> None:
    record: Dict[str, Any] = {"ts": round(time.time(), 3), "event": event, "action": action,
                              "v": build.plugin_version(), "skill": build.skill_hash()}
    for key, value in fields.items():
        if key not in ALLOWED_FIELDS:
            raise ValueError("field not allowed in log: %s" % key)
        if value is None:
            continue
        if not isinstance(value, _SCALARS):
            raise ValueError("log field %s must be a scalar" % key)
        record[key] = value
    append_line(layout.log, json.dumps(record, ensure_ascii=False))


def read_events(layout: Layout) -> List[Dict[str, Any]]:
    try:
        lines = layout.log.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    events = []
    for line in lines:
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events
