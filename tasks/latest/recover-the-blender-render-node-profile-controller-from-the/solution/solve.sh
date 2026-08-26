#!/bin/bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$DIR/blendprofile.py" /app/src/blendprofile.py
cp "$DIR/blendprofile-reconcile@.service" /app/systemd/blendprofile-reconcile@.service
cp "$DIR/blendprofile.conf" /app/tmpfiles.d/blendprofile.conf
make -C /app clean install
