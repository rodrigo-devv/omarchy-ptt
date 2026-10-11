Omarchy PTT 0.1.0-beta.3

Discord push-to-talk across workspaces on Omarchy with Lua Hyprland configuration.

- Fix workspace jumps caused by activation requests from other XWayland clients
  during PTT. Protection lasts through the hold and 200 ms after release.
  Manual focus and workspace changes remain available.
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
successfully; live profile changes were checked and Mouse9 restored. The user confirmed the workspace-jump fix works on this desktop.
A full fresh-install machine still needs functional validation.
This is an independent community beta, not an official Omarchy/Discord tool.
