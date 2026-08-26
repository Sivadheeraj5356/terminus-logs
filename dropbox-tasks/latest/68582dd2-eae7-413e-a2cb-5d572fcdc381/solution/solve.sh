#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
patch -p1 --forward --batch -d /app < fix.patch

python3 -m compileall -q /app/src

rm -rf /output/restore-root /output/restore-log.json

/app/bin/restore-bundle \
  --archives-dir /app/archives \
  --manifest /app/manifests/simple-svc.json \
  --output /output/restore-root \
  --idmap /app/config/idmap.toml \
  --log /output/restore-log.json

/app/bin/restore-bundle \
  --archives-dir /app/archives \
  --manifest /app/manifests/meta-svc.json \
  --output /output/restore-root \
  --idmap /app/config/idmap.toml \
  --log /output/restore-log.json

python3 - <<'PY'
import json
from pathlib import Path
log = json.loads(Path('/output/restore-log.json').read_text())
assert log.get('schema_version') == 1
assert log.get('status') == 'ok'
text = Path('/output/restore-log.json').read_text()
assert '/tmp/' not in text
PY
