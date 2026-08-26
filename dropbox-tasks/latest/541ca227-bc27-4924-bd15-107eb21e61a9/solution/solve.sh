#!/bin/bash
set -euo pipefail

export PATH="/usr/local/go/bin:/usr/local/bin:${PATH}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

patch -d /app/environment -p0 < "$ROOT_DIR/patches/01-reg.patch"
patch -d /app/environment -p0 < "$ROOT_DIR/patches/02-lse.patch"
patch -d /app/environment -p0 < "$ROOT_DIR/patches/03-pub.patch"
patch -d /app/environment -p0 < "$ROOT_DIR/patches/04-wal.patch"
patch -d /app/environment -p0 < "$ROOT_DIR/patches/05-qtn.patch"
patch -d /app/environment -p0 < "$ROOT_DIR/patches/06-engine.patch"

cd /app/environment
bash /app/environment/scripts/build_linkctl.sh
rm -rf /app/output/* /app/var/state
bash /app/scripts/run_link_ops.sh alpha
