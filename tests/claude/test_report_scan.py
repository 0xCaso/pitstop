import json
import time
from pathlib import Path

from pitstop.claude.report_scan import calls_after, projects_dirs, skip_categories
from tests.helpers import TempLayoutTestCase, assistant_line, user_line, write_jsonl

T = 1800000000.0


def iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ts)) + ".%03dZ" % int(round((ts % 1) * 1000))


def said(text, ts, message_id="m1", sidechain=False):
    line = assistant_line(message_id=message_id, sidechain=sidechain, timestamp=iso(ts))
    line["message"]["content"] = [{"type": "text", "text": text}]
    return line


def skip(category, reason="the bug is half-way"):
    return "Ok.\n🔋 **pitstop** · skipped: %s — %s\nGoing on." % (category, reason)


class SkipCategoriesTest(TempLayoutTestCase):
    def test_skip_lines_are_counted_by_category(self):
        path = write_jsonl(self.tmp / "s.jsonl", [
            said(skip("debugging"), T + 10, "m1"),
            said(skip("debugging"), T + 20, "m2"),
            said(skip("ending-soon"), T + 30, "m3"),
            said(skip("brainstorming"), T + 500, "m4"),  # after the window
            said(skip("fine-editing"), T - 5, "m5"),  # before the window
        ])
        self.assertEqual(skip_categories(path, T, T + 100), {"debugging": 2, "ending-soon": 1})
        self.assertEqual(skip_categories(path, T, None)["brainstorming"], 1)

    def test_unknown_and_old_format_skips(self):
        path = write_jsonl(self.tmp / "s.jsonl", [
            said(skip("tired"), T + 1, "m1"),
            said("🔋 **pitstop** · skipped: a debugging session is half-way", T + 2, "m2"),
        ])
        self.assertEqual(skip_categories(path, T, None), {"other": 1, "unparsed": 1})

    def test_sidechain_messages_are_ignored(self):
        path = write_jsonl(self.tmp / "s.jsonl", [said(skip("debugging"), T + 1, sidechain=True)])
        self.assertEqual(skip_categories(path, T, None), {})

    def test_broken_and_partial_lines_are_skipped(self):
        # a broken line in the middle, a non-JSON line, and a last line still being written
        path = self.tmp / "s.jsonl"
        path.write_text("\n".join([json.dumps(said(skip("debugging"), T + 1, "m1")), "{broken",
                                   json.dumps(said(skip("ending-soon"), T + 3, "m3")), "not json at all",
                                   json.dumps(said(skip("other"), T + 2, "m2"))[:40]]), encoding="utf-8")
        self.assertEqual(skip_categories(path, T, None), {"debugging": 1, "ending-soon": 1})
        self.assertEqual(calls_after(path, T, None), 2)


class CallsAfterTest(TempLayoutTestCase):
    def test_calls_are_deduplicated_by_message_id(self):
        path = write_jsonl(self.tmp / "s.jsonl", [
            user_line(),
            said("a", T + 1, "m1"), said("b", T + 1.5, "m1"),  # one message streamed as two lines
            said("c", T + 2, "m2"),
            said("d", T + 3, "m3", sidechain=True),
            said("e", T + 50, "m4"),
        ])
        self.assertEqual(calls_after(path, T, T + 10), 2)
        self.assertEqual(calls_after(path, T, None), 3)

    def test_missing_file_counts_nothing(self):
        self.assertEqual(calls_after(self.tmp / "gone.jsonl", T, None), 0)
        self.assertEqual(skip_categories(self.tmp / "gone.jsonl", T, None), {})


class ProjectsDirsTest(TempLayoutTestCase):
    def test_projects_dirs_covers_all_profiles_once(self):
        home = self.tmp / "home"
        for name in (".claude", ".claude-work", ".claude-other"):
            (home / name / "projects").mkdir(parents=True)
        (home / ".claude-empty").mkdir()
        (home / ".claude.json").write_text("{}", encoding="utf-8")
        found = projects_dirs({"CLAUDE_CONFIG_DIR": str(home / ".claude-work")}, home)
        self.assertEqual(sorted(p.parent.name for p in found), [".claude", ".claude-other", ".claude-work"])
        self.assertEqual(found[0], home / ".claude-work" / "projects")
        extra = self.tmp / "elsewhere"
        (extra / "projects").mkdir(parents=True)
        self.assertIn(extra / "projects", projects_dirs({"CLAUDE_CONFIG_DIR": str(extra)}, home))
