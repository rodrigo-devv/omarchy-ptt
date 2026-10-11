import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from . import __version__
from .config import DEFAULT, Paths, fingerprint, load, validate
from . import installer, release_loader, discord_settings, selector
from .system import hypr_json, live, run


def status(paths):
    report = {'version': __version__, 'installed': paths.manifest.exists(),
              'profile': load(paths.profile) if paths.profile.exists() else None,
              'session': live(), 'service': 'unknown', 'plugin_loaded': False,
              'bridge_ready': False, 'ready': False, 'discord': [], 'errors': []}
    if not live():
        report['errors'].append('Sem sessão Hyprland; instalação preparada será ativada no login.')
        return report
    for name, command in [('active', 'is-active'), ('enabled', 'is-enabled')]:
        report['service_' + name] = run('systemctl', '--user', command, installer.UNIT, check=False).stdout.strip()
    report['service'] = report['service_active']
    try:
        report['hyprland'] = hypr_json(['version'])
        report['plugin_loaded'] = release_loader.loaded()
        report['config_errors'] = run('hyprctl', 'configerrors').stdout.strip()
        report['discord'] = [{'xwayland': w.get('xwayland'), 'workspace': w.get('workspace', {}).get('id')}
                             for w in hypr_json(['clients']) if w.get('class', '').lower() == 'discord']
        ready = Path(os.getenv('XDG_RUNTIME_DIR', '/nonexistent')) / 'omarchy-ptt.ready'
        if ready.exists() and report['profile']:
            lines = ready.read_text().splitlines()
            report['bridge_ready'] = (len(lines) >= 6 and lines[0] == os.getenv('HYPRLAND_INSTANCE_SIGNATURE')
                and 0 <= time.time() - int(lines[1]) <= 2 and lines[4] == fingerprint(report['profile']))
    except Exception as error:
        report['errors'].append(str(error))
    report['ready'] = (report['installed'] and report['service'] == 'active' and
                       report['plugin_loaded'] and report['bridge_ready'] and not report.get('config_errors'))
    if report['installed'] and not report['plugin_loaded']:
        report['errors'].append('Extensão ausente: PTT encerra ao trocar workspace. Consulte journalctl --user -u omarchy-ptt.')
    if any(not w['xwayland'] for w in report['discord']):
        report['errors'].append('Discord aberto em Wayland. Encerre-o completamente e reabra pelo menu de aplicações.')
        report['ready'] = False
    return report


def doctor(paths):
    report = status(paths)
    try:
        installer.dependencies()
        report['dependencies'] = 'ok'
    except Exception as error:
        report['dependencies'] = str(error)
    report['lua_config'] = paths.main_config.exists()
    report['config_path'] = str(paths.profile)
    report['log_command'] = 'journalctl --user -u omarchy-ptt.service -n 50 --no-pager'
    return report


def parser():
    result = argparse.ArgumentParser(prog='omarchy-ptt', description='Discord PTT entre workspaces no Omarchy (instalação por usuário).')
    result.add_argument('--version', action='version', version=__version__)
    commands = result.add_subparsers(dest='command', required=True,
        metavar='{setup,configure,detect-discord,status,doctor,remove,export-profile,launch-discord}')
    setup = commands.add_parser('setup', help='Instalar ou atualizar preservando a configuração pessoal.')
    setup.add_argument('--profile', type=Path, help='Perfil JSON portátil, sem caminhos da máquina original.')
    setup.add_argument('--linux-button', type=int, help='Código Hyprland/libinput, padrão 276.')
    setup.add_argument('--x11-button', type=int, help='Número no Discord/X11, padrão 9.')
    setup.add_argument('--defer', action='store_true', help='Preparar o próximo login sem tocar na sessão atual.')
    setup.add_argument('--install-deps', action='store_true', help='Instalar dependências ausentes via sudo pacman.')
    setup.add_argument('--dry-run', action='store_true', help='Mostrar o plano sem instalar ou compilar.')
    setup.add_argument('--migrate', action='store_true', help='Substituir a integração local anterior com backup.')
    setup.add_argument('--capture', action='store_true', help='Escolher o botão em uma janela antes de instalar.')
    setup.add_argument('--from-discord', action='store_true', help='Exigir importação do atalho local do Discord.')
    setup.add_argument('--no-detect', action='store_true', help='Usar Mouse9 sem procurar o atalho do Discord.')
    configure = commands.add_parser('configure', help='Configuração PTT Discord: trocar botão ou importar o atalho existente.')
    configure.add_argument('--from-discord', action='store_true')
    configure.add_argument('--profile', type=Path)
    configure.add_argument('--linux-button', type=int)
    configure.add_argument('--x11-button', type=int)
    configure.add_argument('--dry-run', action='store_true')
    commands.add_parser('detect-discord', help='Mostrar somente o perfil PTT local do Discord, sem alterar arquivos.')
    for name in ('status', 'doctor'):
        command = commands.add_parser(name)
        command.add_argument('--json', action='store_true')
    remove = commands.add_parser('remove', help='Restaurar arquivos originais e preservar edições posteriores.')
    remove.add_argument('--defer', action='store_true')
    export = commands.add_parser('export-profile', help='Exportar apenas preferências para outra máquina.')
    export.add_argument('destination', type=Path)
    commands.add_parser('launch-discord', help='Abrir pelo launcher X11 instalado; não encerra chamadas.')
    commands.add_parser('bridge', help=argparse.SUPPRESS)
    commands.add_parser('release-load', help=argparse.SUPPRESS)
    commands._choices_actions = [action for action in commands._choices_actions if action.help != argparse.SUPPRESS]
    return result


def choose_profile(args, paths):
    explicit = args.profile or args.linux_button is not None or args.x11_button is not None
    capture = getattr(args, 'capture', False)
    from_discord = args.from_discord
    no_detect = getattr(args, 'no_detect', False)
    if sum(bool(x) for x in (explicit, capture, from_discord, no_detect)) > 1:
        raise ValueError('Escolha apenas uma origem: perfil/códigos, captura, Discord ou --no-detect.')
    if (args.linux_button is None) != (args.x11_button is None):
        raise ValueError('Informe --linux-button e --x11-button juntos ou use o seletor.')
    if from_discord:
        return discord_settings.detect(paths), 'discord'
    if args.profile:
        config = load(args.profile)
    elif paths.profile.exists():
        config = load(paths.profile)
    else:
        config = DEFAULT.copy()
    if explicit:
        for key in ('linux_button', 'x11_button'):
            if getattr(args, key) is not None:
                config[key] = getattr(args, key)
        return validate(config), 'explicit'
    if no_detect:
        return DEFAULT.copy(), 'default'
    if not capture and args.command == 'setup' and paths.profile.exists():
        return config, 'existing'
    if not capture and args.command == 'setup':
        try:
            return discord_settings.detect(paths), 'discord'
        except (ValueError, OSError) as error:
            print('Importação automática indisponível: ' + str(error), file=sys.stderr)
            if args.dry_run or not os.getenv('DISPLAY'):
                raise ValueError('Escolha --profile, --no-detect ou --capture dentro da sessão gráfica.') from error
    if args.dry_run:
        raise ValueError('Captura precisa da janela; para --dry-run informe um perfil ou --from-discord.')
    if not os.getenv('DISPLAY'):
        raise ValueError('Abra a configuração na sessão gráfica ou use --profile/--from-discord.')
    try:
        return selector.capture(), 'capture'
    except ImportError as error:
        raise RuntimeError('Seletor requer python-xlib. Instale-o ou use --profile.') from error


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        paths = Paths.discover()
        if args.command == 'bridge':
            from .bridge import main as bridge_main
            bridge_main()
            return
        if args.command == 'release-load':
            release_loader.main()
            return
        if args.command in ('setup', 'configure'):
            if args.command == 'configure' and not paths.manifest.exists():
                raise RuntimeError('Execute setup primeiro; configure altera uma instalação existente.')
            if args.command == 'setup' and args.install_deps and not args.dry_run:
                installer.dependencies(install=True)
            config, origin = choose_profile(args, paths)
            print(f"Botão: Mouse{config['x11_button']} (origem: {origin}).")
            report = installer.setup(paths, config, defer=args.defer or not live(),
                install_deps=getattr(args, 'install_deps', False), dry_run=args.dry_run,
                migrate=getattr(args, 'migrate', False)) if args.command == 'setup' else installer.setup(
                    paths, config, defer=not live(), dry_run=args.dry_run)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            if not args.dry_run:
                if origin == 'discord':
                    print('\nAtalho local importado. Verifique se o modo de entrada no Discord está em Push-to-Talk.')
                else:
                    print(f"\nNo Discord: Voz e Vídeo → Push-to-Talk → grave Mouse {config['x11_button']}.")
                print('Use o launcher Discord do menu. Encerre uma instância Wayland antes de reabrir.')
                print('Teste: segure, mude de workspace, solte; o foco deve permanecer onde você estava.')
        elif args.command == 'detect-discord':
            print(json.dumps(discord_settings.detect(paths), ensure_ascii=False, indent=2))
        elif args.command in ('status', 'doctor'):
            report = (doctor if args.command == 'doctor' else status)(paths)
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print(f"Omarchy PTT {__version__}: " + ('pronto' if report.get('ready') else 'aguardando configuração/sessão'))
                print('Serviço: ' + report['service'])
                print('Extensão: ' + ('carregada' if report['plugin_loaded'] else 'ausente'))
                print('Ponte: ' + ('pronta' if report['bridge_ready'] else 'indisponível'))
                if not report['discord']:
                    print('Abra o Discord pelo menu e configure seu PTT.')
                for error in report['errors']:
                    print('• ' + error)
                if args.command == 'doctor':
                    print('Dependências: ' + report['dependencies'])
                    print('Logs: ' + report['log_command'])
        elif args.command == 'remove':
            print(json.dumps(installer.remove(paths, args.defer or not live()), ensure_ascii=False, indent=2))
        elif args.command == 'export-profile':
            config = load(paths.profile) if paths.profile.exists() else DEFAULT
            if args.destination.exists():
                raise ValueError('Destino já existe; escolha outro arquivo para preservar seu perfil.')
            args.destination.parent.mkdir(parents=True, exist_ok=True)
            args.destination.write_text(json.dumps(config, indent=2) + '\n')
            print('Perfil portátil salvo em ' + str(args.destination))
        elif args.command == 'launch-discord':
            if live() and any(not w.get('xwayland') for w in hypr_json(['clients']) if w.get('class', '').lower() == 'discord'):
                raise RuntimeError('Encerre o Discord Wayland antes de reabrir; uma chamada pode estar em andamento.')
            wrapper = paths.home / '.local/bin/discord-ptt-x11'
            if not wrapper.exists():
                raise RuntimeError('Execute setup primeiro.')
            command = [str(wrapper)]
            if shutil.which('uwsm-app'):
                command.insert(0, 'uwsm-app')
            subprocess.Popen(command, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print('Omarchy PTT: ' + str(error), file=sys.stderr)
        sys.exit(1)
