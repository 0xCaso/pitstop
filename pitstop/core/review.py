"""/pitstop review: which cycles to read. Pure: no I/O."""
from typing import Any, Dict, List, Optional, Tuple

from pitstop.core.cycles import Cycle, cycle_start

MAX_SAMPLE = 100  # about 500K input tokens per review (stima: ~5K per cycle file)


def _eligible(cycles: List[Cycle]) -> List[Cycle]:
    return [c for c in cycles if c.outcome == "resumed" and c.checkpoint_path and c.resume_ts is not None]


def pick_sample(cycles: List[Cycle], n: int) -> List[Cycle]:
    """The n most recently resumed cycles that name their checkpoint file, newest first."""
    return sorted(_eligible(cycles), key=lambda c: c.resume_ts, reverse=True)[:n]


def count_resumed_since(cycles: List[Cycle], since: Optional[float]) -> int:
    """Resumed cycles a review can read whose resume came at or after `since` (all of them when None)."""
    return sum(1 for c in _eligible(cycles) if since is None or c.resume_ts >= since)


def sample_size(configured: int, resumed_since: int) -> int:
    """At least `configured`; all the cycles resumed since the last review when there are more; at most MAX_SAMPLE."""
    return min(MAX_SAMPLE, max(configured, resumed_since))


def since_last_review(cycles: List[Cycle], events: List[Dict[str, Any]], since: Optional[float]) -> Tuple[int, int]:
    """(closed cycles that began at or after `since`, gap events at or after `since`); everything when None."""
    def after(ts: Any) -> bool:
        return isinstance(ts, (int, float)) and not isinstance(ts, bool) and (since is None or ts >= since)
    closed = sum(1 for c in cycles if c.closed and after(cycle_start(c)))
    gaps = sum(1 for e in events if e.get("action") == "gap" and after(e.get("ts")))
    return closed, gaps
