#!/usr/bin/env bash
set -euo pipefail

GRAPH_PATH="${CHAMBER_GRAPH_PATH:?}"
PORT="${CHAMBER_PORT:?}"
HANDLER="${CHAMBER_HANDLER:?}"
PROC_NAME="${CHAMBER_PROC_NAME:-chamberd}"

# Keep the live graph open for the lifetime of the listener.
exec 9<"$GRAPH_PATH"
exec -a "$PROC_NAME" socat "TCP-LISTEN:${PORT},reuseaddr,fork" "EXEC:${HANDLER}"
