"""/pitstop review: which cycles to read. Pure: no I/O."""
from typing import List

from pitstop.core.cycles import Cycle


def pick_sample(cycles: List[Cycle], n: int) -> List[Cycle]:
    """The n most recently resumed cycles that name their checkpoint file, newest first."""
    eligible = [c for c in cycles if c.outcome == "resumed" and c.checkpoint_path and c.resume_ts is not None]
    return sorted(eligible, key=lambda c: c.resume_ts, reverse=True)[:n]
