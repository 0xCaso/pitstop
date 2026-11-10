import dataclasses
import unittest

from pitstop.claude.messages import (
    badge_title,
    banner_resumed,
    banner_triggered,
    batch_request_context,
    done_line,
    hard_request_context,
    offer_context,
    previous_transcript,
    resume_context,
    resumed_line,
    stop_request_context,
)
from pitstop.core.store import PendingRecord

RECORD = PendingRecord(checkpoint="/cp/20260913-101010-s1.md", session_id="s1", cwd="/work/repo",
                       context_tokens=212000, created_at=1.0, title="Titolo")


class MessagesTest(unittest.TestCase):
    def test_fixed_formats(self):
        self.assertEqual(banner_triggered(212345), "🔋 pitstop · 212K → pitting at the next clean point")
        self.assertEqual(banner_resumed(212999), "🔋 pitstop · resumed from 212K")
        self.assertEqual(done_line(212000), "🔋 **pitstop** · done at 212K → back on track with a clean context")
        self.assertEqual(resumed_line(212000), "🔋 **pitstop** · resumed from 212K · Where we were:")

    def test_badge_title_has_no_double_prefix(self):
        self.assertEqual(badge_title("Piano pitstop"), "🔋 Piano pitstop")
        self.assertEqual(badge_title("🔋 Piano pitstop"), "🔋 Piano pitstop")
        self.assertIsNone(badge_title(None))
        self.assertIsNone(badge_title("  "))

    def test_resume_context_names_the_plan_only_when_set(self):
        self.assertNotIn("subagent-driven-development", resume_context(RECORD, "# C", cli="/c"))
        with_plan = dataclasses.replace(RECORD, plan="docs/superpowers/plans/p.md")
        self.assertIn(
            "resume the plan `docs/superpowers/plans/p.md` from its ledger with superpowers:subagent-driven-development",
            resume_context(with_plan, "# C", cli="/c"),
        )

    def test_request_contexts_carry_the_values_the_skill_needs(self):
        for builder in (stop_request_context, batch_request_context):
            with self.subTest(builder=builder.__name__):
                text = builder(tokens=212345, threshold=200000, step=50000, cwd="/work/repo", cli="/repo/bin/pitstop",
                               skill="/repo/skills/pitstop/SKILL.md", background_tasks=None, hard=280000)
                for expected in ("[pitstop]", "212K", "cwd: /work/repo", "/usr/bin/python3 /repo/bin/pitstop",
                                 "/repo/skills/pitstop/SKILL.md", "Automatic pitstop",
                                 "the next request comes at the 280K hard limit"):
                    self.assertIn(expected, text)

    def test_modes_and_background_tasks(self):
        stop_text = stop_request_context(212345, 200000, 50000, "/w", "/c", "/s", 2, hard=280000)
        batch_text = batch_request_context(212345, 200000, 50000, "/w", "/c", "/s", None, hard=280000)
        self.assertIn("mode: conversation", stop_text)
        self.assertIn("background tasks running: 2", stop_text)
        self.assertIn("clean boundary", batch_text)
        self.assertIn("background tasks running: unknown", batch_text)

    def test_resume_context_embeds_checkpoint_and_resumed_line(self):
        text = resume_context(RECORD, "# Checkpoint\nobiettivo {non un placeholder}", cli="/repo/bin/pitstop")
        self.assertIn("# Checkpoint\nobiettivo {non un placeholder}", text)
        self.assertIn(RECORD.checkpoint, text)
        self.assertIn("🔋 **pitstop** · resumed from 212K · Where we were:", text)
        self.assertIn('/usr/bin/python3 /repo/bin/pitstop gap "', text)


class PreviousTranscriptTest(unittest.TestCase):
    def test_resume_context_sends_an_owed_reply_before_the_next_action(self):
        text = resume_context(RECORD, "# cp", cli="/x/bin/pitstop")
        owed = text.index("Last reply to the user: NOT SENT")
        self.assertLess(owed, text.index("Continue from the next action"))
        self.assertIn("Never tell the user it was already sent", text)

    def test_resume_context_points_to_the_previous_transcript(self):
        record = dataclasses.replace(RECORD, project_dir="/p")
        self.assertEqual(previous_transcript(record), "/p/s1.jsonl")
        context = resume_context(record, "# cp", cli="/x/bin/pitstop")
        self.assertIn("Transcript before the restart: /p/s1.jsonl", context)
        step5 = context.split("\n5. ", 1)[1].split("\n", 1)[0]
        self.assertIn("/p/s1.jsonl", step5)
        self.assertIn("gap", step5)

    def test_without_project_dir_there_is_no_transcript_line(self):
        self.assertIsNone(previous_transcript(RECORD))
        self.assertNotIn("Transcript before the restart", resume_context(RECORD, "# cp", cli="/x/bin/pitstop"))


class ZoneMessagesTest(unittest.TestCase):
    def test_offer_context_first_line_and_mode(self):
        text = offer_context(175000, 170000, 200000, "/w", "/cli", "/skill")
        self.assertTrue(text.startswith(
            "[pitstop] Main-thread context is 175K, in the soft zone (170K–200K). Pitstop only if the work is at a "
            "natural boundary right now; otherwise carry on and print nothing.\n"))
        self.assertIn("- mode: offer\n", text)
        self.assertIn("- cwd: /w\n", text)

    def test_hard_context_first_line_and_mode(self):
        text = hard_request_context(285000, 280000, 50000, "/w", "/cli", "/skill", 2)
        self.assertTrue(text.startswith(
            "[pitstop] Main-thread context is 285K, past the 280K hard limit. Pitstop now. Skip only if subagents or "
            "background tasks are running (category background-tasks).\n"))
        self.assertIn("- mode: hard\n", text)
        self.assertIn("- background tasks running: 2\n", text)
