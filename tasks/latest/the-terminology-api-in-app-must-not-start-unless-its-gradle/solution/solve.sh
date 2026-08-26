#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd /app
patch -p0 < "${ROOT_DIR}/fix.patch"

chmod +x /app/kit/h2.sh /app/kit/r7.sh /app/kit/v3.sh

./gradlew --offline --no-daemon updateHfAssetLock
./gradlew --offline --no-daemon validateHfAssetLock
./gradlew --offline --no-daemon check
./gradlew --offline --no-daemon bootJar

python3 - <<'PY'
import json, subprocess
from pathlib import Path

lock = json.loads(Path("/app/config/hf-assets.lock.json").read_text())
required = [
    "lock_schema_version", "repository", "revision", "source_metadata_digest",
    "transcript_digest", "gradle_lock_digest", "routes",
]
for key in required:
    assert key in lock, key

transcript = Path("/app/docs/release-council-transcript.md")
digest = subprocess.check_output(["sha256sum", str(transcript)], text=True).split()[0]
assert lock["transcript_digest"] == digest
PY
