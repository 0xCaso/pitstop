import tempfile
import unittest
from pathlib import Path

from pitstop.core.paths import pitstop_home


class PitstopHomeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.work = self.home / ".claude-work"

    def tearDown(self):
        self._tmp.cleanup()

    def test_pitstop_home_env_wins(self):
        (self.home / ".claude" / "pitstop").mkdir(parents=True)
        env = {"PITSTOP_HOME": "/custom/place", "CLAUDE_CONFIG_DIR": str(self.work)}
        self.assertEqual(pitstop_home(env, self.home), Path("/custom/place"))

    def test_config_dir_new_user(self):
        self.assertEqual(pitstop_home({"CLAUDE_CONFIG_DIR": str(self.work)}, self.home), self.work / "pitstop")

    def test_config_dir_keeps_existing_data(self):
        (self.home / ".claude" / "pitstop").mkdir(parents=True)
        self.assertEqual(pitstop_home({"CLAUDE_CONFIG_DIR": str(self.work)}, self.home),
                         self.home / ".claude" / "pitstop")

    def test_config_dir_own_folder_wins(self):
        (self.home / ".claude" / "pitstop").mkdir(parents=True)
        (self.work / "pitstop").mkdir(parents=True)
        self.assertEqual(pitstop_home({"CLAUDE_CONFIG_DIR": str(self.work)}, self.home), self.work / "pitstop")

    def test_no_config_dir(self):
        self.assertEqual(pitstop_home({}, self.home), self.home / ".claude" / "pitstop")
        self.assertEqual(pitstop_home({"CLAUDE_CONFIG_DIR": ""}, self.home), self.home / ".claude" / "pitstop")
