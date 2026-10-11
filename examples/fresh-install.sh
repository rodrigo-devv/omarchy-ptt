#!/usr/bin/env bash
# Run after installing Omarchy, as the regular desktop user.
# The installer automatically defers activation when outside Hyprland.
set -euo pipefail
ptt_pack_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ptt_pack_root/install.sh" --install-deps \
  --profile "$ptt_pack_root/profiles/mouse9.json" "$@"
