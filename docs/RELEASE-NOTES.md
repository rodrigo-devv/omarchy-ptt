Omarchy PTT 0.1.0-beta.2

Discord push-to-talk across workspaces on Omarchy with Lua Hyprland configuration.

- First install can import one existing compatible Discord mouse PTT shortcut.
- Focused button selector and “Discord PTT Configuration” applications menu item.
- Change the button with `omarchy-ptt configure`; re-import with `--from-discord`.
- User-scoped service, X11 launcher, portable profiles, backups and rollback.
- Source-built release observer with Hyprland ABI guards; no input-device access.

Install as your desktop user: extract the source archive and run
`./install.sh --install-deps`. A fresh account still needs its PTT shortcut and
input mode configured in Discord. Automatic import supports one enabled,
unmodified Mouse8–Mouse12 shortcut in the official stable Linux/X11 client.

Baseline: Omarchy 4.0.0.alpha, Hyprland 0.56.2, official stable Discord. Old
Hyprland `.conf` configurations and alternative Discord clients are unsupported.
The on-disk Discord schema is unofficial and may change.

37 automated tests passed, including the real selector on an isolated display
and real offline installation in temporary directories. This desktop migrated
successfully; live profile changes were checked and Mouse9 restored. Functional
voice validation of this package and a full fresh-install machine remain pending.
This is an independent community beta, not an official Omarchy/Discord tool.
