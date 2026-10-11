"""Portable profiles, independent of usernames and installation paths."""
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT = {"schema": 1, "linux_button": 276, "x11_button": 9,
           "window_class": "discord", "executable": "discord"}


def validate(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT):
        raise ValueError("Perfil inválido: use apenas os campos do perfil distribuído.")
    result = DEFAULT | value
    if type(result['schema']) is not int or result['schema'] != 1:
        raise ValueError("Versão de perfil não suportada.")
    if type(result['linux_button']) is not int or result['linux_button'] not in range(275, 280):
        raise ValueError("linux_button deve ser um botão lateral entre 275 e 279.")
    if type(result['x11_button']) is not int or not 8 <= result['x11_button'] <= 32:
        raise ValueError("x11_button deve estar entre 8 e 32.")
    # Only the official stable client is validated. Generalize buttons, not clients.
    if result['window_class'] != 'discord' or result['executable'] != 'discord':
        raise ValueError("Esta versão suporta o cliente oficial stable: discord.")
    return result


def load(path):
    return validate(json.loads(Path(path).read_text()))


def fingerprint(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]


def lua_string(value):
    if any(ord(c) < 32 for c in value):
        raise ValueError("Caminhos com caracteres de controle não são suportados.")
    return json.dumps(value, ensure_ascii=False)


@dataclass(frozen=True)
class Paths:
    home: Path
    config: Path
    data: Path
    state: Path
    cache: Path

    @classmethod
    def discover(cls):
        home = Path.home()
        paths = cls(home, Path(os.getenv('XDG_CONFIG_HOME', home / '.config')),
                    Path(os.getenv('XDG_DATA_HOME', home / '.local/share')),
                    Path(os.getenv('XDG_STATE_HOME', home / '.local/state')),
                    Path(os.getenv('XDG_CACHE_HOME', home / '.cache')))
        for path in (paths.home, paths.config, paths.data, paths.state, paths.cache):
            if not path.is_absolute():
                raise ValueError("Os diretórios XDG precisam ser absolutos.")
            lua_string(str(path))
        return paths

    @property
    def package(self):
        return self.data / 'omarchy-ptt'

    @property
    def profile(self):
        return self.config / 'omarchy-ptt/config.json'

    @property
    def manifest(self):
        return self.state / 'omarchy-ptt/installation.json'

    @property
    def main_config(self):
        return self.config / 'hypr/hyprland.lua'

    @property
    def unit(self):
        return self.config / 'systemd/user/omarchy-ptt.service'

    @property
    def launcher(self):
        return self.home / '.local/bin/omarchy-ptt'
