"""What pitstop reads from Claude Code's settings files: the auto-compact window."""
import json
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

SETTING = "autoCompactWindow"  # tokens (100000 to 1000000) or "auto"; /autocompact saves it


def _windows(raw: Any) -> List[int]:
    """The top-level window, and any per-model one (a dict of models whose entries carry the same key)."""
    if not isinstance(raw, dict):
        return []
    found = []
    candidates = [raw] + [v for value in raw.values() if isinstance(value, dict)
                          for v in value.values() if isinstance(v, dict)]
    for entry in candidates:
        value = entry.get(SETTING)
        if isinstance(value, int) and not isinstance(value, bool):
            found.append(value)
    return found


def settings_files(config_dir: Path, cwd: Optional[str]) -> List[Path]:
    files = [config_dir / "settings.json"]
    if cwd:
        files += [Path(cwd) / ".claude" / "settings.json", Path(cwd) / ".claude" / "settings.local.json"]
    return files


def lowest_auto_compact_window(files: Iterable[Path]) -> Optional[Tuple[int, Path]]:
    """The lowest auto-compact window set in these files, with its file; None when none sets a number."""
    lowest = None
    for path in files:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for window in _windows(raw):
            if lowest is None or window < lowest[0]:
                lowest = (window, path)
    return lowest
