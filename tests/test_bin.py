import json
import os
import subprocess

from pitstop.core.config import update_config
from tests.helpers import REPO_ROOT, TempLayoutTestCase, assistant_line, write_jsonl


class BinHookTest(TempLayoutTestCase):
    def run_bin(self, stdin_bytes):
        env = dict(os.environ, PITSTOP_HOME=str(self.layout.base))
        return subprocess.run(["/usr/bin/python3", str(REPO_ROOT / "bin" / "pitstop"), "hook", "stop"],
                              input=stdin_bytes, capture_output=True, env=env, timeout=10)

    def test_hook_runs_with_system_python(self):
        update_config(self.layout, notify=False)
        transcript = write_jsonl(self.tmp / "s.jsonl", [assistant_line()])
        payload = {"hook_event_name": "Stop", "session_id": "s1", "transcript_path": str(transcript), "cwd": "/work/repo"}
        result = self.run_bin(json.dumps(payload).encode("utf-8"))
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        self.assertEqual(json.loads(result.stdout)["systemMessage"], "🔋 pitstop · 212K → pitting at the next clean point")

    def test_garbage_input_exits_zero_silently(self):
        result = self.run_bin(b"garbage")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))


class BinHeredocTest(TempLayoutTestCase):
    """The skill's one-call checkpoint: the quoted heredoc in SKILL.md hands the text over byte for byte."""

    def test_checkpoint_with_shell_characters_arrives_intact(self):
        import re
        skill = (REPO_ROOT / "skills" / "pitstop" / "SKILL.md").read_text(encoding="utf-8")
        line = next(l.strip() for l in skill.splitlines() if "pitstop mark-pending --stdin" in l and "<<" in l)
        command = re.sub(r" \[[^\]]*\]", "", line).replace("<code|other>", "code")
        command = command.replace("pitstop mark-pending", "/usr/bin/python3 '%s' mark-pending --session s1 "
                                  "--transcript '%s' --cwd '%s'" % (REPO_ROOT / "bin" / "pitstop",
                                                                    self.tmp / "s.jsonl", self.tmp), 1)
        write_jsonl(self.tmp / "s.jsonl", [assistant_line()])
        text = ("# pitstop checkpoint — `quotes` 'single' \"double\"\n\n## Goal\nKeep $HOME, ${PATH}, $(whoami) and "
                "`date` as written; a backslash \\ and \\n stay.\n\n## Re-read\n—")
        script = "%s\n%s\nPITSTOP_EOF\n" % (command, text)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE", "PITSTOP"))}
        env["PITSTOP_HOME"] = str(self.layout.base)
        result = subprocess.run(["/bin/bash", "-c", script], capture_output=True, env=env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (written,) = list(self.layout.checkpoints_dir.iterdir())
        self.assertEqual(written.read_text(encoding="utf-8"), text + "\n")
