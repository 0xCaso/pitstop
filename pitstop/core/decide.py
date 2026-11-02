"""Pure decision: should this hook event ask Claude for a pitstop?"""
from dataclasses import dataclass
from typing import Optional

from pitstop.core.config import Config
from pitstop.core.state import SessionState

NOOP = "noop"
REQUEST = "request"
OFFER = "offer"  # soft zone: pitstop only at a natural boundary; not a request
HARD = "hard"  # past the hard limit: pitstop required


@dataclass(frozen=True)
class Event:
    kind: str  # "stop" or "post_tool_batch"
    context_tokens: Optional[int]
    is_subagent: bool = False
    stop_hook_active: bool = False


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str


def segment_start(config: Config, state: SessionState, context_tokens: Optional[int]) -> None:
    """A context back under the soft limit was compacted or cleared outside pitstop: a new segment starts, so the
    next offer and request come again at their limits, not after the old ones."""
    if context_tokens is not None and context_tokens < config.soft_threshold_tokens:
        if state.requested_at_tokens is not None:
            # The requested cycle ended without a pitstop. A resumed segment (no request yet) keeps its cycle id.
            state.cycle_id = None
        state.requested_at_tokens = None
        state.offered_at_tokens = None


def decide(config: Config, state: SessionState, event: Event) -> Decision:
    """Three zones: soft (one offer at the end of a turn), threshold (one request per segment), hard (required:
    every Stop, and every retrigger step on tool batches)."""
    if not config.enabled:
        return Decision(NOOP, "disabled")
    if state.excluded:
        return Decision(NOOP, "excluded")
    if event.is_subagent:
        return Decision(NOOP, "subagent")
    if event.stop_hook_active:
        return Decision(NOOP, "stop_hook_active")
    tokens = event.context_tokens
    if tokens is None:
        return Decision(NOOP, "no_usage")
    if tokens < config.soft_threshold_tokens:
        return Decision(NOOP, "below_soft")
    if tokens < config.threshold_tokens:
        if event.kind != "stop":
            return Decision(NOOP, "soft")
        if state.offered_at_tokens is not None:
            return Decision(NOOP, "offered")
        return Decision(OFFER, "soft")
    last = state.requested_at_tokens
    if tokens < config.hard_threshold_tokens:
        return Decision(NOOP, "already_requested") if last is not None else Decision(REQUEST, "threshold")
    if event.kind == "stop":
        return Decision(HARD, "hard")
    if last is None or last < config.hard_threshold_tokens or tokens >= last + config.retrigger_step_tokens:
        return Decision(HARD, "hard")
    return Decision(NOOP, "already_requested")
