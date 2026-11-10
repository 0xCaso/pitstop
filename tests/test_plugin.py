import json
import unittest

from pitstop.claude import messages
from pitstop.claude.hooks import CLI_PATH, SKILL_PATH
from tests.helpers import REPO_ROOT


class PluginFilesTest(unittest.TestCase):
    def test_manifest(self):
        manifest = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual((manifest["name"], manifest["author"]["name"]), ("pitstop", "Matteo Casonato"))
        self.assertNotIn("skills", manifest)

    def test_hooks_call_bin_pitstop_with_system_python(self):
        config = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(config["modules"], ["./register.ts"])
        self.assertTrue((REPO_ROOT / "hooks" / "register.ts").is_file())
        hooks = config["hooks"]
        self.assertEqual(set(hooks), {"Stop", "PostToolBatch", "UserPromptSubmit", "SessionStart", "PreToolUse"})
        # Every source (startup, resume, clear, compact): the daily report; the resume itself is for compact only.
        self.assertEqual(len(hooks["SessionStart"]), 1)
        self.assertNotIn("matcher", hooks["SessionStart"][0])
        self.assertEqual(hooks["PreToolUse"][0]["matcher"], "mcp__t3-code__t3_thread_send")
        for event, arg in (("Stop", "stop"), ("PostToolBatch", "post-tool-batch"),
                           ("UserPromptSubmit", "user-prompt-submit"), ("SessionStart", "session-start"),
                           ("PreToolUse", "pre-tool-use")):
            with self.subTest(event=event):
                command = hooks[event][0]["hooks"][0]["command"]
                self.assertEqual(command, '/usr/bin/python3 "${CLAUDE_PLUGIN_ROOT}/bin/pitstop" hook ' + arg)

    def test_skill_has_frontmatter_sections_and_fixed_lines(self):
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: pitstop\n"))
        for needle in ("## Commands", "## Automatic pitstop", "## Manual pitstop", "## Checkpoint procedure",
                       "## Checkpoint content", "## Resuming", "🔋 **pitstop** · skipped:",
                       "Run /clear", "restart: auto", "restart: compact", "t3_thread_send", "Compact context",
                       '/usr/bin/python3 "${CLAUDE_PLUGIN_ROOT}/bin/pitstop"'):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_skill_queues_exactly_the_command_the_guard_recognises(self):
        self.assertIn("`%s`" % messages.COMPACT_COMMAND, SKILL_PATH.read_text(encoding="utf-8"))

    def test_hooks_module_resumes_with_the_summary_the_session_start_hook_expects(self):
        module = (REPO_ROOT / "hooks" / "register.ts").read_text(encoding="utf-8")
        self.assertIn("const SUMMARY = '%s'" % messages.COMPACT_SUMMARY, module)

    def test_paths_used_by_hooks_exist(self):
        self.assertTrue(CLI_PATH.is_file())
        self.assertTrue(SKILL_PATH.is_file())

    def test_skill_registers_in_one_call_with_a_quoted_heredoc(self):
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("mark-pending --stdin --kind", text)
        self.assertIn("<<'PITSTOP_EOF'", text)

    def test_skill_template_has_chat_only_text_section(self):
        text = SKILL_PATH.read_text(encoding="utf-8")
        template = text.split("```markdown", 1)[1].split("```", 1)[0]
        self.assertIn("## Next action\n<one precise action>\n## Chat-only text\n", template)

    def test_skill_template_has_no_discarded_section(self):
        template = SKILL_PATH.read_text(encoding="utf-8").split("```markdown\n# pitstop checkpoint", 1)[1].split("```", 1)[0]
        self.assertNotIn("## Discarded", template)

    def test_skill_template_has_reply_status_line(self):
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("Last reply to the user:", text)
        self.assertIn("NOT SENT", text)

    def test_skill_sends_an_owed_reply(self):
        text = SKILL_PATH.read_text(encoding="utf-8")
        procedure = text.split("## Checkpoint procedure", 1)[1]
        self.assertTrue(procedure.lstrip().startswith("1. If a reply to the user is owed"))
        self.assertIn("anything still owed makes it NOT SENT", text)
        resuming = text.split("## Resuming", 1)[1].split("## Review", 1)[0]
        self.assertIn("send that reply first", resuming)

    def test_skill_has_exact_text_and_assumed_rules(self):
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("never as a description", text)
        self.assertIn("(assumed)", text)

    def test_skill_lists_the_fixed_skip_categories(self):
        text = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("🔋 **pitstop** · skipped: <category> — <reason>", text)
        for category in ("debugging", "fine-editing", "ending-soon", "background-tasks", "brainstorming", "other"):
            with self.subTest(category=category):
                self.assertIn("`%s`" % category, text)

    def test_skill_documents_metrics_and_report_commands(self):
        text = SKILL_PATH.read_text(encoding="utf-8")
        for needle in ("`/pitstop metrics on`", "`pitstop metrics on`", "`/pitstop report`", "`pitstop report`"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)


class ZonesPluginTest(unittest.TestCase):
    def test_skill_has_offer_and_hard_modes_and_chat_heavy_checkpoints(self):
        text = SKILL_PATH.read_text(encoding="utf-8")
        for needle in ("mode: offer", "mode: hard", "For --kind other",
                       "an offer is not a request and needs no skip line",
                       "No exceptions except [background-tasks]."):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_readme_documents_the_three_limits(self):
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for needle in ("soft_threshold_tokens", "hard_threshold_tokens"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_versions_are_0_5_0(self):
        for path in (REPO_ROOT / "package.json", REPO_ROOT / ".claude-plugin" / "plugin.json"):
            with self.subTest(path=path.name):
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["version"], "0.5.1")


class ReviewPluginTest(unittest.TestCase):
    def test_skill_lists_review(self):
        text = SKILL_PATH.read_text(encoding="utf-8")
        description = text.split("description:", 1)[1].split("\n", 1)[0]
        self.assertIn("review", description)
        for needle in ("| `/pitstop review` |", "\n## Review\n", "`pitstop review-bundle`",
                       "`pitstop config <key> <value>`", "Approved rules",
                       "🔋 **pitstop** · review: <N> cycles · <A> approved · <R> rejected"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_review_survives_a_slow_first_report_and_no_proposals(self):
        review = SKILL_PATH.read_text(encoding="utf-8").split("\n## Review\n", 1)[1]
        for needle in ("timeout of 600000 ms", "No proposals: skip to step 6", "each proposal gets its own answer"):
            with self.subTest(needle=needle):
                self.assertIn(needle, review)
        self.assertNotIn("one proposal at a time", review)

    def test_review_logs_the_review_and_keeps_rules_general(self):
        review = SKILL_PATH.read_text(encoding="utf-8").split("\n## Review\n", 1)[1]
        for needle in ("`pitstop review-done --bundle <bundle> --cycles <N> --approved <A> --rejected <R>`",
                       "at least 3 cycles", "Not proposed", "SKILL.md"):
            with self.subTest(needle=needle):
                self.assertIn(needle, review)

    def test_readme_documents_review_log_and_reminder(self):
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for needle in ("review_remind_cycles", "review_remind_gaps", "reviews.jsonl", "review-reminder-last.txt",
                       "review-reminder.lock", "pitstop review-done", "/pitstop notify off"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_readme_documents_review_and_config(self):
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for needle in ("`/pitstop review`", "`review_sample`", "pitstop config"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
