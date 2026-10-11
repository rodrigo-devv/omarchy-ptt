"""Opt-in integration with installed Hyprland headers/parser, never live input."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from _support import ROOT
from omarchy_ptt import installer
from omarchy_ptt.config import DEFAULT, Paths


@unittest.skipUnless(os.getenv('OMARCHY_PTT_NATIVE_TESTS') == '1', 'Enable native integration explicitly')
class NativeTests(unittest.TestCase):
    def test_real_offline_install_parser_user_unit_and_uninstall(self):
        with tempfile.TemporaryDirectory(prefix='omarchy-ptt-native-') as directory:
            root = Path(directory) / 'user with spaces'
            paths = Paths(root, root / 'config', root / 'data', root / 'state', root / 'cache')
            paths.main_config.parent.mkdir(parents=True)
            original = 'dofile("/usr/share/omarchy/default/hypr/helpers.lua")\n'
            paths.main_config.write_text(original)
            env = {'XDG_CONFIG_HOME': str(paths.config), 'XDG_DATA_HOME': str(paths.data),
                   'XDG_STATE_HOME': str(paths.state), 'XDG_CACHE_HOME': str(paths.cache)}
            with patch.dict(os.environ, env), patch.object(installer, 'live', return_value=False), \
                 patch.object(installer.release_loader, 'live', return_value=False):
                report = installer.setup(paths, DEFAULT.copy(), defer=True)
                self.assertTrue(report['installed'])
                manifest = installer.read_manifest(paths)
                self.assertTrue(Path(manifest['plugin_file']).is_file())
                link = paths.config / 'systemd/user/graphical-session.target.wants/omarchy-ptt.service'
                self.assertTrue(link.is_symlink())
                for command in ('--version', '--help'):
                    result = subprocess.run([str(paths.launcher), command], check=True, capture_output=True, text=True)
                    self.assertTrue(result.stdout)
                result = subprocess.run([str(paths.launcher), 'doctor', '--json'], check=True, capture_output=True, text=True)
                self.assertIn('"installed": true', result.stdout)
                installer.remove(paths, defer=True)
                self.assertEqual(paths.main_config.read_text(), original)
                self.assertFalse(link.exists())
                self.assertFalse(paths.unit.exists())
                self.assertFalse(paths.launcher.exists())

    def test_production_cpp_signal_abi_filter_and_unload(self):
        with tempfile.TemporaryDirectory(prefix='omarchy-ptt-cpp-') as directory:
            binary = Path(directory) / 'test-release'
            flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', 'hyprland'], text=True))
            libs = shlex.split(subprocess.check_output(['pkg-config', '--libs', 'hyprutils'], text=True))
            subprocess.run(['c++', '-std=c++23', '-O1', *flags, str(ROOT / 'tests/test_release.cpp'),
                            str(ROOT / 'src/omarchy_ptt/resources/release.cpp'), *libs, '-o', str(binary)],
                           check=True, capture_output=True, text=True, timeout=120)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
            self.assertIn('PASS:', result.stdout)
