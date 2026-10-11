import contextlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from _support import ROOT
from omarchy_ptt import installer
from omarchy_ptt.config import DEFAULT, Paths, validate


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='omarchy-ptt-test-')
        root = Path(self.temp.name) / 'person with spaces'
        self.paths = Paths(root, root / 'config', root / 'data', root / 'state', root / 'cache')
        self.paths.main_config.parent.mkdir(parents=True)
        self.original = '-- personal config\no = {}\n'
        self.paths.main_config.write_text(self.original)
        self.commands = []
        self.units = {}
        self.fail_parser = False
        self.fail_enable = False
        self.scope = contextlib.ExitStack()
        self.scope.enter_context(patch.object(installer, 'preflight'))
        self.scope.enter_context(patch.object(installer.release_loader, 'build', return_value=root / 'cache/release.so'))
        self.scope.enter_context(patch.object(installer.release_loader, 'loaded', return_value=False))
        self.scope.enter_context(patch.object(installer.release_loader, 'activate'))
        self.scope.enter_context(patch.object(installer, 'reload_config'))
        self.scope.enter_context(patch.object(installer, 'wait_ready'))
        self.scope.enter_context(patch.object(installer, 'run', side_effect=self.fake_run))

    def tearDown(self):
        self.scope.close()
        self.temp.cleanup()

    def fake_run(self, *args, **kwargs):
        self.commands.append(args)
        if args[0] == 'Hyprland' and self.fail_parser:
            return subprocess.CompletedProcess(args, 1, 'bad config', '')
        if args[0] == 'systemctl':
            name = Path(args[-1]).name
            state = self.units.setdefault(name, {'enabled': False, 'active': False})
            if 'is-enabled' in args:
                return subprocess.CompletedProcess(args, 0, 'enabled' if state['enabled'] else 'disabled', '')
            if 'is-active' in args:
                return subprocess.CompletedProcess(args, 0, 'active' if state['active'] else 'inactive', '')
            if 'enable' in args:
                if self.fail_enable:
                    raise subprocess.CalledProcessError(1, args)
                state['enabled'] = True
            if 'disable' in args:
                state['enabled'] = False
                if '--now' in args:
                    state['active'] = False
            if 'start' in args:
                state['active'] = True
            if 'stop' in args:
                state['active'] = False
        return subprocess.CompletedProcess(args, 0, '', '')

    def snapshot(self):
        return {str(p.relative_to(self.paths.home)): p.read_bytes()
                for p in self.paths.home.rglob('*') if p.is_file()}

    def setup(self, **kwargs):
        return installer.setup(self.paths, DEFAULT.copy(), **kwargs)

    def test_fresh_install_repeat_and_remove_restore_originals(self):
        original = self.snapshot()
        self.setup(defer=True)
        first = self.paths.main_config.read_bytes()
        self.setup(defer=True)
        self.assertEqual(self.paths.main_config.read_bytes(), first)
        self.assertEqual(first.count(installer.BEGIN.encode()), 1)
        self.assertTrue(self.units[installer.UNIT]['enabled'])
        manifest = installer.read_manifest(self.paths)
        self.assertFalse(manifest['prior_service']['enabled'])
        installer.remove(self.paths, defer=True)
        self.assertEqual(self.snapshot(), original)
        self.assertFalse(self.units[installer.UNIT]['enabled'])

    def test_existing_launcher_and_mime_fields_restored(self):
        desktop = self.paths.data / 'applications/discord.desktop'
        desktop.parent.mkdir(parents=True)
        original = '[Desktop Entry]\nType=Application\nName=Discord\nExec=discord %u\nMimeType=x-scheme-handler/discord;\nHidden=true\n'
        desktop.write_text(original)
        self.setup(defer=True)
        installed = desktop.read_text()
        self.assertIn('MimeType=x-scheme-handler/discord;', installed)
        self.assertIn('Hidden=false', installed)
        subprocess.run(['desktop-file-validate', str(desktop)], check=True, capture_output=True)
        installer.remove(self.paths, defer=True)
        self.assertEqual(desktop.read_text(), original)

    def test_dry_run_does_not_compile_or_write(self):
        original = self.snapshot()
        report = self.setup(defer=True, dry_run=True)
        self.assertTrue(report['dry_run'])
        self.assertEqual(self.snapshot(), original)
        installer.release_loader.build.assert_not_called()
        self.assertEqual(self.commands, [])

    def test_config_validation_failure_rolls_back_every_file(self):
        original = self.snapshot()
        self.fail_parser = True
        with self.assertRaisesRegex(RuntimeError, 'rejeitada'):
            self.setup(defer=True)
        self.assertEqual(self.snapshot(), original)
        self.assertFalse(self.units[installer.UNIT]['enabled'])

    def test_live_service_failure_restores_configuration_and_old_service(self):
        original = self.snapshot()
        self.units[installer.UNIT] = {'enabled': False, 'active': False}
        with patch.object(installer, 'wait_ready', side_effect=RuntimeError('bridge not ready')):
            with self.assertRaisesRegex(RuntimeError, 'bridge not ready'):
                self.setup(defer=False)
        self.assertEqual(self.snapshot(), original)
        self.assertEqual(self.units[installer.UNIT], {'enabled': False, 'active': False})

    def test_personal_changes_after_install_survive_removal(self):
        self.setup(defer=True)
        with self.paths.main_config.open('a') as file:
            file.write('-- new personal setting\n')
        installer.remove(self.paths, defer=True)
        self.assertIn('-- new personal setting', self.paths.main_config.read_text())
        self.assertNotIn(installer.BEGIN, self.paths.main_config.read_text())

    def test_edited_owned_script_is_preserved(self):
        self.setup(defer=True)
        self.paths.launcher.write_text('#!/bin/sh\n# user modification\n')
        report = installer.remove(self.paths, defer=True)
        self.assertIn(str(self.paths.launcher), report['preserved'])
        self.assertIn('user modification', self.paths.launcher.read_text())
        self.assertTrue(self.paths.manifest.exists())

    def test_edited_include_prevents_destructive_update_and_remove(self):
        self.setup(defer=True)
        self.paths.main_config.write_text(self.paths.main_config.read_text().replace('dofile(', 'custom_loader('))
        before = self.snapshot()
        with self.assertRaisesRegex(RuntimeError, 'bloco omarchy-ptt'):
            self.setup(defer=True)
        with self.assertRaisesRegex(RuntimeError, 'bloco de inclusão'):
            installer.remove(self.paths, defer=True)
        self.assertEqual(self.snapshot(), before)

    def test_migration_is_explicit_and_reversible(self):
        self.paths.main_config.write_text(self.original + '-- BEGIN discord-ptt-focus\no.window("discord", {})\n-- END discord-ptt-focus\n')
        bindings = self.paths.config / 'hypr/bindings.lua'
        bindings.write_text('-- my bind\n-- BEGIN discord-ptt-mouse9\nold_ptt()\n-- END discord-ptt-mouse9\n')
        original = self.snapshot()
        self.units[installer.LEGACY_UNIT] = {'enabled': True, 'active': False}
        with self.assertRaisesRegex(RuntimeError, '--migrate'):
            self.setup(defer=True)
        self.setup(defer=True, migrate=True)
        self.assertNotIn('old_ptt()', bindings.read_text())
        self.assertFalse(self.units[installer.LEGACY_UNIT]['enabled'])
        installer.remove(self.paths, defer=True)
        self.assertEqual(self.snapshot(), original)
        self.assertTrue(self.units[installer.LEGACY_UNIT]['enabled'])

    def test_user_profile_survives_update(self):
        config = DEFAULT | {'linux_button': 275, 'x11_button': 8}
        installer.setup(self.paths, config, defer=True)
        self.assertIn('local linux_button = 275', (self.paths.package / 'ptt.lua').read_text())
        self.assertEqual(json.loads(self.paths.profile.read_text()), config)

    def test_update_keeps_ownership_of_previous_components_for_removal(self):
        self.setup(defer=True)
        previous_file = self.paths.package / 'obsolete_component.py'
        previous_file.write_bytes(b'# previous release\n')
        manifest = installer.read_manifest(self.paths)
        manifest['files'][str(previous_file)] = {'original': None, 'original_mode': None,
                                                'installed_hash': installer.digest(previous_file.read_bytes())}
        self.paths.manifest.write_text(json.dumps(manifest))
        self.setup(defer=True)
        installer.remove(self.paths, defer=True)
        self.assertFalse(previous_file.exists())

    def test_plugin_update_failure_reloads_previous_binary(self):
        self.setup(defer=True)
        old = installer.read_manifest(self.paths)['plugin_file']
        with patch.object(installer.release_loader, 'build', return_value=Path('/tmp/new-release.so')), \
             patch.object(installer.release_loader, 'loaded', return_value=True), \
             patch.object(installer, 'wait_ready', side_effect=RuntimeError('update failed')):
            with self.assertRaisesRegex(RuntimeError, 'update failed'):
                self.setup(defer=False)
        self.assertIn(('hyprctl', 'plugin', 'unload', old), self.commands)
        self.assertIn(('hyprctl', 'plugin', 'load', old), self.commands)
        self.assertEqual(installer.read_manifest(self.paths)['plugin_file'], old)

    def test_symlink_is_not_overwritten(self):
        target = self.paths.home / 'real.lua'
        target.write_text('personal data')
        self.paths.main_config.unlink()
        self.paths.main_config.symlink_to(target)
        with self.assertRaisesRegex(RuntimeError, 'link simbólico'):
            self.setup(defer=True)
        self.assertEqual(target.read_text(), 'personal data')


class ProfileTests(unittest.TestCase):
    def test_rejects_unsupported_clients_and_invalid_codes(self):
        for config in ({'linux_button': 272}, {'x11_button': 1}, {'schema': True},
                       {'window_class': '.*'}, {'executable': 'shell;command'}, {'home': '/tmp'}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                validate(config)

    def test_defaults_are_portable(self):
        self.assertEqual(validate({}), DEFAULT)
        self.assertNotIn('/home/', json.dumps(DEFAULT))


class PreflightTests(unittest.TestCase):
    def test_existing_non_ptt_button_bind_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = Paths(root, root / 'config', root / 'data', root / 'state', root / 'cache')
            paths.main_config.parent.mkdir(parents=True)
            paths.main_config.write_text('-- existing Omarchy config\n')
            with patch.object(installer.os, 'geteuid', return_value=1000), patch.object(installer, 'dependencies'), \
                 patch.object(installer, 'live', return_value=True), \
                 patch.object(installer, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')), \
                 patch.object(installer, 'hypr_json', return_value=[{'key': 'mouse:276', 'description': 'game action'}]):
                with self.assertRaisesRegex(RuntimeError, 'Botão já vinculado'):
                    installer.preflight(paths, DEFAULT)
