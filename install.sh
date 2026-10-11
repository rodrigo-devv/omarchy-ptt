#!/usr/bin/env bash
set -euo pipefail
ptt_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$ptt_root/bin/omarchy-ptt" setup "$@"
