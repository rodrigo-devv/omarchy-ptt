"""Build against exact local headers; never ship a compositor-specific binary."""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys

from .config import Paths
from .system import hypr_json, live, reload_config, run

PLUGIN = 'omarchy-ptt-release'


def version():
    if live():
        return hypr_json(['version'])
    return json.loads(run('Hyprland', '--version-json').stdout)


def build(paths, force=False):
    commit = version().get('commit', '')
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise RuntimeError('Não foi possível identificar o build do Hyprland.')
    include = Path(run('pkg-config', '--variable=includedir', 'hyprland').stdout.strip())
    header = include / 'hyprland/src/version.h'
    if not header.exists():
        header = include / 'src/version.h'
    if not header.exists():
        header = Path('/usr/include/hyprland/src/version.h')
    if not re.search(r'#define\s+GIT_COMMIT_HASH\s+"' + re.escape(commit) + '"', header.read_text()):
        raise RuntimeError('Headers e Hyprland em execução diferem. Reinicie a sessão após atualizar.')
    source = Path(__file__).parent / 'resources/release.cpp'
    flags = shlex.split(run('pkg-config', '--cflags', 'hyprland').stdout)
    toolchain = run('c++', '--version').stdout
    # Include dependency versions in the cache identity, not just compositor SHA.
    dependencies = run('pkg-config', '--modversion', 'hyprland', 'hyprutils', 'aquamarine',
                       'hyprgraphics', 'hyprcursor', 'hyprlang').stdout
    digest = hashlib.sha256(source.read_bytes() + header.read_bytes() +
                            (str(flags) + toolchain + dependencies).encode()).hexdigest()[:20]
    target = paths.cache / 'omarchy-ptt' / commit / digest / 'release.so'
    if force or not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        pending = target.with_name(f'release.{os.getpid()}.tmp.so')
        try:
            run('c++', '-std=c++23', '-O2', '-shared', '-fPIC', '-fno-gnu-unique',
                '-Wall', '-Wextra', *flags, str(source), '-o', str(pending), timeout=120)
            os.replace(pending, target)
        finally:
            pending.unlink(missing_ok=True)
    return target


def loaded():
    return any(p.get('name') == PLUGIN for p in hypr_json(['plugin', 'list']))


def activate(paths):
    if not loaded():
        target = build(paths)
        result = run('hyprctl', 'plugin', 'load', str(target)).stdout.strip()
        if result != 'ok' or not loaded():
            raise RuntimeError('Extensão não carregada: ' + result)
    # Lua may have initialized before the plugin; register its release callback now.
    reload_config()


def main():
    try:
        activate(Paths.discover())
    except Exception as error:
        # Keep ordinary PTT available; Lua releases on workspace change in this mode.
        print('PTT em modo reduzido: ' + str(error), file=sys.stderr, flush=True)
