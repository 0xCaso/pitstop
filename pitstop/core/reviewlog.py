"""reviews.jsonl: one line per /pitstop review."""
import json
import math
from typing import Optional

from pitstop.core.fsutil import append_line
from pitstop.core.paths import Layout


def append_review(layout: Layout, ts: float, bundle: str, cycles: int, approved: int, rejected: int) -> None:
    append_line(layout.reviews_log, json.dumps({"ts": ts, "bundle": bundle, "cycles": cycles, "approved": approved,
                                                "rejected": rejected}, ensure_ascii=False))


def last_review_ts(layout: Layout) -> Optional[float]:
    """When the last review ran; None without reviews. Lines it cannot read are skipped."""
    try:
        lines = layout.reviews_log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    times = []
    for line in lines:
        try:
            ts = json.loads(line).get("ts")
        except (ValueError, AttributeError):
            continue
        if isinstance(ts, (int, float)) and not isinstance(ts, bool) and math.isfinite(ts):
            times.append(float(ts))
    return max(times) if times else None
