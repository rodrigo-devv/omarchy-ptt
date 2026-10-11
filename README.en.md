# Omarchy PTT

User-scoped Discord push-to-talk across Hyprland workspaces, including physical
button release after changing workspaces. Version **0.1.0-beta.3**.

The original workflow was manually confirmed on Omarchy 4.0.0.alpha,
Hyprland 0.56.2 and the official stable Discord client. The reusable package
has isolated installer/runtime tests; additional machines still need testing.

## Install

Run as your regular desktop user, after installing Omarchy:

```bash
./install.sh --install-deps
```

First installation imports one compatible saved Discord PTT shortcut, or opens
a focused button selector. Explicit profiles take priority; updates keep the
installed profile. `--no-detect` chooses Mouse9 / Linux `mouse:276`. Missing dependencies are installed
through `sudo pacman` only when `--install-deps` is requested. Existing desktop
configuration is backed up. Unsupported old `.conf` configurations are rejected.

Inside Hyprland, setup validates and starts the service. Outside the graphical
session it enables startup for the next login. Existing Discord calls are not
interrupted. Close an existing Wayland Discord instance and reopen from the app
menu. Select Push-to-Talk in Discord's Voice & Video settings. A new account
or a changed button still requires recording that button in Discord. Keep the Discord window open.

## Change the button

Find **Discord PTT Configuration** in the applications menu, or run:

```bash
omarchy-ptt configure
omarchy-ptt configure --from-discord
omarchy-ptt detect-discord
./install.sh --capture
```

Press and release Mouse8–Mouse12, then confirm with Enter; Esc cancels. The
standard Linux/XWayland mapping is assumed. Remapped mice need an explicit
profile. Only one enabled, unmodified mouse PTT shortcut can be imported.
The local keybinds format is unofficial and may change: unsupported or ambiguous
settings are rejected. The reader does not write, copy or export the Discord
DB, print unrelated values or use network/account credentials. Offline installs
without saved PTT require a profile or `--no-detect`. New accounts still need
to configure Discord itself.

## Portable configuration

```bash
./install.sh --profile profiles/mouse9.json --defer --install-deps
omarchy-ptt export-profile ./fresh-install-pack/ptt.json
omarchy-ptt doctor --json
omarchy-ptt remove
```

Use `--defer` only outside the graphical session. Re-running setup preserves
the installed profile and does not duplicate the include. `--dry-run` lists
the plan without writing or compiling. `--migrate` explicitly migrates the
previous local `discord-ptt-mouse9` integration and keeps a recovery record.

The release observer builds against local Hyprland headers and validates the
compositor ABI. If it is unavailable after an update, PTT ends on a workspace
switch instead of staying stuck; `doctor` reports this reduced mode.

The bridge uses XTEST and does not read `/dev/input`. Other XWayland clients
using the same mouse button may receive input. Test your games and modifiers.
Changed installed files are preserved during removal. Symlinked managed files
are refused to protect dotfile managers.

## Tests and distribution

```bash
/usr/bin/python3 -m unittest discover -s tests -v
OMARCHY_PTT_NATIVE_TESTS=1 /usr/bin/python3 -m unittest discover -s tests -v
/usr/bin/python3 tools/build-release.py
```

Native tests compile the production C++ observer, use the real Hyprland config
parser and install/remove a user unit in isolated temporary XDG directories.
They do not load plugins into the desktop or generate input events.

Source distributions include profiles, documentation and tests, not a
machine-specific plugin binary. Independent community project, MIT licensed.
