import unittest
from pathlib import Path

from pitstop.core.config import Config
from pitstop.core.decide import HARD, NOOP, OFFER, REQUEST, Decision, Event, decide, segment_start
from pitstop.core.state import SessionState


def stop(tokens, **kwargs):
    return Event(kind="stop", context_tokens=tokens, **kwargs)


def batch(tokens):
    return Event(kind="post_tool_batch", context_tokens=tokens)


class DecideTest(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.state = SessionState(session_id="s")

    def test_threshold_boundaries(self):
        for tokens, action in ((199999, NOOP), (200000, REQUEST), (200001, REQUEST)):
            with self.subTest(tokens=tokens):
                self.assertEqual(decide(self.config, self.state, batch(tokens)).action, action)

    def test_below_soft_reason(self):
        self.assertEqual(decide(self.config, self.state, stop(10)), Decision(NOOP, "below_soft"))

    def test_soft_boundaries(self):
        self.assertEqual(decide(self.config, self.state, stop(169999)), Decision(NOOP, "below_soft"))
        self.assertEqual(decide(self.config, self.state, stop(170000)), Decision(OFFER, "soft"))

    def test_soft_zone_batch_is_silent(self):
        self.assertEqual(decide(self.config, self.state, batch(180000)), Decision(NOOP, "soft"))

    def test_soft_zone_offers_once(self):
        self.state.offered_at_tokens = 175000
        self.assertEqual(decide(self.config, self.state, stop(195000)), Decision(NOOP, "offered"))

    def test_one_request_between_threshold_and_hard(self):
        self.state.requested_at_tokens = 212000
        for tokens in (262000, 279999):
            with self.subTest(tokens=tokens):
                self.assertEqual(decide(self.config, self.state, batch(tokens)), Decision(NOOP, "already_requested"))

    def test_hard_on_stop_always(self):
        self.state.requested_at_tokens = 285000
        self.assertEqual(decide(self.config, self.state, stop(286000)), Decision(HARD, "hard"))

    def test_hard_on_batch(self):
        cases = [(None, 280000, HARD), (212000, 281000, HARD), (285000, 300000, NOOP), (285000, 335000, HARD)]
        for requested, tokens, action in cases:
            with self.subTest(requested=requested, tokens=tokens):
                self.state.requested_at_tokens = requested
                self.assertEqual(decide(self.config, self.state, batch(tokens)).action, action)

    def test_segment_start_resets_offer(self):
        self.state.offered_at_tokens = 180000
        self.state.cycle_id = "c1"
        segment_start(self.config, self.state, 100000)
        self.assertIsNone(self.state.offered_at_tokens)
        self.assertEqual(self.state.cycle_id, "c1")

    def test_segment_start_keeps_state_inside_soft_zone(self):
        self.state.offered_at_tokens = 180000
        segment_start(self.config, self.state, 175000)
        self.assertEqual(self.state.offered_at_tokens, 180000)

    def test_guards(self):
        cases = [
            (Config(enabled=False), SessionState("s"), stop(300000), "disabled"),
            (Config(), SessionState("s", excluded=True), stop(300000), "excluded"),
            (Config(), SessionState("s"), stop(300000, is_subagent=True), "subagent"),
            (Config(), SessionState("s"), stop(300000, stop_hook_active=True), "stop_hook_active"),
            (Config(), SessionState("s"), stop(None), "no_usage"),
        ]
        for config, state, event, reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(decide(config, state, event), Decision(NOOP, reason))

    def test_custom_limits(self):
        config = Config(soft_threshold_tokens=40000, threshold_tokens=60000, hard_threshold_tokens=90000,
                        retrigger_step_tokens=10000)
        self.assertEqual(decide(config, self.state, stop(40000)).action, OFFER)
        self.assertEqual(decide(config, self.state, batch(60000)).action, REQUEST)
        self.state.requested_at_tokens = 90000
        self.assertEqual(decide(config, self.state, batch(99999)).action, NOOP)
        self.assertEqual(decide(config, self.state, batch(100000)).action, HARD)

    def test_context_back_under_the_threshold_starts_a_new_segment(self):
        # A /compact outside pitstop: without the reset the next request would wait until 270K.
        self.state.requested_at_tokens = 220000
        segment_start(self.config, self.state, 230000)
        self.assertEqual(self.state.requested_at_tokens, 220000)
        segment_start(self.config, self.state, None)
        self.assertEqual(self.state.requested_at_tokens, 220000)
        segment_start(self.config, self.state, 50000)
        self.assertIsNone(self.state.requested_at_tokens)
        self.assertEqual(decide(self.config, self.state, stop(200000)), Decision(REQUEST, "threshold"))


class CoreIndependenceTest(unittest.TestCase):
    def test_core_does_not_import_the_claude_adapter(self):
        core = Path(__file__).resolve().parents[2] / "pitstop" / "core"
        for path in sorted(core.glob("*.py")):
            with self.subTest(file=path.name):
                self.assertNotIn("pitstop.claude", path.read_text(encoding="utf-8"))
