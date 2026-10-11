import contextlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from _support import ROOT
from omarchy_ptt import cli, discord_settings as ds, selector
from omarchy_ptt.config import DEFAULT, Paths


def vi(n):
    result = bytearray()
    while n >= 128:
        result.append((n & 127) | 128)
        n >>= 7
    return bytes(result + bytes([n]))


def fld(value):
    return vi(len(value)) + value


def masked(data):
    crc = ds.crc32c(data)
    return (((crc >> 15) | (crc << 17)) + 0xa282ead8) & 0xffffffff


def record(data, kind=1):
    return struct.pack('<IHB', masked(bytes([kind]) + data), len(data), kind) + data


def payload(button=9):
    return b'\x01' + json.dumps({'_state': {'5': {'action': 'PUSH_TO_TALK', 'enabled': True,
        'shortcut': [[1, button, '0:0']]}}}).encode()


def batch(sequence, value, key=ds.KEY):
    return struct.pack('<QI', sequence, 1) + bytes([0 if value is None else 1]) + fld(key) + (fld(value) if value is not None else b'')


def entries(items):
    return b''.join(vi(0) + vi(len(k)) + vi(len(v)) + k + v for k, v in items) + struct.pack('<II', 0, 1)


def table(items):
    data = entries([(k + struct.pack('<Q', (s << 8) | kind), v) for s, kind, k, v in items])
    block = data + b'\0' + struct.pack('<I', masked(data + b'\0'))
    index = entries([(b'z', vi(0) + vi(len(data)))])
    iblock = index + b'\0' + struct.pack('<I', masked(index + b'\0'))
    footer = vi(0) + vi(0) + vi(len(block)) + vi(len(index))
    return block + iblock + footer.ljust(40, b'\0') + struct.pack('<Q', 0xdb4775248b80fb57)


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.paths = Paths(root, root/'config', root/'data', root/'state', root/'cache')
        self.db = self.paths.config / 'discord/Local Storage/leveldb'
        self.db.mkdir(parents=True)
        (self.db/'CURRENT').write_text('MANIFEST-000001\n')
        (self.db/'MANIFEST-000001').write_bytes(record(vi(2) + vi(2)))

    def tearDown(self):
        self.temp.cleanup()

    def args(self, *args):
        return cli.parser().parse_args(list(args))

    def test_import_exact_key_and_does_not_write(self):
        (self.db/'000002.log').write_bytes(record(batch(4, payload(8))) + record(batch(5, b'private', b'token')))
        before = {p: p.read_bytes() for p in self.db.iterdir()}
        self.assertEqual(ds.detect(self.paths)['linux_button'], 275)
        self.assertEqual(before, {p: p.read_bytes() for p in self.db.iterdir()})

    def test_latest_sequence_and_deletion_win(self):
        (self.db/'000002.log').write_bytes(record(batch(10, payload(8))) + record(batch(11, payload(9))))
        self.assertEqual(ds.detect(self.paths)['x11_button'], 9)
        with (self.db/'000002.log').open('ab') as f:
            f.write(record(batch(12, None)))
        with self.assertRaises(ValueError):
            ds.detect(self.paths)

    def test_manifest_excludes_obsolete_tables(self):
        edit = vi(2) + vi(2) + vi(7) + vi(0) + vi(3) + vi(100) + fld(b'a') + fld(b'z')
        (self.db/'MANIFEST-000001').write_bytes(record(edit))
        (self.db/'000003.ldb').write_bytes(table([(10, 1, ds.KEY, payload(8))]))
        (self.db/'000004.ldb').write_bytes(table([(999, 1, ds.KEY, payload(9))]))
        self.assertEqual(ds.detect(self.paths)['x11_button'], 8)
        (self.db/'000002.log').write_bytes(record(batch(11, payload(9))))
        self.assertEqual(ds.detect(self.paths)['x11_button'], 9)

    def test_fragmented_log(self):
        data = batch(4, payload())
        self.assertEqual(list(ds.records(record(data[:20], 2) + record(data[20:60], 3) + record(data[60:], 4))), [data])

    def test_corrupt_storage_fails_closed(self):
        for value in [b'bad', record(batch(4, payload()))[:-1], record(batch(4, payload()))[:-1] + b'x']:
            (self.db/'000002.log').write_bytes(value)
            with self.subTest(value=value[:5]), self.assertRaises(ValueError):
                ds.detect(self.paths)
        (self.db/'000002.log').write_bytes(record(batch(4, payload(8))) + record(batch(5, payload(9)))[:-1])
        with self.assertRaises(ValueError):
            ds.detect(self.paths)  # Never import an old button when the newer write is partial.

    def test_snappy_compressed_block(self):
        import ctypes
        import ctypes.util
        name = ctypes.util.find_library('snappy')
        if not name:
            self.skipTest('Snappy library unavailable')
        lib = ctypes.CDLL(name)
        lib.snappy_max_compressed_length.argtypes = [ctypes.c_size_t]
        lib.snappy_max_compressed_length.restype = ctypes.c_size_t
        lib.snappy_compress.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
        raw = entries([(ds.KEY, payload())])
        length = ctypes.c_size_t(lib.snappy_max_compressed_length(len(raw)))
        out = ctypes.create_string_buffer(length.value)
        self.assertEqual(lib.snappy_compress(raw, len(raw), out, ctypes.byref(length)), 0)
        compressed = out.raw[:length.value]
        block = compressed + b'\x01' + struct.pack('<I', masked(compressed + b'\x01'))
        self.assertEqual(ds.unpack_block(block, vi(0) + vi(len(compressed))), raw)

    def test_unsupported_or_ambiguous_shortcuts(self):
        value = json.loads(payload()[1:])
        cases = []
        for shortcut in [[[0, 64, 3]], [[1, 9, '0:0'], [0, 64, 3]], [[1, 50, '0:0']]]:
            item = json.loads(payload()[1:]); item['_state']['5']['shortcut'] = shortcut; cases.append(item)
        item = json.loads(payload()[1:]); item['_state']['6'] = item['_state']['5']; cases.append(item)
        item = json.loads(payload()[1:]); item['_state']['5']['enabled'] = False; cases.append(item)
        for item in cases:
            with self.subTest(item=item), self.assertRaises(ValueError):
                ds.profile_from_value(b'\x01' + json.dumps(item).encode())
        self.assertEqual(ds.profile_from_value(b'\x00' + json.dumps(value).encode('utf-16-le')), DEFAULT)

    def test_profile_priority_and_explicit_import(self):
        (self.db/'000002.log').write_bytes(record(batch(4, payload(8))))
        config, origin = cli.choose_profile(self.args('setup'), self.paths)
        self.assertEqual((config['x11_button'], origin), (8, 'discord'))
        self.paths.profile.parent.mkdir(parents=True)
        self.paths.profile.write_text(json.dumps(DEFAULT))
        self.assertEqual(cli.choose_profile(self.args('setup'), self.paths), (DEFAULT, 'existing'))
        self.assertEqual(cli.choose_profile(self.args('configure', '--from-discord'), self.paths)[0]['x11_button'], 8)

    def test_no_silent_default_or_partial_codes(self):
        for args in [('setup', '--dry-run'), ('setup', '--linux-button', '275'), ('setup', '--capture', '--from-discord')]:
            with self.subTest(args=args), patch.dict(os.environ, {'DISPLAY': ''}), self.assertRaises(ValueError):
                cli.choose_profile(self.args(*args), self.paths)
        self.assertEqual(cli.choose_profile(self.args('setup', '--no-detect'), self.paths), (DEFAULT, 'default'))

    def test_capture_and_cancel_do_not_install(self):
        with patch.object(cli.Paths, 'discover', return_value=self.paths), patch.object(cli.installer, 'setup', return_value={'installed': True}) as setup:
            with patch.dict(os.environ, {'DISPLAY': ':999'}), patch.object(selector, 'capture', return_value=selector.button_profile(8)):
                cli.main(['setup', '--capture'])
                self.assertEqual(setup.call_args.args[1]['x11_button'], 8)
            setup.reset_mock()
            with patch.dict(os.environ, {'DISPLAY': ':999'}), patch.object(selector, 'capture', side_effect=selector.SelectionCancelled('cancelled')):
                with self.assertRaises(SystemExit):
                    cli.main(['setup', '--capture'])
                setup.assert_not_called()

    def test_supported_button_mapping(self):
        for b in range(8, 13):
            self.assertEqual(selector.button_profile(b)['linux_button'], 275 + b - 8)
        for b in [1, 2, 3, 4, 7, 13, True]:
            with self.assertRaises(ValueError):
                selector.button_profile(b)


@unittest.skipUnless(os.getenv('OMARCHY_PTT_GUI_TESTS') == '1', 'Enable isolated Xvfb test explicitly')
class SelectorIntegrationTests(unittest.TestCase):
    def test_real_window_hold_release_confirm_and_cancel(self):
        from Xlib import X, XK, display
        from Xlib.ext import xtest
        # Xvfb creates an isolated display: events never reach the user's desktop.
        # Avoid -displayfd: some server builds may unlink an existing XWayland
        # path while probing display 0. Use an explicit unused high display.
        number = 18000 + os.getpid() % 10000
        while any(Path(p).exists() or Path(p).is_symlink() for p in
                  (f'/tmp/.X11-unix/X{number}', f'/tmp/.X11-unix/X{number}_', f'/tmp/.X{number}-lock')):
            number += 1
        name = ':' + str(number)
        server = subprocess.Popen(['Xvfb', name, '-screen', '0', '800x400x24', '-nolisten', 'tcp'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            limit = time.monotonic() + 5
            while not Path(f'/tmp/.X11-unix/X{number}').exists():
                if time.monotonic() >= limit or server.poll() is not None:
                    raise RuntimeError('Xvfb não iniciou no display de teste.')
                time.sleep(.02)
            connection = display.Display(name)
            env = os.environ | {'DISPLAY': name, 'PYTHONPATH': str(ROOT/'src')}
            for cancel in (False, True):
                process = subprocess.Popen(['/usr/bin/python3', '-c',
                    'from omarchy_ptt.selector import capture; print(capture())'], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    limit = time.monotonic() + 5
                    window = None
                    while time.monotonic() < limit:
                        for w in connection.screen().root.query_tree().children:
                            if w.get_wm_class() == ('omarchy-ptt-configure', 'OmarchyPTTConfigure'):
                                window = w; break
                        if window: break
                        time.sleep(.02)
                    self.assertIsNotNone(window, process.stderr.read() if process.poll() is not None else 'window not mapped')
                    window.set_input_focus(X.RevertToParent, X.CurrentTime)
                    window.warp_pointer(50, 70)
                    connection.sync()
                    if not cancel:
                        if os.getenv('OMARCHY_PTT_SCREENSHOT'):
                            from PIL import Image
                            time.sleep(.05)
                            connection.sync()
                            shot = window.get_image(0, 0, 600, 220, X.ZPixmap, 0xffffffff)
                            Image.frombytes('RGB', (600, 220), shot.data, 'raw', 'BGRX').save(os.environ['OMARCHY_PTT_SCREENSHOT'])
                        xtest.fake_input(connection, X.ButtonPress, 8)
                        connection.sync(); time.sleep(.05)
                        self.assertIsNone(process.poll(), 'Must wait for release and confirmation')
                        xtest.fake_input(connection, X.ButtonRelease, 8)
                    key = connection.keysym_to_keycode(XK.XK_Escape if cancel else XK.XK_Return)
                    xtest.fake_input(connection, X.KeyPress, key)
                    xtest.fake_input(connection, X.KeyRelease, key)
                    connection.sync()
                    out, err = process.communicate(timeout=5)
                    self.assertEqual(process.returncode, 1 if cancel else 0, err)
                    self.assertIn('cancelada' if cancel else "'x11_button': 8", err if cancel else out)
                finally:
                    if process.poll() is None: process.kill(); process.wait()
                    process.stdout.close(); process.stderr.close()
            connection.close()
        finally:
            server.terminate(); server.wait(timeout=5)
