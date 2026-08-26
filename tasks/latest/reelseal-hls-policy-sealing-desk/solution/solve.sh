#!/usr/bin/env bash
# Oracle solve — ReelSeal desk seal path
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app

install -m 0644 "$ROOT_DIR/files/internal/mediain/fetch.go" /app/internal/mediain/fetch.go
install -m 0644 "$ROOT_DIR/files/internal/hlsdrv/segment.go" /app/internal/hlsdrv/segment.go
install -m 0644 "$ROOT_DIR/files/internal/apiclient/client.go" /app/internal/apiclient/client.go
install -m 0644 "$ROOT_DIR/files/internal/cryptout/manifest.go" /app/internal/cryptout/manifest.go
install -m 0644 "$ROOT_DIR/files/internal/stampv/validate.go" /app/internal/stampv/validate.go
install -m 0644 "$ROOT_DIR/files/internal/packgate/gpg_pack.go" /app/internal/packgate/gpg_pack.go
install -m 0644 "$ROOT_DIR/files/policyapi/main.go" /app/policyapi/main.go

bash /app/scripts/rebuild-reelseal.sh
test -x /app/bin/reelseal
test -x /app/bin/reelseal-policyapi

bash /app/scripts/start-policy-api.sh
rm -rf /app/state /app/output
mkdir -p /app/state /app/output

/app/scripts/reelseal-desk.sh run-all

test -s /app/state/media-fetch.json
test -s /app/state/hls/index.m3u8
test -s /app/state/policy-bind.json
test -s /app/output/encryption-manifest.json
test -s /app/state/validation-stamp.json
test -s /app/state/release-attest.json
test -s /app/output/release-package.tar

python3 - <<'PY'
import json
from pathlib import Path
man = json.loads(Path("/app/output/encryption-manifest.json").read_text())
assert "key_uri" not in man
assert man["method"] == "AES-128"
assert man["schema"] == "reelseal.encryption-manifest/v1"
stamp = json.loads(Path("/app/state/validation-stamp.json").read_text())
assert stamp["accepted"] is True
print("oracle_ok")
PY
