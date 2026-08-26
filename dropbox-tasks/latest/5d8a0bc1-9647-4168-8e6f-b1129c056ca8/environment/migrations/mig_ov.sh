#!/bin/bash
set -euo pipefail
ROOT="/app/environment"
SCRATCH="${ROOT}/kit/scratch"
SEED="${ROOT}/kit/seed/arena_seed.bin"
ANCHOR="${SCRATCH}/anchor.bin"

mkdir -p "${SCRATCH}"

if [[ "${1:-}" == "--restore-anchors" ]]; then
  # Idempotent: reload both training and adversarial anchors into scratch.
  python3 - <<'PY'
from pathlib import Path
seed = Path("/app/environment/kit/seed/arena_seed.bin").read_bytes()
if len(seed) < 40 or seed[:8] != b"OVSEED01":
    raise SystemExit("bad seed")
# Prefer adversarial anchor when present (covers held-out arms); also write dual file.
Path("/app/environment/kit/scratch").mkdir(parents=True, exist_ok=True)
Path("/app/environment/kit/scratch/anchor.bin").write_bytes(seed[8:24])
Path("/app/environment/kit/scratch/anchor_adv.bin").write_bytes(seed[24:40])
PY
  exit 0
fi

# Destructive reset: drop scratch bytes without preserving anchors.
rm -f "${SCRATCH}"/* 2>/dev/null || true
