from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from _support import ROOT
from omarchy_ptt.config import DEFAULT, fingerprint
from omarchy_ptt.installer import render_lua


@unittest.skipUnless(shutil.which('lua'), 'Lua interpreter not installed')
class LuaRoutesTests(unittest.TestCase):
    def test_actual_callbacks_hold_release_deduplicate_and_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ptt.lua'
            path.write_text(render_lua(DEFAULT))
            result = subprocess.run(['lua', str(ROOT / 'tests/test_routes.lua'), str(path), fingerprint(DEFAULT)],
                                    check=True, capture_output=True, text=True)
            self.assertIn('PASS:', result.stdout)
