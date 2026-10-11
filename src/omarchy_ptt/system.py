import json
import os
import subprocess


def run(*args, check=True, timeout=30, offline=False):
    env = dict(os.environ, SYSTEMD_OFFLINE='1') if offline else None
    result = subprocess.run(args, text=True, capture_output=True, check=False, timeout=timeout, env=env)
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"{args[0]} falhou ({result.returncode}): {detail}")
    return result


def hypr_json(command):
    return json.loads(run('hyprctl', '-j', *command).stdout)


def live():
    return bool(os.getenv('HYPRLAND_INSTANCE_SIGNATURE'))


def reload_config():
    result = run('hyprctl', 'reload')
    if result.stdout.strip() != 'ok':
        raise RuntimeError("Falha ao recarregar Hyprland: " + result.stdout.strip())
    errors = run('hyprctl', 'configerrors').stdout.strip()
    if errors:
        raise RuntimeError("Hyprland reportou erros: " + errors)
