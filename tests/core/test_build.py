import json
import re
import unittest

from pitstop.core import build
from tests.helpers import REPO_ROOT


class BuildTest(unittest.TestCase):
    def test_plugin_version_is_the_manifest_version(self):
        manifest = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(build.plugin_version(), manifest["version"])

    def test_skill_hash_is_eight_hex_characters(self):
        self.assertRegex(build.skill_hash(), r"^[0-9a-f]{8}$")

    def test_cycle_ids_are_short_and_unique(self):
        first, second = build.new_cycle_id(), build.new_cycle_id()
        self.assertTrue(re.match(r"^[0-9a-f]{12}$", first))
        self.assertNotEqual(first, second)
