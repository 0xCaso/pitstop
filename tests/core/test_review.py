import unittest

from pitstop.core.cycles import Cycle
from pitstop.core.review import pick_sample


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


if __name__ == "__main__":
    unittest.main()
