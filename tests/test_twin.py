"""The twin harness in scripts/ (a research tool, not shipped): the parts that keep arms inside the snapshot."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / ("%s.py" % name))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load("twin_guard")
twin = _load("twin")


class GuardTest(unittest.TestCase):
    roots = ["/snap/c1", "/proj/twins"]

    def test_file_tools_outside_the_snapshot_are_refused(self):
        self.assertIsNone(guard.decide("Read", {"file_path": "/snap/c1/repo/a.py"}, self.roots))
        self.assertIn("outside", guard.decide("Read", {"file_path": "/Users/me/repo/a.py"}, self.roots))
        self.assertIn("outside", guard.decide("Glob", {"pattern": "*", "path": "/Users/me"}, self.roots))
        self.assertIn("outside", guard.decide("Write", {"file_path": "/snap/c1/../other/x"}, self.roots))

    def test_bash_paths_outside_and_parent_paths_are_refused(self):
        self.assertIsNone(guard.decide("Bash", {"command": "cat /snap/c1/repo/a && /usr/bin/git status"},
                                       self.roots, "/snap/c1/repo"))
        self.assertIn("outside", guard.decide("Bash", {"command": "cat ~/.claude/x"}, self.roots, "/snap/c1"))
        self.assertIn("outside", guard.decide("Bash", {"command": "cat ../../b.txt"}, self.roots, "/snap/c1/repo"))
        self.assertIsNone(guard.decide("Bash", {"command": "cat ../repo/a"}, self.roots, "/snap/c1/repo"))

    def test_heredoc_text_is_not_read_as_paths(self):
        command = "cat > /snap/c1/body.html <<'EOF'\n</head>\n<a href=\"/about\">x</a>\nEOF\nls /Users/me"
        self.assertIn("/Users/me", guard.decide("Bash", {"command": command}, self.roots, "/snap/c1"))
        self.assertIsNone(guard.decide("Bash", {"command": command.rsplit("\n", 1)[0]}, self.roots, "/snap/c1"))

    def test_apps_and_sed_slashes_are_not_paths(self):
        command = "'/Applications/Google Chrome.app/x' --headless; sed -i 's/- (20)/-/' f.md"
        self.assertIsNone(guard.decide("Bash", {"command": command}, self.roots, "/snap/c1"))

    def test_home_through_variables_or_tilde_is_refused(self):
        for command in ('cat "$HOME/.claude/x"', "ls ${CLAUDE_CONFIG_DIR}", "cd ~ && cat .claude/x",
                        "cat $TMPDIR/x", "cd / && cat Users/me/f"):
            self.assertIn("outside", guard.decide("Bash", {"command": command}, self.roots, "/snap/c1"))

    def test_heredoc_fed_to_an_interpreter_is_scanned(self):
        for command in ("python3 - <<'EOF'\nprint(open('/Users/me/repo/f').read())\nEOF",
                        "cat <<EOF | python3\nprint(open('/Users/me/x').read())\nEOF"):
            self.assertIn("/Users/me", guard.decide("Bash", {"command": command}, self.roots, "/snap/c1"))

    def test_network_and_push_are_refused(self):
        for command in ("git push origin main", "gh pr create", "curl -s https://x.dev", "npm publish",
                        "cd x && GH_TOKEN=t gh pr create", "echo $(curl -s x.dev)", "git -C repo push",
                        "/usr/bin/curl x.dev", 'bash -c "curl x"', "timeout 5 curl x"):
            self.assertIn("no network", guard.decide("Bash", {"command": command}, self.roots, "/snap/c1"))

    def test_hook_prints_a_deny_decision_and_logs_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "refused.jsonl"
            event = {"tool_name": "Read", "tool_input": {"file_path": "/etc/passwd"}, "cwd": tmp}
            out = subprocess.run([sys.executable, str(SCRIPTS / "twin_guard.py")], input=json.dumps(event),
                                 capture_output=True, text=True,
                                 env=dict(os.environ, TWIN_ALLOW=tmp, TWIN_GUARD_LOG=str(log)))
            decision = json.loads(out.stdout)["hookSpecificOutput"]
            self.assertEqual(decision["permissionDecision"], "deny")
            self.assertEqual(json.loads(log.read_text())["tool"], "Read")


class WaggleStubTest(unittest.TestCase):
    def test_records_an_ask_and_answers_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "asks.jsonl"
            lines = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                     {"jsonrpc": "2.0", "method": "notifications/initialized"},
                     {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                     {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                      "params": {"name": "waggle_ask", "arguments": {"title": "Which one?"}}}]
            out = subprocess.run([sys.executable, str(SCRIPTS / "twin_waggle_stub.py")],
                                 input="\n".join(json.dumps(x) for x in lines) + "\n", capture_output=True,
                                 text=True, env=dict(os.environ, TWIN_WAGGLE_LOG=str(log)))
            replies = [json.loads(x) for x in out.stdout.splitlines()]
            self.assertEqual([r["id"] for r in replies], [1, 2, 3])
            self.assertIn("waggle_ask", [t["name"] for t in replies[1]["result"]["tools"]])
            self.assertEqual(json.loads(replies[2]["result"]["content"][0]["text"])["status"], "pending")
            self.assertEqual(json.loads(log.read_text())["arguments"], {"title": "Which one?"})


class SnapshotTest(unittest.TestCase):
    def test_rewrite_maps_each_path_once_also_json_escaped(self):
        mapping = {"/a/repo": "/snap/repo", "/tmp/s": "/snap/_ext/tmp/s"}
        text = 'cd /a/repo/x; ls /tmp/s/f; {"p": "/a/repo"}'
        self.assertEqual(twin.rewrite(text, mapping),
                         'cd /snap/repo/x; ls /snap/_ext/tmp/s/f; {"p": "/snap/repo"}')
        self.assertEqual(twin.rewrite("/tmp/s", {"/tmp/s": "/tmp/s/copy"}), "/tmp/s/copy")

    def test_rewrite_matches_tilde_and_tmp_forms_and_whole_path_parts_only(self):
        copies = {"/private/tmp/s": "/snap/_ext/s", "/Users/me/.claude/t": "/snap/_ext/t", "/Users/me/p": "/snap/repo"}
        mapping = {form: copy for real, copy in copies.items() for form in twin.aliases(real, "/Users/me")}
        text = "ls /tmp/s/f ~/.claude/t/a.md /Users/me/p/x /Users/me/p-site/y /Users/me/p."
        self.assertEqual(twin.rewrite(text, mapping),
                         "ls /snap/_ext/s/f /snap/_ext/t/a.md /snap/repo/x /Users/me/p-site/y /snap/repo.")
        self.assertEqual(twin.rewrite('{"c": "ls\\n/Users/me/p/a"}', mapping), '{"c": "ls\\n/snap/repo/a"}')

    def test_outside_paths_keep_named_folders_and_skip_repo_home_and_transcripts(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:  # not /var/folders, which is never copied
            tmp = os.path.realpath(tmp)
            home, repo = Path(tmp) / "home", Path(tmp) / "home" / "work" / "repo"
            pad = Path(tmp) / "home" / "pads" / "s1" / "scratchpad"
            transcripts = Path(tmp) / "home" / ".claude" / "projects"
            for d in (repo, pad / "deck", transcripts):
                d.mkdir(parents=True)
            (pad / "deck" / "a.html").write_text("x")
            texts = ["see `%s/deck/a.html` and %s/src" % (pad, repo), '{"path": "%s"}' % pad,
                     "%s/old.jsonl %s" % (transcripts, home / "work")]
            found = twin.outside_paths(texts, str(repo), str(home), [str(transcripts)])
            self.assertEqual(found, [str(pad)])

    def test_copy_outside_takes_only_files_from_before_the_cut(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "pad"
            src.mkdir()
            (src / "old.md").write_text("old")
            (src / "new.md").write_text("new")
            cut = time.time() - 60
            os.utime(src / "old.md", (cut - 60, cut - 60))
            mapping = twin.copy_outside([str(src)], Path(tmp) / "ext", cut)
            copy = Path(mapping[str(src)])
            self.assertTrue((copy / "old.md").is_file())
            self.assertFalse((copy / "new.md").exists())

    def test_outside_paths_follow_first_appearance_and_tool_inputs_take_every_call(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            tmp = os.path.realpath(tmp)
            a, b = Path(tmp) / "x" / "y" / "a", Path(tmp) / "x" / "y" / "b"
            for d in (a, b):
                d.mkdir(parents=True)
            self.assertEqual(twin.outside_paths(["%s" % b, "%s %s/f" % (a, b)], "/nope", "/home/me", []),
                             [str(b), str(a)])
        call = lambda i: (b"", {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/p/%d" % i}}]}})
        rows = [call(i) for i in range(120)]
        inputs = twin.tool_inputs(rows, 100)
        self.assertEqual(len(inputs), 100)
        self.assertIn("/p/0", inputs[-1])
        self.assertIn("/p/99", inputs[0])

    def test_snapshot_keeps_uncommitted_work_and_history_up_to_the_cut(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, dest = Path(tmp) / "repo", Path(tmp) / "snap"
            def git(*args, at=None):
                env = dict(os.environ, GIT_COMMITTER_DATE="@%d" % (at or time.time()))
                subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"] + list(args),
                               check=True, capture_output=True, env=env)
            repo.mkdir()
            git("init", "-q")
            (repo / "a.txt").write_text("committed")
            (repo / "b.txt").write_text("committed")
            git("add", ".")
            git("commit", "-qm", "one", at=time.time() - 600)
            cut = time.time() - 200
            (repo / "b.txt").write_text("edited after the cut")
            git("commit", "-qam", "two")
            (repo / "a.txt").write_text("edited before the cut")  # uncommitted at the cut
            os.utime(repo / "a.txt", (time.time() - 300, time.time() - 300))
            twin.snapshot(str(repo), cut, dest)
            self.assertEqual((dest / "a.txt").read_text(), "edited before the cut")
            self.assertEqual((dest / "b.txt").read_text(), "committed")
            log = subprocess.run(["git", "-C", str(dest), "log", "--all", "--format=%s"], capture_output=True,
                                 text=True).stdout.split()
            self.assertEqual(log, ["one"])
            self.assertFalse((dest / ".git" / "FETCH_HEAD").exists())  # it names the live repo
            status = subprocess.run(["git", "-C", str(dest), "status", "--porcelain"], capture_output=True,
                                    text=True).stdout
            self.assertIn("a.txt", status)

    def test_copied_worktree_has_no_git_pointer_to_the_live_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            wt = Path(tmp) / "wt"
            wt.mkdir()
            (wt / ".git").write_text("gitdir: /live/repo/.git/worktrees/wt")
            (wt / "f.py").write_text("x")
            for path in (wt / ".git", wt / "f.py"):
                os.utime(path, (time.time() - 120, time.time() - 120))
            copy = Path(twin.copy_outside([str(wt)], Path(tmp) / "ext", time.time() - 60)[str(wt)])
            self.assertTrue((copy / "f.py").is_file())
            self.assertFalse((copy / ".git").exists())

    def test_retry_once_runs_an_arm_again_only_when_it_has_no_text(self):
        calls = []
        def attempt(retry):
            calls.append(retry)
            return {"reply": "ok"} if retry else {"no_text": True, "stopped": "claude -p failed (1)"}
        self.assertEqual(twin.retry_once(attempt), {"reply": "ok", "retried": "claude -p failed (1)"})
        self.assertEqual(calls, [False, True])
        self.assertEqual(twin.retry_once(lambda retry: {"reply": "first"}), {"reply": "first"})
        self.assertTrue(twin.failed_run(RuntimeError("claude -p failed (1): Error: No deferred tool")))
        self.assertFalse(twin.failed_run(RuntimeError("claude -p error (error_max_turns): ")))
        self.assertFalse(twin.failed_run(RuntimeError("claude -p timeout after 1200s")))

    def test_summary_shows_p_does_not_lose(self):
        arm = {"tools": []}
        results = [{"cycle": c, "kind": "code", "message": "m", "grade": {"winner": w, "N": {}, "P": {}},
                    "arms": {"N": arm, "P": dict(arm, retried="e") if c == "c3" else arm},
                    "cost": {"N": 0, "P": 0, "grade": 0}} for c, w in (("c1", "P"), ("c2", "tie"), ("c3", "N"))]
        with tempfile.TemporaryDirectory() as tmp:
            for r in results:
                (Path(tmp) / ("%s.json" % r["cycle"])).write_text(json.dumps(r))
            with open(os.devnull, "w") as null, unittest.mock.patch("sys.stdout", null):
                twin.cmd_continue_summary(Path(tmp))
            text = (Path(tmp) / "summary.md").read_text()
        self.assertIn("P does not lose (wins + ties): 2 of 3", text)
        self.assertIn("failed `claude -p`: c3 P", text)

    def test_grader_counts_a_missing_detail_only_if_the_real_session_used_it(self):
        prompt = " ".join(twin.CONT_GRADE_PROMPT.format(limit=twin.TOOL_INPUT_CHARS, cut="c", before="b", after="a",
                                                        message="m", x="x", y="y").split())
        self.assertIn("only if the real session used it in its next steps", prompt)
        self.assertIn("neither states it nor shows it has it", prompt)
        self.assertIn("cut at %d characters" % twin.TOOL_INPUT_CHARS, prompt)

    def test_last_text_reads_the_last_assistant_text_after_the_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            rows = [{"type": "assistant", "message": {"content": [{"type": "text", "text": "before"}]}},
                    {"type": "system", "subtype": "compact_boundary"},
                    {"type": "assistant", "message": {"content": [{"type": "text", "text": "step one"}]}},
                    {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read"}]}}]
            path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
            self.assertEqual(twin.last_text(path), "step one")

    def test_arm_settings_hook_every_tool_and_allow_the_waggle_stub(self):
        settings = json.loads(twin.arm_settings())
        self.assertEqual(settings["hooks"]["PreToolUse"][0]["matcher"], "*")
        self.assertIn("twin_guard.py", settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"])
        self.assertIn("mcp__plugin_waggle_waggle__*", settings["permissions"]["allow"])
        self.assertTrue(settings["sandbox"]["enabled"])


if __name__ == "__main__":
    unittest.main()
