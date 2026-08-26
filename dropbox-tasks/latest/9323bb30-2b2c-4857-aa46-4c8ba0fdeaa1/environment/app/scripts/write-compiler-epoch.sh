#!/usr/bin/env bash
# Write /app/var/compiler-epoch.json from attn-profile spine_salt (residency-seal-schema.md).
# MODE=presence (build.sh) → rebuild_nonce=0
# MODE=rebuild (rebuild.sh) → rebuild_nonce from epoch material
set -euo pipefail
ROOT="${KVTILE_APP_ROOT:-/app}"
PROFILE="${1:-${ROOT}/config/attn-profile.json}"
MODE="${2:-presence}"
python3 - "${ROOT}" "${PROFILE}" "${MODE}" <<'PY'
import hashlib, json, pathlib, sys

root = pathlib.Path(sys.argv[1])
profile_path = pathlib.Path(sys.argv[2])
mode = sys.argv[3].strip().lower()
spine_salt = 0
if profile_path.is_file():
    try:
        spine_salt = int(json.loads(profile_path.read_text(encoding="utf-8")).get("spine_salt", 0) or 0)
    except (json.JSONDecodeError, TypeError, ValueError):
        spine_salt = 0
material = f"kvtile-compiler-epoch|{spine_salt}".encode("utf-8")
epoch = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
if mode == "rebuild":
    nonce_material = f"kvtile-rebuild-nonce|{epoch}".encode("utf-8")
    rebuild_nonce = int.from_bytes(hashlib.sha256(nonce_material).digest()[:8], "big")
else:
    rebuild_nonce = 0
out_dir = root / "var"
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "compiler-epoch.json").write_text(
    json.dumps(
        {"epoch_u64": epoch, "rebuild_nonce": rebuild_nonce},
        separators=(",", ":"),
    )
    + "\n",
    encoding="utf-8",
)
PY
