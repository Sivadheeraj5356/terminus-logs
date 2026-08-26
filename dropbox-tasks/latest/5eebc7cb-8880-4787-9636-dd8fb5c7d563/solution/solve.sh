#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ls -la /app/environment
find /app/environment -maxdepth 3 -type f -name '*.go' | sort

head -40 /app/environment/contracts/sync_record_contract.json
sed -n '1,80p' /app/environment/docs/footer_contract.md
sed -n '1,25p' /app/environment/docs/runbook.md
cat /app/environment/payload/cases.json
xxd -l 64 /app/environment/payload/ring_seg.bin || true

grep -Rn 'sel_k\|fold_b\|FlushSoft\|FlushHard\|crossSeed\|cross_seed\|ProjectEpoch' \
  /app/environment/k7 \
  /app/environment/m3 \
  /app/environment/keyring \
  /app/environment/r3 \
  /app/environment/footcache \
  /app/environment/internal/run || true

cd /app/environment

patch -p1 -i "${ROOT_DIR}/patches/proj_core.go.udiff"
patch -p1 -i "${ROOT_DIR}/patches/fold_core.go.udiff"
patch -p1 -i "${ROOT_DIR}/patches/key_resolve.go.udiff"
patch -p1 -i "${ROOT_DIR}/patches/cache_flush.go.udiff"
patch -p1 -i "${ROOT_DIR}/patches/pipeline.go.udiff"
patch -p1 -i "${ROOT_DIR}/patches/footer_stats.go.udiff"

python3 - <<'PY'
from pathlib import Path

emit = Path("/app/environment/r3/emit_mat.go")
text = emit.read_text()
text = text.replace(
    "doc.CrossAadDigest = CrossAadHex(g1Prefix, g2Prefix, 0)",
    "doc.CrossAadDigest = CrossAadHex(g1Prefix, g2Prefix, crossSeed)",
)
needle = '\tpayload := "G|" + a + "|" + b\n\tsum := sha256.Sum256([]byte(payload))'
insert = '\tpayload := "G|" + a + "|" + b\n\tif crossSeed != 0 {\n\t\tpayload += "|" + strconv.FormatUint(uint64(crossSeed), 10)\n\t}\n\tsum := sha256.Sum256([]byte(payload))'
if needle not in text:
    raise SystemExit("emit_mat patch anchor missing")
emit.write_text(text.replace(needle, insert))
PY

go build -C /app/environment -o /tmp/fxctl ./cmd/fxctl

mkdir -p /app/output
bash /app/environment/scripts/purge_state.sh

run_case() {
  local case_id="$1"
  local phase="$2"
  rm -f /app/output/sync_record.json
  /tmp/fxctl --case "${case_id}" --phase "${phase}" --out /app/output/sync_record.json
}

run_case k4 seal
run_case r2 verify
run_case f7 verify
run_case h3 append
run_case h3 verify
run_case h3 verify
run_case j6 verify
run_case f7 verify
run_case j6 verify
run_case n3 verify
run_case z5 verify
run_case q7 verify
run_case w9 verify
run_case b2 verify
run_case c8 verify
run_case d6 verify
run_case r2 verify
run_case r2 verify

bash /app/environment/scripts/purge_state.sh
run_case k4 seal

if [[ ! -s /app/output/sync_record.json ]]; then
  echo "sync record missing after oracle sweep" >&2
  exit 1
fi

if ! grep -q '"record_digest"' /app/output/sync_record.json; then
  echo "record digest field missing" >&2
  exit 1
fi
