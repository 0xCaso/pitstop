import json
import unittest

from pitstop.core.cycles import Cycle
from pitstop.core.review import count_resumed_since, pick_sample, sample_size, since_last_review
from pitstop.core.reviewlog import append_review, last_review_ts
from tests.helpers import TempLayoutTestCase


def cycle(cycle_id, outcome, resume_ts=None, checkpoint_path="/c.md"):
    return Cycle(cycle_id=cycle_id, v="0.3.1", skill="s", outcome=outcome, resume_ts=resume_ts,
                 checkpoint_path=checkpoint_path)


class PickSampleTest(unittest.TestCase):
    def test_pick_sample_newest_resumed_first(self):
        cycles = [cycle("a", "resumed", 10), cycle("b", "resumed", 30), cycle("c", "resumed", 20),
                  cycle("d", "dropped"), cycle("e", "skipped"), cycle("f", "resumed", 40, checkpoint_path=None)]
        self.assertEqual([c.cycle_id for c in pick_sample(cycles, 2)], ["b", "c"])

    def test_pick_sample_fewer_than_n(self):
        cycles = [cycle("a", "resumed", 10), cycle("b", "resumed", 30), cycle("d", "dropped")]
        self.assertEqual([c.cycle_id for c in pick_sample(cycles, 5)], ["b", "a"])


class ReviewLogTest(TempLayoutTestCase):
    def test_last_review_none_without_file(self):
        self.assertIsNone(last_review_ts(self.layout))

    def test_append_and_last_review(self):
        append_review(self.layout, 100.0, "/b1", 5, 3, 0)
        append_review(self.layout, 200.0, "/b2", 20, 1, 2)
        self.assertEqual(last_review_ts(self.layout), 200.0)
        last = self.layout.reviews_log.read_text(encoding="utf-8").splitlines()[-1]
        self.assertEqual(json.loads(last), {"ts": 200.0, "bundle": "/b2", "cycles": 20, "approved": 1, "rejected": 2})

    def test_last_review_skips_bad_lines(self):
        append_review(self.layout, 300.0, "/b1", 5, 3, 0)
        with self.layout.reviews_log.open("a", encoding="utf-8") as f:
            f.write("not json\n")
            f.write(json.dumps({"bundle": "/x"}) + "\n")
        append_review(self.layout, 100.0, "/b2", 5, 0, 0)
        self.assertEqual(last_review_ts(self.layout), 300.0)


def closed(cycle_id, start, closed_=True):
    return Cycle(cycle_id=cycle_id, v="0.5.0", skill="s", first_request_ts=start, outcome="resumed",
                 resume_ts=start + 10, checkpoint_path="/c.md", closed=closed_)


class SinceLastReviewTest(unittest.TestCase):
    def test_since_last_review_counts_closed_cycles_and_gaps(self):
        cycles = [closed("old", 50), closed("new", 150), closed("open", 160, closed_=False)]
        events = [{"action": "gap", "ts": 60}, {"action": "gap", "ts": 170}, {"action": "request", "ts": 180}]
        self.assertEqual(since_last_review(cycles, events, 100), (1, 1))
        self.assertEqual(since_last_review(cycles, events, None), (2, 2))

    def test_count_resumed_since(self):
        cycles = [cycle("a", "resumed", 50), cycle("b", "resumed", 150), cycle("c", "dropped")]
        self.assertEqual(count_resumed_since(cycles, 100), 1)
        self.assertEqual(count_resumed_since(cycles, None), 2)

    def test_sample_size_at_least_configured(self):
        self.assertEqual(sample_size(20, 3), 20)

    def test_sample_size_takes_all_since_review(self):
        self.assertEqual(sample_size(20, 45), 45)

    def test_sample_size_capped_at_100(self):
        self.assertEqual(sample_size(20, 187), 100)


if __name__ == "__main__":
    unittest.main()
