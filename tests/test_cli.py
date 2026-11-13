import io
import json
import time
from pathlib import Path

from pitstop.cli import main
from pitstop.core.config import load_config
from pitstop.core.fsutil import append_line
from pitstop.core.log import log_event, read_events
from pitstop.core.metrics import load_rows
from pitstop.core.reviewlog import append_review, last_review_ts
from pitstop.core.state import load_state
from pitstop.core.store import consume_pending
from tests.helpers import NOW, TempLayoutTestCase, assistant_line, user_line, write_jsonl

SESSION_ENV = {"CLAUDE_CODE_SESSION_ID": "s1"}


class CliTestCase(TempLayoutTestCase):
    def setUp(self):
        super().setUp()
        self.projects = self.tmp / "projects"
        self.transcript = write_jsonl(self.projects / "-work-repo" / "s1.jsonl", [
            {"type": "custom-title", "customTitle": "Piano pitstop", "sessionId": "s1"},
            user_line(),
            assistant_line(),
        ])

    def cli(self, *argv, stdin_text="", env=None):
        out = io.StringIO()
        code = main(list(argv), stdin=io.StringIO(stdin_text), stdout=out,
                    env=SESSION_ENV if env is None else env, layout=self.layout, projects_dir=self.projects, now=NOW)
        return code, out.getvalue()

    def consume(self):
        return consume_pending(self.layout, "s1", "/work/repo", NOW, 10)


class ToggleCommandsTest(CliTestCase):
    def test_on_off_and_notify_update_config(self):
        self.assertEqual(self.cli("off"), (0, "🔋 pitstop off in all sessions\n"))
        self.assertFalse(load_config(self.layout)[0].enabled)
        self.assertEqual(self.cli("on"), (0, "🔋 pitstop on\n"))
        self.assertTrue(load_config(self.layout)[0].enabled)
        self.assertEqual(self.cli("notify", "off"), (0, "🔋 pitstop notifications off\n"))
        self.assertFalse(load_config(self.layout)[0].notify)

    def test_metrics_toggle_and_status_line(self):
        self.assertIn("metrics: off\n", self.cli("status")[1])
        self.assertEqual(self.cli("metrics", "on"), (0, "🔋 pitstop metrics on\n"))
        self.assertTrue(load_config(self.layout)[0].metrics)
        self.assertIn("metrics: on\n", self.cli("status")[1])
        self.assertEqual(self.cli("metrics", "off"), (0, "🔋 pitstop metrics off\n"))
        self.assertFalse(load_config(self.layout)[0].metrics)

    def test_off_here_excludes_current_session_only(self):
        self.assertEqual(self.cli("off-here"), (0, "🔋 pitstop off in this session\n"))
        self.assertTrue(load_state(self.layout, "s1").excluded)
        self.assertFalse(load_state(self.layout, "s2").excluded)

    def test_session_commands_need_a_session(self):
        code, out = self.cli("off-here", env={})
        self.assertEqual(code, 1)
        self.assertIn("CLAUDE_CODE_SESSION_ID", out)

    def test_invalid_config_is_reported_not_overwritten(self):
        self.layout.base.mkdir(parents=True, exist_ok=True)
        self.layout.config.write_text("{nope", encoding="utf-8")
        code, out = self.cli("on")
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("🔋 pitstop · config.json"))
        self.assertEqual(self.layout.config.read_text(encoding="utf-8"), "{nope")


class MarkPendingTest(CliTestCase):
    def test_new_checkpoint_then_mark_pending_registers_resume(self):
        code, out = self.cli("new-checkpoint")
        self.assertEqual(code, 0)
        path = Path(out.strip())
        path.write_text("# Checkpoint", encoding="utf-8")
        code, out = self.cli("mark-pending", "--checkpoint", str(path), "--cwd", "/work/repo")
        self.assertEqual(code, 0)
        self.assertTrue(out.endswith("🔋 **pitstop** · done at 212K → back on track with a clean context\n"))
        record = self.consume()
        self.assertEqual((record.context_tokens, record.title, record.cwd, record.plan),
                         (212010, "Piano pitstop", "/work/repo", None))
        self.assertEqual([e["action"] for e in read_events(self.layout)], ["pitstop_done"])

    def test_manual_pitstop_gets_its_own_cycle_id(self):
        code, _ = self.cli("mark-pending", "--stdin", "--cwd", "/work/repo", stdin_text="# Checkpoint",
                           env={"CLAUDE_CODE_SESSION_ID": "s1", "CLAUDE_CODE_ENTRYPOINT": "cli"})
        self.assertEqual(code, 0)
        done = read_events(self.layout)[0]
        self.assertRegex(done["cycle_id"], r"^[0-9a-f]{12}$")
        self.assertEqual((done["host"], done["restart"]), ("cli", "clear"))
        self.assertEqual(self.consume().cycle_id, done["cycle_id"])
        self.cli("gap", "missing the table")
        self.assertNotIn("cycle_id", read_events(self.layout)[-1])

    def reread_checkpoint(self, *entries):
        return "# cp\n\n## Next action\nGo.\n## Chat-only text\n—\n## Re-read\n%s\n" % "\n".join(entries)

    def test_missing_reread_file_blocks_and_writes_nothing(self):
        (self.tmp / "docs").mkdir()
        code, out = self.cli("mark-pending", "--stdin", "--cwd", str(self.tmp),
                             stdin_text=self.reread_checkpoint("- `docs/plan.md:4` — the plan", "- `docs/b.md` — b"))
        self.assertEqual(code, 1)
        self.assertEqual(out, "🔋 pitstop · files under Re-read not found: docs/plan.md:4, docs/b.md\n")
        self.assertFalse(self.layout.checkpoints_dir.exists() and any(self.layout.checkpoints_dir.iterdir()))
        self.assertIsNone(self.consume())
        self.assertEqual(read_events(self.layout), [])

    def test_unchecked_entries_warn_and_register(self):
        code, out = self.cli("mark-pending", "--stdin", "--cwd", str(self.tmp),
                             stdin_text=self.reread_checkpoint("- `S/a.md` — alias", "- the PR text"))
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("warning: not checked under Re-read: 2 entries\n"))
        self.assertIsNotNone(consume_pending(self.layout, "s1", str(self.tmp), NOW, 10))

    def test_done_event_carries_checkpoint_stats_and_kind(self):
        notes = self.layout.checkpoints_dir / "cp-chat.md"
        notes.parent.mkdir(parents=True)
        notes.write_text("n", encoding="utf-8")
        (self.tmp / "repo-file.md").write_text("r", encoding="utf-8")
        text = ("# cp\n\n## Next action\nGo.\n## Chat-only text\nSee `%s` and `repo-file.md`.\n## Re-read\n"
                "- `S/x` — alias\n" % notes)
        code, _ = self.cli("mark-pending", "--stdin", "--kind", "other", "--cwd", str(self.tmp), stdin_text=text)
        self.assertEqual(code, 0)
        done = read_events(self.layout)[0]
        self.assertEqual({k: done[k] for k in ("checkpoint_bytes", "sections_filled", "chat_text_filled",
                                               "support_files", "unchecked_entries", "kind")},
                         {"checkpoint_bytes": len(text.encode("utf-8")), "sections_filled": 3,
                          "chat_text_filled": True, "support_files": 1, "unchecked_entries": 1, "kind": "other"})
        self.cli("mark-pending", "--stdin", "--cwd", str(self.tmp), stdin_text="# cp\n")
        self.assertEqual(read_events(self.layout)[-1]["kind"], "unknown")

    def test_restart_mode_follows_the_entrypoint(self):
        checkpoint = self.tmp / "cp.md"
        checkpoint.write_text("# Checkpoint", encoding="utf-8")
        for entrypoint, mode in (("sdk-ts", "compact"), ("sdk-py", "compact"), ("t3-code", "compact"), ("cli", "clear"),
                                  (None, "clear")):
            with self.subTest(entrypoint=entrypoint):
                env = dict(SESSION_ENV)
                if entrypoint is not None:
                    env["CLAUDE_CODE_ENTRYPOINT"] = entrypoint
                code, out = self.cli("mark-pending", "--checkpoint", str(checkpoint), env=env)
                self.assertEqual(code, 0)
                self.assertIn("restart: %s\n" % mode, out)
                self.assertEqual(self.consume().restart, mode)

    def test_restart_is_automatic_where_the_hooks_module_is_loaded(self):
        checkpoint = self.tmp / "cp.md"
        checkpoint.write_text("# Checkpoint", encoding="utf-8")
        # t3-code: an SDK host queues its own /compact even if the flag leaked into its environment.
        for entrypoint, mode in (("cli", "auto"), (None, "auto"), ("sdk-cli", "auto"), ("t3-code", "compact")):
            with self.subTest(entrypoint=entrypoint):
                env = dict(SESSION_ENV, PITSTOP_AUTO_RESTART="1")
                if entrypoint is not None:
                    env["CLAUDE_CODE_ENTRYPOINT"] = entrypoint
                code, out = self.cli("mark-pending", "--checkpoint", str(checkpoint), env=env)
                self.assertEqual(code, 0)
                self.assertIn("restart: %s\n" % mode, out)

    def test_compact_restart_spells_out_both_queued_messages(self):
        # The session follows the skill text it loaded first, so a later SKILL.md never reaches it: on
        # 8 Oct 2026 a pitstop queued the /compact but not the resume message (issue #1). This output is always current.
        checkpoint = self.tmp / "cp.md"
        checkpoint.write_text("# Checkpoint", encoding="utf-8")
        env = dict(SESSION_ENV, CLAUDE_CODE_ENTRYPOINT="sdk-ts")
        out = self.cli("mark-pending", "--checkpoint", str(checkpoint), env=env)[1]
        self.assertIn('queue 1: /compact One-line summary: "Resume from the pitstop checkpoint."\n', out)
        self.assertIn("queue 2: Resume from the pitstop checkpoint.\n", out)
        self.assertLess(out.index("queue 1:"), out.index("queue 2:"))
        out = self.cli("mark-pending", "--checkpoint", str(checkpoint), env=dict(SESSION_ENV))[1]
        self.assertNotIn("queue ", out)

    def test_cwd_defaults_to_transcript_and_plan_is_kept(self):
        checkpoint = self.tmp / "cp.md"
        checkpoint.write_text("# Checkpoint", encoding="utf-8")
        self.assertEqual(self.cli("mark-pending", "--checkpoint", str(checkpoint), "--plan", "docs/p.md")[0], 0)
        record = self.consume()
        self.assertEqual((record.cwd, record.plan), ("/work/repo", "docs/p.md"))

    def test_stdin_writes_the_checkpoint_itself(self):
        code, _ = self.cli("mark-pending", "--stdin", stdin_text="# Checkpoint da stdin\n")
        self.assertEqual(code, 0)
        record = self.consume()
        self.assertEqual(Path(record.checkpoint).read_text(encoding="utf-8"), "# Checkpoint da stdin\n")
        self.assertEqual(Path(record.checkpoint).parent, self.layout.checkpoints_dir.resolve())

    def test_missing_or_empty_checkpoint_fails_without_pending_record(self):
        empty = self.tmp / "empty.md"
        empty.write_text("", encoding="utf-8")
        for argv in (("--checkpoint", str(self.tmp / "missing.md")), ("--checkpoint", str(empty)), ("--stdin",)):
            with self.subTest(argv=argv):
                code, out = self.cli("mark-pending", *argv)
                self.assertEqual(code, 1)
                self.assertTrue(out.startswith("🔋 pitstop · "))
        self.assertIsNone(self.consume())

    def owed_transcript(self):
        text = {"type": "assistant", "isSidechain": False,
                "message": {"role": "assistant", "content": [{"type": "text", "text": "fatto"}]}}
        write_jsonl(self.transcript, [user_line(), text, user_line("e il test?"), assistant_line()])

    def test_owed_reply_blocks_the_checkpoint(self):
        self.owed_transcript()
        code, out = self.cli("mark-pending", "--stdin", stdin_text="# cp\nLast reply to the user: SENT\n")
        self.assertEqual(code, 1)
        self.assertIn("owed reply: 1 message(s)", out)
        self.assertIsNone(self.consume())

    def test_owed_reply_passes_when_not_sent_or_checked(self):
        self.owed_transcript()
        code, _ = self.cli("mark-pending", "--stdin", stdin_text="# cp\nLast reply to the user: NOT SENT\n")
        self.assertEqual(code, 0)
        code, _ = self.cli("mark-pending", "--stdin", "--reply-checked", stdin_text="# cp\n")
        self.assertEqual(code, 0)

    def test_unreadable_context_fails(self):
        write_jsonl(self.transcript, [user_line()])
        checkpoint = self.tmp / "cp.md"
        checkpoint.write_text("# Checkpoint", encoding="utf-8")
        code, out = self.cli("mark-pending", "--checkpoint", str(checkpoint))
        self.assertEqual(code, 1)
        self.assertIn("context", out)


class StatusAndGapTest(CliTestCase):
    def test_status_shows_state_context_and_pilot_numbers(self):
        log_event(self.layout, "cli", "pitstop_done", session_id="s1", context_tokens=212000)
        log_event(self.layout, "stop", "resume_base", session_id="s1", resume_base=70000)
        log_event(self.layout, "stop", "resume_base", session_id="s1", resume_base=90000)
        self.assertEqual(self.cli("gap", "missing", "the", "ledger"), (0, "🔋 checkpoint gap recorded\n"))
        code, out = self.cli("status")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), [
            "🔋 pitstop: on",
            "notifications: on",
            "metrics: off",
            "current context: 212K · soft 170K · threshold 200K · hard 280K",
            "pitstops: 1 · real resumes: 2 · gaps: 1",
            "real resume size: last 90K · median 80K",
            "folder: %s" % self.layout.base,
        ])
        gaps = [json.loads(line) for line in self.layout.gaps.read_text(encoding="utf-8").splitlines()]
        self.assertEqual((gaps[0]["session_id"], gaps[0]["text"]), ("s1", "missing the ledger"))
        self.assertNotIn("ledger", self.layout.log.read_text(encoding="utf-8"))

    def test_status_shows_folder(self):
        code, out = self.cli("status")
        self.assertEqual(code, 0)
        self.assertIn("folder: %s" % self.layout.base, out.splitlines())

    def test_status_reports_exclusion_and_missing_context(self):
        self.cli("off-here")
        self.assertIn("🔋 pitstop: off in this session", self.cli("status")[1])
        self.assertIn("current context: not available", self.cli("status", env={})[1])


def _iso(ts):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def _event(action, ts, cycle, session, v="0.2.0", **fields):
    entry = {"ts": ts, "event": "x", "action": action, "v": v, "skill": "abcd1234", "session_id": session,
             "cycle_id": cycle}
    entry.update(fields)
    return json.dumps(entry)


def _said(text, ts, message_id, session):
    return assistant_line(message_id=message_id, sessionId=session, timestamp=_iso(ts),
                          message={"id": message_id, "model": "claude-opus-5", "role": "assistant",
                                   "content": [{"type": "text", "text": text}],
                                   "usage": {"input_tokens": 1, "output_tokens": 1}})


class ReportTest(CliTestCase):
    def setUp(self):
        super().setUp()
        lines = [
            _event("request", NOW - 3000, "c1", "s1", context_tokens=210000, host="cli"),
            _event("pitstop_done", NOW - 2900, "c1", "s1", context_tokens=200000, restart="clear", kind="code",
                   checkpoint_bytes=3000, sections_filled=8, chat_text_filled=True, support_files=0),
            _event("resume", NOW - 2800, "c1", "s2"),
            _event("resume_base", NOW - 2790, "c1", "s2", resume_base=60000),
            _event("gap", NOW - 2700, "c1", "s2"),
            _event("pitstop_done", NOW - 2000, "c3", "s3", v="0.2.1", context_tokens=150000, restart="compact"),
            _event("pending_dropped", NOW - 1990, "c3", "s3", v="0.2.1"),
            _event("request", NOW - 10, "c2", "s2", context_tokens=205000),
        ]
        for line in lines:
            append_line(self.layout.log, line)
        write_jsonl(self.projects / "-work-repo" / "s1.jsonl", [
            _said("🔋 **pitstop** · skipped: debugging — half-way through a failing test", NOW - 2990, "m1", "s1"),
            _said("🔋 **pitstop** · skipped: other — after the pitstop", NOW - 2850, "m2", "s1"),
        ])
        write_jsonl(self.projects / "-work-repo" / "s2.jsonl", [
            _said("before the resume", NOW - 2850, "n0", "s2"),
            _said("one", NOW - 2795, "n1", "s2"),
            _said("two", NOW - 2700, "n2", "s2"),
            _said("three", NOW - 2600, "n3", "s2"),
            _said("after the next request", NOW - 5, "n4", "s2"),
        ])

    def test_report_writes_closed_cycles_once_and_prints_summary_by_version(self):
        code, out = self.cli("report")
        self.assertEqual(code, 0)
        rows = {r["cycle_id"]: r for r in load_rows(self.layout)}
        self.assertEqual(sorted(rows), ["c1", "c3"])
        self.assertEqual(rows["c1"]["skips"], {"debugging": 1})
        self.assertEqual((rows["c1"]["post_calls"], rows["c1"]["reduction"]), (3, 0.7))
        self.assertEqual(rows["c3"]["outcome"], "dropped")
        self.assertNotIn("half-way", self.layout.metrics.read_text(encoding="utf-8"))
        self.assertTrue(self.layout.report_stamp.exists())
        lines = out.splitlines()
        self.assertEqual(lines[0], "🔋 pitstop report · 2 new cycles · 2 in metrics.jsonl")
        self.assertIn("v 0.2.0 · cycles 1 · resumed 100% · median reduction 70% · gaps 100 per 100 resumes"
                      " · chat text 100%", lines)
        self.assertIn("  skips: debugging 1", lines)
        self.assertIn("  kind: code 1", lines)
        self.assertIn("v 0.2.1 · cycles 1 · resumed 0% · median reduction — · gaps — · chat text —", lines)
        code, out = self.cli("report")
        self.assertEqual(out.splitlines()[0], "🔋 pitstop report · 0 new cycles · 2 in metrics.jsonl")
        self.assertEqual(len(load_rows(self.layout)), 2)

    def test_report_quiet_prints_nothing(self):
        self.assertEqual(self.cli("report", "--quiet"), (0, ""))
        self.assertEqual(len(load_rows(self.layout)), 2)

    def test_report_imports_the_audit_first(self):
        audit = self.tmp / "audit-data.json"
        audit.write_text(json.dumps({"cycles": [
            {"done": {"ts": 1.0, "context_tokens": 100000, "checkpoint": "/nowhere.md", "_line": 3},
             "base": {"resume_base": 40000}, "status": "resumed", "post_calls": 4}]}), encoding="utf-8")
        code, out = self.cli("report", "--import-audit", str(audit))
        self.assertEqual(code, 0)
        self.assertEqual([r["cycle_id"] for r in load_rows(self.layout)], ["audit-3", "c1", "c3"])
        self.assertIn("v pre-0.2 · cycles 1 · resumed 100% · median reduction 60% · gaps — · chat text —", out.splitlines())


def _user_said(text, ts, session):
    return {"type": "user", "isSidechain": False, "sessionId": session, "timestamp": _iso(ts),
            "message": {"role": "user", "content": text}}


class ReviewBundleTest(CliTestCase):
    def setUp(self):
        super().setUp()
        self.checkpoints = {}
        for n, cycle in enumerate(("a", "b", "c")):
            t = NOW - 30000 + n * 10000
            path = self.tmp / ("cp-%s.md" % cycle)
            path.write_text("# pitstop checkpoint — %s\n## Next action\nship %s" % (cycle, cycle), encoding="utf-8")
            self.checkpoints[cycle] = path
            for line in (
                _event("request", t, cycle, "s-" + cycle, v="0.3.1", context_tokens=205000, host="t3-code"),
                _event("pitstop_done", t + 60, cycle, "s-" + cycle, v="0.3.1", context_tokens=210000,
                       restart="compact", kind="code", checkpoint=str(path)),
                _event("resume", t + 90, cycle, "r-" + cycle),
                _event("resume_base", t + 100, cycle, "r-" + cycle, resume_base=80000),
            ):
                append_line(self.layout.log, line)
            write_jsonl(self.projects / "-work-repo" / ("s-%s.jsonl" % cycle), [
                _user_said("too early %s" % cycle, t - 7200, "s-" + cycle),
                _user_said("please plan %s" % cycle, t - 100, "s-" + cycle),
                _said("planning %s" % cycle, t + 30, "m-" + cycle, "s-" + cycle),
                _said("after the done %s" % cycle, t + 70, "x-" + cycle, "s-" + cycle),
            ])
            write_jsonl(self.projects / "-work-repo" / ("r-%s.jsonl" % cycle), [
                _said("resumed %s" % cycle, t + 95, "q-" + cycle, "r-" + cycle),
            ])

    def bundle(self, *extra):
        code, out = self.cli("review-bundle", *extra)
        lines = out.splitlines()
        folder = next((Path(l[len("bundle: "):]) for l in lines if l.startswith("bundle: ")), None)
        return code, lines, folder

    def test_review_bundle_writes_one_file_per_cycle(self):
        code, lines, folder = self.bundle("--n", "2")
        self.assertEqual(code, 0)
        self.assertTrue(lines[0].startswith("🔋 pitstop report · "))
        self.assertEqual(folder.parent, self.layout.reviews_dir)
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["b.md", "c.md"])
        cycle_lines = [l for l in lines if l.startswith("cycle ")]
        self.assertEqual(cycle_lines, [
            "cycle c · v 0.3.1 · t3-code · 210K → 80K · %s" % (folder / "c.md"),
            "cycle b · v 0.3.1 · t3-code · 210K → 80K · %s" % (folder / "b.md"),
        ])
        text = (folder / "c.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# cycle c\nv 0.3.1 · host t3-code · kind code · restart compact · "
                                        "210000 → 80000 tokens · gaps 0\n"))
        before = text.split("## Before the restart\n")[1].split("## Checkpoint\n")[0]
        self.assertIn("[user] please plan c", before)
        self.assertIn("[assistant] planning c", before)
        self.assertNotIn("too early", before)
        self.assertNotIn("after the done", before)
        self.assertIn("## Checkpoint\n# pitstop checkpoint — c\n## Next action\nship c", text)
        self.assertIn("## After the resume\n[assistant] resumed c", text)

    def test_bundle_missing_transcript(self):
        (self.projects / "-work-repo" / "r-c.jsonl").unlink()
        code, lines, folder = self.bundle("--n", "1")
        self.assertEqual(code, 0)
        self.assertIn("## After the resume\ntranscript not found", (folder / "c.md").read_text(encoding="utf-8"))

    def test_bundle_missing_checkpoint(self):
        self.checkpoints["c"].unlink()
        code, lines, folder = self.bundle("--n", "1")
        self.assertEqual(code, 0)
        self.assertIn("## Checkpoint\ncheckpoint not found: %s" % self.checkpoints["c"],
                      (folder / "c.md").read_text(encoding="utf-8"))

    def test_bundle_no_cycles(self):
        self.layout.log.unlink()
        code, lines, folder = self.bundle()
        self.assertEqual(code, 1)
        self.assertEqual(lines[-1], "🔋 pitstop · no resumed cycles to review")
        self.assertIsNone(folder)

    def test_review_bundle_default_n_from_config(self):
        self.layout.config.write_text(json.dumps({"review_sample": 1}), encoding="utf-8")
        append_review(self.layout, NOW, "/old", 3, 0, 0)
        code, lines, folder = self.bundle()
        self.assertEqual(code, 0)
        self.assertEqual([p.name for p in folder.iterdir()], ["c.md"])

    def test_review_bundle_reads_all_resumed_since_last_review(self):
        self.layout.config.write_text(json.dumps({"review_sample": 1}), encoding="utf-8")
        append_review(self.layout, NOW - 20000, "/old", 3, 0, 0)  # after a's resume, before b's and c's
        code, lines, folder = self.bundle()
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["b.md", "c.md"])

    def test_review_bundle_without_a_logged_review_reads_only_review_sample(self):
        self.layout.config.write_text(json.dumps({"review_sample": 1}), encoding="utf-8")
        code, lines, folder = self.bundle()
        self.assertEqual([p.name for p in folder.iterdir()], ["c.md"])

    def test_review_bundle_n_clamped(self):
        code, lines, folder = self.bundle("--n", "0")
        self.assertEqual([p.name for p in folder.iterdir()], ["c.md"])

    def test_review_bundle_prints_since_last_review(self):
        code, lines, folder = self.bundle("--n", "1")
        self.assertEqual(lines[lines.index("bundle: %s" % folder) + 1],
                         "last review: none · 0 closed cycles · 0 gaps since")
        append_review(self.layout, NOW - 86400 * 3, "/old", 3, 0, 0)
        code, lines, folder = self.bundle("--n", "1")
        since = lines[lines.index("bundle: %s" % folder) + 1]
        self.assertTrue(since.startswith("last review: 20"), since)
        self.assertTrue(since.endswith(" · 0 closed cycles · 0 gaps since"), since)

    def test_review_done_logs_and_prints_final_line(self):
        self.assertEqual(self.cli("review-done", "--bundle", "/x/b", "--cycles", "5", "--approved", "3",
                                  "--rejected", "0"),
                         (0, "🔋 **pitstop** · review: 5 cycles · 3 approved · 0 rejected\n"))
        self.assertEqual(last_review_ts(self.layout), NOW)
        self.assertEqual(len(self.layout.reviews_log.read_text(encoding="utf-8").splitlines()), 1)

    def test_review_done_rejects_negative_counts(self):
        code, out = self.cli("review-done", "--bundle", "/x/b", "--cycles", "5", "--approved", "-1",
                             "--rejected", "0")
        self.assertNotEqual(code, 0)
        self.assertFalse(self.layout.reviews_log.exists())


    def test_review_done_uses_the_bundle_folder_time(self):
        self.cli("review-done", "--bundle", "/r/20261110-163603", "--cycles", "1", "--approved", "0",
                 "--rejected", "0")
        self.assertEqual(last_review_ts(self.layout), time.mktime(time.strptime("20261110-163603", "%Y%m%d-%H%M%S")))

    def test_review_done_rejects_an_empty_bundle(self):
        code, _ = self.cli("review-done", "--bundle", " ", "--cycles", "1", "--approved", "0", "--rejected", "0")
        self.assertNotEqual(code, 0)
        self.assertFalse(self.layout.reviews_log.exists())

class ConfigCommandTest(CliTestCase):
    def test_config_sets_threshold(self):
        self.assertEqual(self.cli("config", "threshold_tokens", "190000"),
                         (0, "🔋 pitstop · threshold_tokens = 190000\n"))
        saved = json.loads(self.layout.config.read_text(encoding="utf-8"))
        self.assertEqual(saved["threshold_tokens"], 190000)
        self.assertNotIn("soft_threshold_tokens", saved)
        self.assertNotIn("hard_threshold_tokens", saved)

    def test_config_sets_review_sample(self):
        self.assertEqual(self.cli("config", "review_sample", "8")[0], 0)
        self.assertEqual(load_config(self.layout)[0].review_sample, 8)

    def test_config_refuses_out_of_order(self):
        self.cli("config", "threshold_tokens", "200000")
        before = self.layout.config.read_bytes()
        code, out = self.cli("config", "soft_threshold_tokens", "250000")
        self.assertEqual(code, 1)
        self.assertEqual(out, "🔋 pitstop · limits out of order "
                              "(soft_threshold_tokens < threshold_tokens < hard_threshold_tokens)\n")
        self.assertEqual(self.layout.config.read_bytes(), before)

    def test_config_unknown_key(self):
        self.assertEqual(self.cli("config", "enabled", "1"), (1, "🔋 pitstop · unknown key: enabled\n"))
        self.assertFalse(self.layout.config.exists())

    def test_config_not_an_integer(self):
        self.assertEqual(self.cli("config", "review_sample", "five"),
                         (1, "🔋 pitstop · review_sample must be an integer\n"))
