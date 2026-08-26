#!/usr/bin/env bash
stamp_digest() {
  local profile="$1"
  local carry="$2"
  shift 2
  python3 - "$profile" "$carry" "$@" <<'PY'
import hashlib, sys
profile, carry = sys.argv[1], sys.argv[2]
names = list(sys.argv[3:])
body = profile + ":" + ",".join(names) + ":" + carry
print(hashlib.sha256(body.encode()).hexdigest()[:16])
PY
}

weight_order() {
  local tbl="$1"
  python3 - "$tbl" <<'PY'
import sys
from pathlib import Path
weights = {}
for line in Path(sys.argv[1]).read_text().splitlines():
    parts = line.strip().split("\t")
    if len(parts) == 2:
        weights[parts[0]] = int(parts[1])
names = sorted(weights.keys())
print("\n".join(names))
PY
}
