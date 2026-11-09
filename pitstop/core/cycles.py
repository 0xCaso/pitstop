"""Pitstop cycles rebuilt from the log: request, checkpoint, restart, resume, outcome. Pure: no I/O."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

DAY_SECONDS = 24 * 60 * 60
CHECKPOINT_MEASURES = ("checkpoint_bytes", "sections_filled", "chat_text_filled", "support_files",
                       "unchecked_entries")


@dataclass
class Cycle:
    cycle_id: str
    v: str
    skill: str
    host: Optional[str] = None
    session: Optional[str] = None  # the session that was asked for the pitstop (or made it)
    kind: Optional[str] = None
    first_offer_ts: Optional[float] = None
    offers: int = 0  # soft-zone offers (0.3+)
    first_request_ts: Optional[float] = None
    request_tokens: Optional[int] = None
    requests: int = 0
    hard_requests: int = 0  # requests past the hard limit (0.3+)
    last_request_ts: Optional[float] = None
    done_ts: Optional[float] = None
    done_tokens: Optional[int] = None
    restart: Optional[str] = None
    checkpoint: Dict[str, int] = field(default_factory=dict)
    checkpoint_path: Optional[str] = None
    resume_ts: Optional[float] = None
    resume_session: Optional[str] = None
    resume_base: Optional[int] = None
    gaps: int = 0
    dropped: bool = False
    expired: bool = False
    outcome: str = "open"
    closed: bool = False


def _number(value: Any) -> Optional[float]:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _apply(cycle: Cycle, event: Dict[str, Any]) -> None:
    action = event.get("action")
    ts = _number(event.get("ts"))
    if cycle.host is None and isinstance(event.get("host"), str):
        cycle.host = event["host"]
    if (cycle.session is None and action in ("offer", "request", "pitstop_done")
            and isinstance(event.get("session_id"), str)):
        cycle.session = event["session_id"]
    if action == "offer":
        cycle.offers += 1
        if cycle.first_offer_ts is None:
            cycle.first_offer_ts = ts
    elif action == "request":
        cycle.requests += 1
        if event.get("zone") == "hard":
            cycle.hard_requests += 1
        if cycle.first_request_ts is None:
            cycle.first_request_ts = ts
            cycle.request_tokens = event.get("context_tokens")
        cycle.last_request_ts = ts
    elif action == "pitstop_done":
        cycle.done_ts = ts
        cycle.done_tokens = event.get("context_tokens")
        cycle.restart = event.get("restart")
        cycle.kind = event.get("kind")
        cycle.checkpoint_path = event["checkpoint"] if isinstance(event.get("checkpoint"), str) else None
        # chat_text_filled is a bool in the log: stored as 0 or 1 like the other measures.
        cycle.checkpoint = {key: int(event[key]) for key in CHECKPOINT_MEASURES
                            if isinstance(event.get(key), (int, float))}
    elif action == "resume":
        cycle.resume_ts = ts
        cycle.resume_session = event.get("session_id")
    elif action == "resume_base" and cycle.resume_base is None:
        cycle.resume_base = event.get("resume_base")
    elif action == "gap":
        cycle.gaps += 1
    elif action == "pending_dropped":
        cycle.dropped = True
    elif action == "resume_expired":
        cycle.expired = True


def cycle_start(cycle: Cycle) -> Optional[float]:
    """When a cycle began: its first offer or request, or its checkpoint for a pitstop nobody offered or requested."""
    asked = [ts for ts in (cycle.first_offer_ts, cycle.first_request_ts) if ts is not None]
    return min(asked) if asked else cycle.done_ts


def next_start(cycles: List[Cycle], session: Optional[str], after: float) -> Optional[float]:
    """When the session's next cycle began after `after`; None if it has none yet."""
    starts = (cycle_start(c) for c in cycles if c.session == session)
    times = [start for start in starts if start is not None and start > after]
    return min(times) if times else None


def _settle(cycle: Cycle, cycles: List[Cycle], now: float) -> None:
    if cycle.resume_ts is not None:
        # Closed once the resumed session reached its next pitstop (its calls and gaps are final), or after a day.
        cycle.outcome = "resumed"
        cycle.closed = (next_start(cycles, cycle.resume_session, cycle.resume_ts) is not None
                        or now - cycle.resume_ts > DAY_SECONDS)
        return
    if cycle.dropped:
        cycle.outcome = "dropped"
    elif cycle.expired:
        cycle.outcome = "expired"
    elif cycle.done_ts is not None:
        # Registered but never resumed: the restart failed or never happened.
        cycle.outcome = "unconsumed" if now - cycle.done_ts > DAY_SECONDS else "open"
    elif cycle.last_request_ts is not None and now - cycle.last_request_ts > DAY_SECONDS:
        cycle.outcome = "skipped"
    elif (cycle.requests == 0 and cycle.first_offer_ts is not None
          and now - cycle.first_offer_ts > DAY_SECONDS):
        # Offered in the soft zone, never requested, no checkpoint: the offer was declined, not a skipped request.
        cycle.outcome = "declined"
    else:
        cycle.outcome = "open"
    cycle.closed = cycle.outcome != "open"


def build_cycles(events: List[Dict[str, Any]], now: float) -> List[Cycle]:
    """One Cycle per cycle_id, in order of its first event. Events without a cycle_id (before 0.2.0) are ignored."""
    cycles: Dict[str, Cycle] = {}
    for event in events:
        cycle_id = event.get("cycle_id")
        if not isinstance(cycle_id, str):
            continue
        cycle = cycles.get(cycle_id)
        if cycle is None:
            cycle = cycles[cycle_id] = Cycle(cycle_id=cycle_id, v=str(event.get("v", "unknown")),
                                             skill=str(event.get("skill", "unknown")))
        _apply(cycle, event)
    built = list(cycles.values())
    for cycle in built:
        _settle(cycle, built, now)
    return built
