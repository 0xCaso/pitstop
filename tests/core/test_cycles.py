import unittest

from pitstop.core.cycles import build_cycles

DAY = 24 * 60 * 60
T = 1800000000.0


def ev(action, ts, cycle="c1", **fields):
    event = {"ts": ts, "event": "x", "action": action, "v": "0.2.0", "skill": "abcd1234", "session_id": "s1"}
    if cycle is not None:
        event["cycle_id"] = cycle
    event.update(fields)
    return event


REQUEST = ev("request", T, context_tokens=212000, host="cli")
DONE = ev("pitstop_done", T + 60, context_tokens=215000, restart="clear", kind="code", checkpoint_bytes=3000,
          sections_filled=8, chat_text_filled=True, support_files=1, unchecked_entries=2)


class BuildCyclesTest(unittest.TestCase):
    def one(self, events, now=T + 120):
        cycles = build_cycles(events, now)
        self.assertEqual(len(cycles), 1)
        return cycles[0]

    def test_resumed_cycle_closes_when_the_resumed_session_is_asked_again(self):
        events = [REQUEST, DONE, ev("resume", T + 90, session_id="s2"),
                  ev("resume_base", T + 100, session_id="s2", resume_base=70000),
                  ev("gap", T + 110, session_id="s2")]
        self.assertFalse(self.one(events).closed)  # the resumed session is still going: calls and gaps still grow
        cycle = build_cycles(events + [ev("request", T + 200, cycle="c2", session_id="s2")], T + 300)[0]
        self.assertEqual((cycle.outcome, cycle.closed), ("resumed", True))
        self.assertEqual((cycle.cycle_id, cycle.v, cycle.skill, cycle.host, cycle.kind), ("c1", "0.2.0", "abcd1234",
                                                                                      "cli", "code"))
        self.assertEqual((cycle.first_request_ts, cycle.request_tokens, cycle.requests), (T, 212000, 1))
        self.assertEqual((cycle.done_ts, cycle.done_tokens, cycle.restart), (T + 60, 215000, "clear"))
        self.assertEqual(cycle.checkpoint, {"checkpoint_bytes": 3000, "sections_filled": 8, "chat_text_filled": 1,
                                            "support_files": 1, "unchecked_entries": 2})
        self.assertEqual((cycle.resume_ts, cycle.resume_session, cycle.resume_base, cycle.gaps),
                         (T + 90, "s2", 70000, 1))
        self.assertEqual(cycle.session, "s1")

    def test_resumed_cycle_closes_at_a_manual_pitstop_of_the_resumed_session(self):
        events = [REQUEST, DONE, ev("resume", T + 90, session_id="s2"),
                  ev("pitstop_done", T + 200, cycle="c2", session_id="s2"),
                  ev("request", T + 250, cycle="c3", session_id="s9")]
        self.assertTrue(build_cycles(events, T + 300)[0].closed)
        self.assertFalse(build_cycles(events[:3] + events[4:], T + 300)[0].closed)

    def test_resumed_without_resume_base_closes_after_a_day(self):
        events = [REQUEST, DONE, ev("resume", T + 90, session_id="s2")]
        self.assertFalse(self.one(events).closed)
        self.assertTrue(self.one(events, now=T + 90 + DAY + 1).closed)

    def test_dropped(self):
        cycle = self.one([REQUEST, DONE, ev("pending_dropped", T + 90)])
        self.assertEqual((cycle.outcome, cycle.closed), ("dropped", True))

    def test_expired(self):
        cycle = self.one([REQUEST, DONE, ev("resume_expired", T + 4000, session_id="s2")])
        self.assertEqual((cycle.outcome, cycle.closed), ("expired", True))

    def test_done_without_outcome_is_unconsumed_after_a_day(self):
        self.assertEqual(self.one([REQUEST, DONE]).outcome, "open")
        cycle = self.one([REQUEST, DONE], now=T + 60 + DAY + 1)
        self.assertEqual((cycle.outcome, cycle.closed), ("unconsumed", True))

    def test_requests_only_are_skipped_after_a_day(self):
        self.assertEqual(self.one([REQUEST]).outcome, "open")
        cycle = self.one([REQUEST], now=T + DAY + 1)
        self.assertEqual((cycle.outcome, cycle.closed, cycle.done_ts), ("skipped", True, None))

    def test_open_cycle_is_not_closed(self):
        cycle = self.one([REQUEST])
        self.assertEqual((cycle.outcome, cycle.closed), ("open", False))

    def test_requests_of_one_segment_count_once(self):
        second = ev("request", T + 30, context_tokens=262000)
        cycle = self.one([REQUEST, second], now=T + 30 + DAY + 1)
        self.assertEqual((cycle.requests, cycle.request_tokens, cycle.outcome), (2, 212000, "skipped"))
        # skipped counts from the last request
        self.assertEqual(self.one([REQUEST, second], now=T + DAY + 10).outcome, "open")

    def test_events_without_cycle_id_are_ignored(self):
        events = [ev("request", T, cycle=None), ev("pitstop_done", T + 1, cycle=None), REQUEST]
        self.assertEqual([c.cycle_id for c in build_cycles(events, T + 5)], ["c1"])

    def test_cycles_come_in_order_of_their_first_event(self):
        events = [ev("request", T + 10, cycle="b"), ev("request", T + 20, cycle="a"), ev("gap", T + 30, cycle="b")]
        self.assertEqual([c.cycle_id for c in build_cycles(events, T + 40)], ["b", "a"])
