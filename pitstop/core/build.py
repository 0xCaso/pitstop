"""Which build of pitstop wrote an event: plugin version and a short hash of the skill text."""
import functools
import hashlib
import json
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UNKNOWN = "unknown"


@functools.lru_cache(maxsize=None)
def plugin_version() -> str:
    try:
        version = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError, TypeError):
        return UNKNOWN
    return version if isinstance(version, str) else UNKNOWN


@functools.lru_cache(maxsize=None)
def skill_hash() -> str:
    try:
        return hashlib.sha256((REPO_ROOT / "skills" / "pitstop" / "SKILL.md").read_bytes()).hexdigest()[:8]
    except OSError:
        return UNKNOWN


def new_cycle_id() -> str:
    """One pitstop cycle: from the first request of a segment to the resume that closes it."""
    return uuid.uuid4().hex[:12]
