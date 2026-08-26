#!/bin/sh
# Ensure tmux socket dir exists before terminus harness starts tmux.
# tmpfs avoids EOVERFLOW on overlay /tmp, /app, and /logs inode numbers.
# Do not remove $TMUX_TMPDIR/tmux-* here — BASH_ENV runs every bash startup and
# would delete a live socket between harness start and agent attach.
export TMUX_TMPDIR=/dev/shm/terminus-tmux
export TMPDIR=/app/tmp
mkdir -p "$TMPDIR" "$TMUX_TMPDIR" /logs/verifier /logs/agent 2>/dev/null || true
chmod 1777 "$TMPDIR" 2>/dev/null || true
chmod 700 "$TMUX_TMPDIR" 2>/dev/null || true
if [ -d "$TMUX_TMPDIR/tmux-0/default" ]; then
  rm -rf "$TMUX_TMPDIR/tmux-0" 2>/dev/null || true
fi
for legacy in /tmp/tmux-0 /tmp/tmux-* /app/tmux /logs/agent/tmux; do
  [ -e "$legacy" ] && rm -rf "$legacy" 2>/dev/null || true
done
