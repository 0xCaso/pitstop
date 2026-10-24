"""metrics.jsonl: one row per closed pitstop cycle, kept after checkpoints and transcripts are deleted.
Numbers and states only: the row keys are a whitelist, like the log's, and unknown keys are dropped."""
import json
import os
import statistics
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from pitstop.core.checkpoint import analyze_checkpoint
from pitstop.core.cycles import CHECKPOINT_MEASURES, Cycle
from pitstop.core.fsutil import append_line, file_lock
from pitstop.core.paths import Layout

SKIP_CATEGORIES = ("debugging", "fine-editing", "ending-soon", "background-tasks", "brainstorming", "other")
# `unparsed`: a skip line in the format before 0.2.0, with no category.
SKIP_KEYS = SKIP_CATEGORIES + ("unparsed",)
ROW_FIELDS = frozenset(
    {"cycle_id", "v", "skill", "host", "kind", "first_request_ts", "request_tokens", "requests", "last_request_ts",
     "done_ts", "done_tokens", "restart", "resume_ts", "resume_base", "gaps", "dropped", "expired", "outcome",
     "post_calls", "reduction"}
)
_SCALARS = (str, int, float, bool)
EMPTY = "—"


def _int(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _counts(value: Any, keys: tuple) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {key: value[key] for key in keys if _int(value.get(key)) is not None}


def _clean(row: Dict[str, Any]) -> Dict[str, Any]:
    clean = {key: value for key, value in row.items()
             if key in ROW_FIELDS and value is not None and isinstance(value, _SCALARS)}
    if "skips" in row:
        clean["skips"] = _counts(row["skips"], SKIP_KEYS)
    if "checkpoint" in row:
        clean["checkpoint"] = _counts(row["checkpoint"], CHECKPOINT_MEASURES)
    return clean


def reduction(done_tokens: Any, resume_base: Any) -> Optional[float]:
    """1 - resume_base / done_tokens: the share of the context the pitstop took off."""
    done, base = _int(done_tokens), _int(resume_base)
    if done is None or base is None or done <= 0:
        return None
    return round(1 - base / done, 4)


def cycle_row(cycle: Cycle) -> Dict[str, Any]:
    """A closed cycle as a row, without session ids (no use once the transcripts are gone)."""
    row = asdict(cycle)
    row["reduction"] = reduction(cycle.done_tokens, cycle.resume_base)
    return _clean(row)


def load_rows(layout: Layout) -> List[Dict[str, Any]]:
    try:
        lines = layout.metrics.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    rows = []
    for line in lines:
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and isinstance(item.get("cycle_id"), str):
            rows.append(item)
    return rows


def append_rows(layout: Layout, rows: List[Dict[str, Any]]) -> int:
    """Append the rows whose cycle_id is not in metrics.jsonl yet; returns how many were written."""
    with file_lock(layout.base / "metrics.lock"):
        seen = {row["cycle_id"] for row in load_rows(layout)}
        written = 0
        for row in rows:
            clean = _clean(row)
            cycle_id = clean.get("cycle_id")
            if not isinstance(cycle_id, str) or cycle_id in seen:
                continue
            append_line(layout.metrics, json.dumps(clean, ensure_ascii=False, sort_keys=True))
            seen.add(cycle_id)
            written += 1
    return written


def _checkpoint_measures(path: Any) -> Dict[str, int]:
    if not isinstance(path, str) or not os.path.isfile(path):
        return {}
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    stats = analyze_checkpoint(text, os.path.dirname(path))
    return {"checkpoint_bytes": stats.bytes, "sections_filled": stats.sections_filled,
            "chat_text_filled": int(stats.chat_text_filled), "support_files": stats.support_files}


def _part(cycle: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = cycle.get(key)
    return value if isinstance(value, dict) else {}


def import_audit(path: Path) -> List[Dict[str, Any]]:
    """The cycles of audit-data.json (key `cycles`) as rows of version `pre-0.2`, with the checkpoint
    measures of the checkpoints still on disk."""
    data = json.loads(path.read_text(encoding="utf-8"))
    cycles = data.get("cycles") if isinstance(data, dict) else None
    rows = []
    for cycle in cycles if isinstance(cycles, list) else []:
        if not isinstance(cycle, dict):
            continue
        done, request = _part(cycle, "done"), _part(cycle, "request")
        line = _int(done.get("_line"))
        if line is None:
            continue
        resume_base = _part(cycle, "base").get("resume_base")
        rows.append(_clean({
            "cycle_id": "audit-%d" % line, "v": "pre-0.2", "skill": "unknown", "outcome": cycle.get("status"),
            "first_request_ts": request.get("ts"), "request_tokens": request.get("context_tokens"),
            "done_ts": done.get("ts"), "done_tokens": done.get("context_tokens"),
            "resume_ts": _part(cycle, "resume").get("ts"), "resume_base": resume_base,
            "post_calls": cycle.get("post_calls"), "reduction": reduction(done.get("context_tokens"), resume_base),
            "checkpoint": _checkpoint_measures(done.get("checkpoint")),
        }))
    return rows


def _percent(part: float, whole: int) -> str:
    return "%d%%" % round(100 * part / whole) if whole else EMPTY


def _summary_line(version: str, rows: List[Dict[str, Any]]) -> List[str]:
    resumed = [row for row in rows if row.get("outcome") == "resumed"]
    reductions = [row["reduction"] for row in rows if isinstance(row.get("reduction"), (int, float))]
    with_gaps = [row["gaps"] for row in resumed if _int(row.get("gaps")) is not None]
    chat = [row["checkpoint"]["chat_text_filled"] for row in rows
            if isinstance(row.get("checkpoint"), dict) and _int(row["checkpoint"].get("chat_text_filled")) is not None]
    median = "%d%%" % round(100 * statistics.median(reductions)) if reductions else EMPTY
    gaps = "%d per 100 resumes" % round(100 * sum(with_gaps) / len(with_gaps)) if with_gaps else EMPTY
    lines = ["v %s · cycles %d · resumed %s · median reduction %s · gaps %s · chat text %s" % (
        version, len(rows), _percent(len(resumed), len(rows)), median, gaps, _percent(sum(chat), len(chat)))]
    skips: Dict[str, int] = {}
    for row in rows:
        for key, count in _counts(row.get("skips"), SKIP_KEYS).items():
            skips[key] = skips.get(key, 0) + count
    if skips:
        lines.append("  skips: " + " · ".join("%s %d" % (key, skips[key]) for key in SKIP_KEYS if key in skips))
    kinds: Dict[str, int] = {}
    for row in rows:
        kind = row.get("kind") if isinstance(row.get("kind"), str) else "unknown"
        kinds[kind] = kinds.get(kind, 0) + 1
    lines.append("  kind: " + " · ".join("%s %d" % item for item in sorted(kinds.items())))
    return lines


def summary(rows: List[Dict[str, Any]]) -> List[str]:
    """Per plugin version, in order of first appearance: cycles, % resumed, median reduction, gaps per 100
    resumes, % checkpoints with chat-only text, skips by category, cycles by kind of work."""
    by_version: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        by_version.setdefault(str(row.get("v", "unknown")), []).append(row)
    lines: List[str] = []
    for version, group in by_version.items():
        lines.extend(_summary_line(version, group))
    return lines
