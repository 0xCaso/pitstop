from pitstop.core.checkpoint import analyze_checkpoint
from tests.helpers import TempLayoutTestCase

TEMPLATE = """# pitstop checkpoint — topic

## Goal
Ship it.
## Current state
—
## Next action
Run the tests.
## Chat-only text
{chat}
## Re-read
{reread}
## Open questions
—
"""


class AnalyzeCheckpointTest(TempLayoutTestCase):
    def setUp(self):
        super().setUp()
        self.cwd = self.tmp / "repo"
        (self.cwd / "pitstop").mkdir(parents=True)
        (self.cwd / "pitstop" / "cli.py").write_text("x", encoding="utf-8")

    def analyze(self, chat="—", reread="—"):
        return analyze_checkpoint(TEMPLATE.format(chat=chat, reread=reread), str(self.cwd))

    def test_counts_sections_and_chat_text(self):
        (self.cwd / "table.md").write_text("| a |", encoding="utf-8")
        empty = self.analyze()
        self.assertEqual((empty.sections_filled, empty.chat_text_filled, empty.support_files), (2, False, 0))
        stats = self.analyze(chat="See `table.md` and `gone.md`.\n| figure | 12 |")
        self.assertEqual((stats.sections_filled, stats.chat_text_filled, stats.support_files), (3, True, 1))
        self.assertEqual(stats.bytes, len(TEMPLATE.format(chat="See `table.md` and `gone.md`.\n| figure | 12 |",
                                                          reread="—").encode("utf-8")))

    def test_reread_paths_with_lines_tilde_and_relative(self):
        (self.tmp / "y").write_text("y", encoding="utf-8")
        home = self.tmp / "home"
        (home).mkdir()
        (home / "x").write_text("x", encoding="utf-8")
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            stats = self.analyze(reread="- `pitstop/cli.py:118` — the flow\n- `pitstop/cli.py:10-20` — parser\n"
                                        "- `~/x` — notes\n- `../y` — sibling\n- `pitstop/gone.py:3` — typo")
        self.assertEqual(stats.missing, ["pitstop/gone.py:3"])
        self.assertEqual(stats.unchecked, [])

    def test_aliases_globs_branches_and_prose_are_unchecked(self):
        stats = self.analyze(reread="- `S/a.md` — spec alias\n- `08{7,8}_*.sql` — migrations\n"
                                    "- `s<N>.jpg` — screenshots\n- `pitstop/cli.py` su origin/staging\n"
                                    "- the PR description\n- `https://example.com/x` — page")
        self.assertEqual(stats.missing, [])
        self.assertEqual(len(stats.unchecked), 6)

    def test_no_reread_section_or_italian_headings_checks_nothing(self):
        text = "# checkpoint\n\n## Obiettivo\nX\n## Da rileggere\n- `pitstop/gone.py` — no\n"
        stats = analyze_checkpoint(text, str(self.cwd))
        self.assertEqual((stats.missing, stats.unchecked), ([], []))
        self.assertEqual(stats.sections_filled, 2)
