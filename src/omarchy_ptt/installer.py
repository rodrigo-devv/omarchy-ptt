"""Idempotent, user-scoped install with recorded originals and rollback."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import time

from . import __version__
from .config import DEFAULT, fingerprint, lua_string, validate
from . import release_loader
from .system import hypr_json, live, reload_config, run

UNIT = 'omarchy-ptt.service'
BEGIN, END = '-- BEGIN omarchy-ptt', '-- END omarchy-ptt'
LEGACY_UNIT = 'discord-ptt-bridge.service'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def block(text, name):
    start, end = f'-- BEGIN {name}', f'-- END {name}'
    if start not in text and end not in text:
        return None
    if text.count(start) != 1 or text.count(end) != 1:
        raise RuntimeError(f'Bloco {name} inválido; nenhum arquivo foi alterado.')
    first, last = text.index(start), text.index(end) + len(end)
    if first > last - len(end):
        raise RuntimeError(f'Bloco {name} inválido.')
    return text[first:last]


def without(text, name):
    found = block(text, name)
    return text.replace(found + '\n', '', 1).replace(found, '', 1) if found else text


def render_lua(config):
    template = (Path(__file__).parent / 'resources/ptt.lua.in').read_text()
    return template.replace('@LINUX_BUTTON@', str(config['linux_button'])).replace(
        '@FINGERPRINT@', lua_string(fingerprint(config)))


def systemd_string(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def unit_text(paths):
    entry = systemd_string(str(paths.package / 'run.py'))
    environment = '\n'.join('Environment=' + systemd_string(key + '=' + str(path)) for key, path in (
        ('XDG_CONFIG_HOME', paths.config), ('XDG_DATA_HOME', paths.data),
        ('XDG_STATE_HOME', paths.state), ('XDG_CACHE_HOME', paths.cache)))
    return f'''[Unit]
Description=Discord PTT compatibility for Omarchy
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
{environment}
ExecStartPre=/usr/bin/python3 {entry} release-load
ExecStart=/usr/bin/python3 {entry} bridge
Restart=on-failure
RestartSec=1
TimeoutStartSec=180
TimeoutStopSec=3

[Install]
WantedBy=graphical-session.target
'''


def desktop_entry(text, replacements):
    lines, result, in_main, seen = text.splitlines(), [], False, set()
    for line in lines:
        if line.startswith('['):
            if in_main:
                result.extend(f'{key}={value}' for key, value in replacements.items() if key not in seen)
            in_main = line == '[Desktop Entry]'
        key = line.split('=', 1)[0]
        if in_main and key in replacements:
            if key not in seen:
                result.append(f'{key}={replacements[key]}')
                seen.add(key)
        else:
            result.append(line)
    if in_main:
        result.extend(f'{key}={value}' for key, value in replacements.items() if key not in seen)
    if '[Desktop Entry]' not in lines:
        raise ValueError('Launcher Discord inválido.')
    return '\n'.join(result) + '\n'


def plan(paths, config, migrate=False):
    writes = {}
    source = Path(__file__).parent
    for file in source.rglob('*'):
        if file.is_file() and '__pycache__' not in file.parts and file.suffix in ('.py', '.cpp', '.in'):
            writes[paths.package / 'omarchy_ptt' / file.relative_to(source)] = (file.read_bytes(), 0o644)
    writes[paths.package / 'run.py'] = ((source.parent / 'run.py').read_bytes(), 0o644)
    writes[paths.package / 'ptt.lua'] = (render_lua(config).encode(), 0o644)
    command = '#!/bin/sh\nexec /usr/bin/python3 ' + shlex.quote(str(paths.package / 'run.py')) + ' "$@"\n'
    writes[paths.launcher] = (command.encode(), 0o755)
    wrapper = paths.home / '.local/bin/discord-ptt-x11'
    writes[wrapper] = (b'''#!/bin/sh
export ELECTRON_OZONE_PLATFORM_HINT=x11 OZONE_PLATFORM=x11 GDK_BACKEND=x11
unset GTK_IM_MODULE QT_IM_MODULE GLFW_IM_MODULE XMODIFIERS
exec discord --ozone-platform=x11 "$@"
''', 0o755)
    writes[paths.profile] = ((json.dumps(config, indent=2) + '\n').encode(), 0o600)
    writes[paths.unit] = (unit_text(paths).encode(), 0o644)
    main = paths.main_config.read_text()
    inclusion = BEGIN + '\ndofile(' + lua_string(str(paths.package / 'ptt.lua')) + ')\n' + END
    existing = block(main, 'omarchy-ptt')
    if existing and existing != inclusion:
        raise RuntimeError('O bloco omarchy-ptt foi editado; preserve suas alterações antes de atualizar.')
    bindings = paths.config / 'hypr/bindings.lua'
    old_bindings = bindings.read_text() if bindings.exists() else ''
    legacy = block(main, 'discord-ptt-focus') or block(old_bindings, 'discord-ptt-mouse9')
    if legacy and not migrate:
        raise RuntimeError('Integração local anterior detectada. Use --migrate para substituí-la com backup.')
    if legacy:
        main = without(main, 'discord-ptt-focus')
        writes[bindings] = (without(old_bindings, 'discord-ptt-mouse9').encode(), 0o644)
    main = without(main, 'omarchy-ptt')
    writes[paths.main_config] = ((main.rstrip('\n') + '\n\n' + inclusion + '\n').encode(), 0o644)
    desktop = paths.data / 'applications/discord.desktop'
    vendor = Path('/usr/share/applications/discord.desktop')
    text = desktop.read_text() if desktop.exists() else vendor.read_text() if vendor.exists() else (
        '[Desktop Entry]\nType=Application\nName=Discord\nIcon=discord\nTerminal=false\n'
        'Categories=Network;InstantMessaging;\nMimeType=x-scheme-handler/discord;\n')
    escaped = str(wrapper).replace('\\', '\\\\\\\\').replace('"', '\\\\"').replace('`', '\\\\`').replace('$', '\\\\$').replace('%', '%%')
    writes[desktop] = (desktop_entry(text, {'Exec': f'"{escaped}" --url -- %u',
        'TryExec': str(wrapper), 'Hidden': 'false', 'NoDisplay': 'false'}).encode(), 0o644)
    cli_escaped = str(paths.launcher).replace('\\', '\\\\\\\\').replace('"', '\\\\"').replace('`', '\\\\`').replace('$', '\\\\$').replace('%', '%%')
    writes[paths.data / 'applications/omarchy-ptt-configure.desktop'] = (
        '[Desktop Entry]\nType=Application\nName=Configuração PTT Discord\n'
        'Name[en]=Discord PTT Configuration\nIcon=discord\nTerminal=true\n'
        f'Exec="{cli_escaped}" configure\nCategories=Settings;\n'
    ).encode(), 0o644
    duplicate = paths.data / 'applications/Discord.desktop'
    if duplicate.exists():
        writes[duplicate] = (desktop_entry(duplicate.read_text(), {'Hidden': 'true', 'NoDisplay': 'true'}).encode(), 0o644)
    return writes, bool(legacy)


class Transaction:
    def __init__(self):
        self.before = {}

    def write(self, path, data, mode=0o644):
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise RuntimeError(f'Arquivo é link ou não é regular: {path}')
        if path not in self.before:
            self.before[path] = (path.read_bytes(), path.stat().st_mode & 0o777) if path.exists() else (None, None)
        if data is None:
            path.unlink(missing_ok=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = path.with_name(path.name + f'.ptt-{os.getpid()}.tmp')
        try:
            pending.write_bytes(data)
            pending.chmod(mode)
            os.replace(pending, path)
        finally:
            pending.unlink(missing_ok=True)

    def rollback(self):
        for path, (data, mode) in reversed(list(self.before.items())):
            self.write(path, data, mode or 0o644)


def dependencies(install=False):
    packages = set()
    commands = {'Hyprland': 'hyprland', 'hyprctl': 'hyprland', 'c++': 'gcc',
                'pkg-config': 'pkgconf', 'desktop-file-validate': 'desktop-file-utils',
                'systemctl': 'systemd'}
    for command, package in commands.items():
        if not shutil.which(command):
            packages.add(package)
    if run('/usr/bin/python3', '-c', 'import Xlib', check=False).returncode:
        packages.add('python-xlib')
    if not shutil.which('discord'):
        packages.add('discord')
    # Header compilation also needs transitive development files supplied by Arch packages.
    if shutil.which('pkg-config') and run('pkg-config', '--exists', 'hyprland', check=False).returncode:
        packages.add('hyprland')
    if packages and install:
        if not shutil.which('pacman'):
            raise RuntimeError('--install-deps suporta Arch/Omarchy com pacman.')
        import subprocess
        result = subprocess.run(['sudo', 'pacman', '-S', '--needed', '--noconfirm', *sorted(packages)])
        if result.returncode:
            raise RuntimeError('Falha ao instalar dependências; consulte a saída do pacman.')
        return dependencies(False)
    if packages:
        raise RuntimeError('Dependências ausentes: ' + ', '.join(sorted(packages)) + '. Use --install-deps.')


def preflight(paths, config, *, defer=False, install_deps=False):
    validate(config)
    if os.geteuid() == 0:
        raise RuntimeError('Execute como usuário normal; --install-deps usa sudo apenas para os pacotes.')
    if not paths.main_config.exists():
        raise RuntimeError('Omarchy com configuração Lua não encontrado. Esta versão não migra configurações .conf antigas.')
    if defer and live():
        raise RuntimeError('--defer é para fora da sessão gráfica. Dentro do Hyprland, execute setup sem --defer.')
    dependencies(install_deps)
    if not defer:
        if not live():
            raise RuntimeError('Fora da sessão Hyprland: use --defer para preparar o próximo login.')
        errors = run('hyprctl', 'configerrors').stdout.strip()
        if errors:
            raise RuntimeError('Corrija os erros existentes do Hyprland antes de instalar: ' + errors)
        button = f"mouse:{config['linux_button']}"
        collisions = [b for b in hypr_json(['binds']) if b.get('key') == button and
                      'Omarchy PTT' not in b.get('description', '') and
                      not (b.get('description', '').startswith('Discord push-to-talk') and
                           (paths.config / 'hypr/bindings.lua').exists() and
                           block((paths.config / 'hypr/bindings.lua').read_text(), 'discord-ptt-mouse9'))]
        if collisions:
            raise RuntimeError('Botão já vinculado: ' + json.dumps(collisions, ensure_ascii=False))


def read_manifest(paths):
    if not paths.manifest.exists():
        return {'schema': 1, 'files': {}}
    value = json.loads(paths.manifest.read_text())
    if value.get('schema') != 1:
        raise ValueError('Registro de instalação não suportado.')
    return value


def service_state(unit, offline=False):
    return {'enabled': run('systemctl', '--user', 'is-enabled', unit, check=False, offline=True).stdout.strip() == 'enabled',
            'active': False if offline else run('systemctl', '--user', 'is-active', unit, check=False).stdout.strip() == 'active'}


def restore_service(unit, state, offline=False):
    run('systemctl', '--user', '--no-reload', 'enable' if state['enabled'] else 'disable', unit, check=False, offline=True)
    if not offline:
        run('systemctl', '--user', 'start' if state['active'] else 'stop', unit, check=False)


def wait_ready(config):
    ready = Path(os.environ['XDG_RUNTIME_DIR']) / 'omarchy-ptt.ready'
    limit = time.monotonic() + 5
    while time.monotonic() < limit:
        try:
            lines = ready.read_text().splitlines()
            if (len(lines) >= 6 and lines[0] == os.environ['HYPRLAND_INSTANCE_SIGNATURE'] and
                0 <= time.time() - int(lines[1]) <= 2 and lines[4] == fingerprint(config)):
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    raise RuntimeError('Ponte não ficou pronta. Consulte journalctl --user -u omarchy-ptt.service.')


def setup(paths, config, *, defer=False, install_deps=False, dry_run=False, migrate=False):
    preflight(paths, config, defer=defer, install_deps=install_deps and not dry_run)
    writes, legacy = plan(paths, config, migrate)
    previous = read_manifest(paths)
    for path in writes:
        if path.is_symlink():
            raise RuntimeError(f'Não será substituído um link simbólico: {path}')
        entry = previous['files'].get(str(path))
        if entry and path.exists() and digest(path.read_bytes()) != entry['installed_hash']:
            if path not in (paths.main_config, paths.data / 'applications/discord.desktop',
                            paths.data / 'applications/Discord.desktop', paths.config / 'hypr/bindings.lua'):
                raise RuntimeError(f'Arquivo instalado foi editado; preserve suas mudanças antes de atualizar: {path}')
    if dry_run:
        return {'dry_run': True, 'files': [str(p) for p in writes], 'deferred': defer}
    target = release_loader.build(paths)  # Fails before writing any desktop configuration.
    transaction = Transaction()
    services = {UNIT: service_state(UNIT, offline=defer)}
    if legacy:
        services[LEGACY_UNIT] = service_state(LEGACY_UNIT, offline=defer)
    manifest = {'schema': 1, 'version': __version__, 'files': previous['files'].copy(), 'deferred': defer,
                'profile': config, 'plugin_file': str(target), 'installed_at': int(time.time()),
                'prior_service': previous.get('prior_service', services[UNIT]),
                'legacy_service': previous.get('legacy_service', services.get(LEGACY_UNIT))}
    plugin_was_loaded = release_loader.loaded() if not defer else False
    old_plugin = previous.get('plugin_file')
    plugin_replaced = False
    try:
        if legacy:
            flags = ['--no-reload', 'disable'] if defer else ['disable', '--now']
            run('systemctl', '--user', *flags, LEGACY_UNIT, offline=defer)
        if not defer:
            run('systemctl', '--user', 'stop', UNIT, check=False)
        for path, (data, mode) in writes.items():
            old = previous['files'].get(str(path))
            transaction.write(path, data, mode)
            original, original_mode = transaction.before[path]
            manifest['files'][str(path)] = {
                'original': old['original'] if old else base64.b64encode(original).decode() if original is not None else None,
                'original_mode': old['original_mode'] if old else original_mode,
                'installed_hash': digest(data),
            }
        desktop = paths.data / 'applications/discord.desktop'
        for candidate in writes:
            if candidate.suffix == '.desktop':
                run('desktop-file-validate', str(candidate))
        result = run('Hyprland', '--verify-config', '--config', str(paths.main_config), check=False)
        if result.returncode:
            raise RuntimeError('Configuração rejeitada: ' + result.stdout + result.stderr)
        # Offline enable writes the user target link without contacting a manager.
        run('systemctl', '--user', '--no-reload', 'enable', str(paths.unit), offline=True)
        if not defer:
            run('systemctl', '--user', 'daemon-reload')
            if plugin_was_loaded and old_plugin and old_plugin != str(target):
                run('hyprctl', 'plugin', 'unload', old_plugin)
                plugin_replaced = True
            release_loader.activate(paths)
            run('systemctl', '--user', 'start', UNIT, timeout=180)
            if not service_state(UNIT)['active']:
                raise RuntimeError('O serviço não iniciou.')
            reload_config()
            wait_ready(config)
        paths.manifest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        paths.manifest.parent.chmod(0o700)
        transaction.write(paths.manifest, (json.dumps(manifest, indent=2) + '\n').encode(), 0o600)
    except Exception:
        run('systemctl', '--user', '--no-reload', 'disable', UNIT, check=False, offline=True)
        if not defer:
            run('systemctl', '--user', 'stop', UNIT, check=False)
            if (not plugin_was_loaded or plugin_replaced) and release_loader.loaded():
                run('hyprctl', 'plugin', 'unload', str(target), check=False)
        transaction.rollback()
        if not defer:
            if plugin_replaced:
                run('hyprctl', 'plugin', 'load', old_plugin, check=False)
            run('systemctl', '--user', 'daemon-reload', check=False)
            reload_config()
        for unit, state in services.items():
            restore_service(unit, state, offline=defer)
        raise
    if shutil.which('update-desktop-database'):
        run('update-desktop-database', str(paths.data / 'applications'), check=False)
    return {'installed': True, 'deferred': defer, 'profile': config, 'legacy_migrated': legacy}


def remove(paths, defer=False):
    manifest = read_manifest(paths)
    if not paths.manifest.exists():
        return {'removed': False, 'message': 'Nenhuma instalação registrada.'}
    changes, preserved = {}, []
    for name, entry in manifest['files'].items():
        path = Path(name)
        if not path.exists():
            continue
        current = path.read_bytes()
        original = base64.b64decode(entry['original']) if entry['original'] is not None else None
        if digest(current) == entry['installed_hash']:
            changes[path] = (original, entry['original_mode'] or 0o644)
        elif path == paths.main_config:
            text = current.decode()
            expected = BEGIN + '\ndofile(' + lua_string(str(paths.package / 'ptt.lua')) + ')\n' + END
            if block(text, 'omarchy-ptt') != expected:
                preserved.append(name)
                continue
            text = without(text, 'omarchy-ptt')
            if original:
                old_focus = block(original.decode(), 'discord-ptt-focus')
                if old_focus and not block(text, 'discord-ptt-focus'):
                    text += '\n' + old_focus + '\n'
            changes[path] = (text.encode(), path.stat().st_mode & 0o777)
        else:
            preserved.append(name)
    # Do not remove the runtime while a modified main config still references it.
    if str(paths.main_config) in preserved:
        raise RuntimeError('O bloco de inclusão foi editado. Remova-o antes de desinstalar; arquivos preservados.')
    transaction = Transaction()
    old_service = service_state(UNIT, offline=defer)
    try:
        run('systemctl', '--user', '--no-reload', 'disable', UNIT, check=False, offline=True)
        if not defer:
            run('systemctl', '--user', 'stop', UNIT)
        for path, (data, mode) in changes.items():
            transaction.write(path, data, mode)
        if not defer:
            run('systemctl', '--user', 'daemon-reload')
            reload_config()
            if release_loader.loaded():
                run('hyprctl', 'plugin', 'unload', manifest['plugin_file'])
                reload_config()
        if manifest.get('legacy_service') and str(paths.config / 'hypr/bindings.lua') not in preserved:
            restore_service(LEGACY_UNIT, manifest['legacy_service'], offline=defer)
        restore_service(UNIT, manifest.get('prior_service', {'enabled': False, 'active': False}), offline=defer)
        if preserved:
            # Keep the recovery record for files deliberately left untouched.
            manifest['files'] = {name: manifest['files'][name] for name in preserved}
            manifest['removed_with_preserved_files'] = True
            transaction.write(paths.manifest, (json.dumps(manifest, indent=2) + '\n').encode(), 0o600)
        else:
            transaction.write(paths.manifest, None)
    except Exception:
        transaction.rollback()
        if not defer:
            run('systemctl', '--user', 'daemon-reload', check=False)
            reload_config()
        restore_service(UNIT, old_service, offline=defer)
        raise
    if shutil.which('update-desktop-database'):
        run('update-desktop-database', str(paths.data / 'applications'), check=False)
    return {'removed': True, 'preserved': preserved}
