import json

from pitstop.core.fsutil import append_line
from pitstop.core.metrics import append_rows, import_audit, load_rows
from tests.helpers import TempLayoutTestCase


def row(cycle_id, **fields):
    base = {"cycle_id": cycle_id, "v": "0.2.0", "skill": "abcd1234", "outcome": "resumed", "done_tokens": 200000,
            "resume_base": 60000}
    base.update(fields)
    return base


class MetricsTest(TempLayoutTestCase):
    def test_append_is_idempotent_by_cycle_id(self):
        self.assertEqual(append_rows(self.layout, [row("c1"), row("c2")]), 2)
        self.assertEqual(append_rows(self.layout, [row("c2"), row("c3"), row("c3")]), 1)
        self.assertEqual([r["cycle_id"] for r in load_rows(self.layout)], ["c1", "c2", "c3"])

    def test_load_rows_skips_broken_lines(self):
        append_rows(self.layout, [row("c1")])
        append_line(self.layout.metrics, "{broken")
        self.assertEqual([r["cycle_id"] for r in load_rows(self.layout)], ["c1"])

    def test_rows_never_carry_free_text(self):
        append_rows(self.layout, [row("c1", reason="the user was debugging the parser", resume_session="s2",
                                      skips={"debugging": 2, "debugging the parser": 1},
                                      checkpoint={"checkpoint_bytes": 3000, "title": 7},
                                      post_calls=12, reduction=0.7)])
        (stored,) = load_rows(self.layout)
        self.assertNotIn("reason", stored)
        self.assertNotIn("resume_session", stored)
        self.assertEqual(stored["skips"], {"debugging": 2})
        self.assertEqual(stored["checkpoint"], {"checkpoint_bytes": 3000})
        self.assertEqual((stored["post_calls"], stored["reduction"]), (12, 0.7))
        self.assertNotIn("debugging the parser", self.layout.metrics.read_text(encoding="utf-8"))

    def test_import_audit_maps_cycles_and_measures_surviving_checkpoints(self):
        kept = self.tmp / "kept.md"
        kept.write_text("# pitstop checkpoint\n\n## Goal\nship\n\n## Chat-only text\n- a table\n\n## Open questions\n—\n",
                        encoding="utf-8")
        audit = self.tmp / "audit-data.json"
        audit.write_text(json.dumps({"summary": {}, "cycles": [
            {"done": {"ts": 10.0, "context_tokens": 200000, "checkpoint": str(kept), "_line": 5},
             "request": {"ts": 5.0, "context_tokens": 190000}, "resume": {"ts": 20.0},
             "base": {"resume_base": 50000}, "status": "resumed", "post_calls": 11, "project": "secret-project"},
            {"done": {"ts": 30.0, "context_tokens": 100000, "checkpoint": str(self.tmp / "gone.md"), "_line": 9},
             "request": None, "resume": None, "base": None, "status": "dropped"},
        ]}), encoding="utf-8")
        first, second = import_audit(audit)
        self.assertEqual((first["cycle_id"], first["v"], first["skill"], first["outcome"]),
                         ("audit-5", "pre-0.2", "unknown", "resumed"))
        self.assertEqual((first["done_tokens"], first["resume_base"], first["post_calls"], first["reduction"]),
                         (200000, 50000, 11, 0.75))
        self.assertEqual((first["first_request_ts"], first["request_tokens"], first["done_ts"], first["resume_ts"]),
                         (5.0, 190000, 10.0, 20.0))
        self.assertEqual(first["checkpoint"]["sections_filled"], 2)
        self.assertEqual(first["checkpoint"]["chat_text_filled"], 1)
        self.assertGreater(first["checkpoint"]["checkpoint_bytes"], 0)
        self.assertNotIn("project", first)
        self.assertEqual((second["cycle_id"], second["outcome"], second["checkpoint"]), ("audit-9", "dropped", {}))
        self.assertNotIn("reduction", second)
        self.assertEqual(append_rows(self.layout, [first, second]), 2)
        self.assertEqual(append_rows(self.layout, import_audit(audit)), 0)
