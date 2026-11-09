import unittest
from datetime import datetime, timezone

from pitstop.claude.review_scan import AFTER_CHARS, BEFORE_CHARS, CUT_LINE, chat_excerpt
from tests.helpers import TempLayoutTestCase, write_jsonl


def stamp(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")


def user(ts, content, **extra):
    entry = {"type": "user", "isSidechain": False, "timestamp": stamp(ts),
             "message": {"role": "user", "content": content}}
    entry.update(extra)
    return entry


def assistant(ts, blocks, **extra):
    entry = {"type": "assistant", "isSidechain": False, "timestamp": stamp(ts),
             "message": {"role": "assistant", "content": blocks}}
    entry.update(extra)
    return entry


class ChatExcerptTest(TempLayoutTestCase):
    def write(self, entries):
        return write_jsonl(self.tmp / "t.jsonl", entries)

    def test_sizes(self):
        self.assertEqual((BEFORE_CHARS, AFTER_CHARS), (12000, 8000))

    def test_excerpt_window(self):
        path = self.write([user(5, "early"), user(15, "inside"), user(25, "late")])
        self.assertEqual(chat_excerpt(path, 10, 20, 1000, "tail"), "[user] inside")

    def test_open_end_reads_to_the_end(self):
        path = self.write([user(5, "early"), user(15, "inside"), user(25, "late")])
        self.assertEqual(chat_excerpt(path, 10, None, 1000, "head"), "[user] inside\n[user] late")

    def test_excerpt_caps_and_skips_tool_results(self):
        big = "x" * 50000
        entries = [user(1, "first question")]
        entries.append(assistant(2, [{"type": "text", "text": "reading"},
                                     {"type": "tool_use", "name": "Read",
                                      "input": {"file_path": "/a/" + "b" * 400}}]))
        entries.append(user(3, [{"type": "tool_result", "content": big}]))
        entries += [user(4 + i, "message %d %s" % (i, "y" * 80)) for i in range(100)]
        entries.append(user(200, "last question"))
        path = self.write(entries)
        for keep in ("tail", "head"):
            with self.subTest(keep=keep):
                text = chat_excerpt(path, 0, None, 2000, keep)
                self.assertNotIn(big[:100], text)
                self.assertLessEqual(len(text), 2000 + len(CUT_LINE) + 1)
        tail = chat_excerpt(path, 0, None, 2000, "tail")
        self.assertTrue(tail.startswith(CUT_LINE + "\n"))
        self.assertTrue(tail.endswith("[user] last question"))
        head = chat_excerpt(path, 0, None, 2000, "head")
        self.assertTrue(head.startswith("[user] first question\n[assistant] reading\n[tool] Read "))
        self.assertTrue(head.endswith("\n" + CUT_LINE))
        tool_line = head.split("\n")[2]
        self.assertTrue(tool_line.startswith('[tool] Read {"file_path": "/a/b'))
        self.assertLessEqual(len(tool_line), 207)

    def test_excerpt_skips_sidechain_and_meta(self):
        path = self.write([user(1, "side", isSidechain=True), user(2, "meta", isMeta=True),
                           assistant(3, [{"type": "text", "text": "side reply"}], isSidechain=True),
                           user(4, "kept")])
        self.assertEqual(chat_excerpt(path, 0, None, 1000, "head"), "[user] kept")

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            chat_excerpt(self.tmp / "nope.jsonl", 0, None, 1000, "head")


if __name__ == "__main__":
    unittest.main()
