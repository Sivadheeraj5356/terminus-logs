#!/bin/bash
set -euo pipefail
WORKDIR="${1:-/tmp/fleet_verify}"
mkdir -p "$WORKDIR/units"
tar -xf /app/output/fleet_units.tar -C "$WORKDIR"
for f in "$WORKDIR"/units/*; do
  systemd-analyze verify "$f"
done
