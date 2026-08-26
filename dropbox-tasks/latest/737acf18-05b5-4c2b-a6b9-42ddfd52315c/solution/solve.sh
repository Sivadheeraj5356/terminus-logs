#!/bin/bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd /app

# 1) Point source replacement at the active local-registry mirror.
mkdir -p /app/.cargo
cat > /app/.cargo/config.toml <<'EOF'
# Offline source replacement for the air-gapped vendor lane.
[source.crates-io]
replace-with = "offline-mirror"

[source.offline-mirror]
local-registry = "/app/mirror"
EOF
cp /app/.cargo/config.toml /app/cargo-config.toml

# 2) Restore hyphenated sparse-style index path for cfg-if.
mkdir -p /app/mirror/index/cf/g-
if [[ -f /app/mirror/index/cf/gi/cfg-if ]]; then
  mv /app/mirror/index/cf/gi/cfg-if /app/mirror/index/cf/g-/cfg-if
  rmdir /app/mirror/index/cf/gi 2>/dev/null || true
fi

# 3) Restore bitflags lockfile checksum to match the on-disk .crate.
python3 -u - <<'PY'
from pathlib import Path
import hashlib
lock = Path("/app/Cargo.lock")
crate = Path("/app/mirror/bitflags-2.4.1.crate")
digest = hashlib.sha256(crate.read_bytes()).hexdigest()
text = lock.read_text()
import re
text2, n = re.subn(
    r'(name = "bitflags"\nversion = "2\.4\.1"\nsource = "[^"]+"\nchecksum = ")[0-9a-f]+(")',
    r"\g<1>" + digest + r"\2",
    text,
    count=1,
)
if n != 1:
    raise SystemExit(f"bitflags checksum rewrite failed (n={n})")
lock.write_text(text2)
print("bitflags checksum ->", digest)
PY

rm -rf /app/target
/app/scripts/offline_build.sh
