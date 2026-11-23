"""The twin harness in scripts/ (a research tool, not shipped): the parts that keep arms inside the snapshot."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
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

    def test_network_and_push_are_refused(self):
        for command in ("git push origin main", "gh pr create", "curl -s https://x.dev", "npm publish"):
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

    def test_outside_paths_keep_named_folders_and_skip_repo_home_and_transcripts(self):
        with tempfile.TemporaryDirectory() as tmp:
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
