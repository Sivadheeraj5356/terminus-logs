#!/bin/bash
# Harbor starts the agent through tmux as the image user (root).
# Drop interactive agent sessions to unprivileged rebooker so the
# candidate cannot mutate root-owned verifier/toolchain assets.
set -euo pipefail
TMUX_REAL="/usr/bin/tmux.real"
if [ "$(id -u)" -eq 0 ] && id -u rebooker >/dev/null 2>&1; then
  export HOME=/home/rebooker
  export USER=rebooker
  export LOGNAME=rebooker
  exec /usr/sbin/runuser -u rebooker -- "${TMUX_REAL}" "$@"
fi
exec "${TMUX_REAL}" "$@"
