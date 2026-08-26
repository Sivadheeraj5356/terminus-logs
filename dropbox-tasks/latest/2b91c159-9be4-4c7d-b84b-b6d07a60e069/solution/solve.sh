#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH_SRC="$ROOT/oracle"
ENV="/app/environment"

install -D -m 0644 "$PATCH_SRC/kernels/pair_ops.cpp" "$ENV/kernels/pair_ops.cpp"
install -D -m 0644 "$PATCH_SRC/vault/segment_store.cpp" "$ENV/vault/segment_store.cpp"
install -D -m 0644 "$PATCH_SRC/wrap/tile_wrap.cpp" "$ENV/wrap/tile_wrap.cpp"
install -D -m 0644 "$PATCH_SRC/session_plane/epoch_fold.cpp" "$ENV/session_plane/epoch_fold.cpp"
install -D -m 0644 "$PATCH_SRC/codec_lane/journal_codec.cpp" "$ENV/codec_lane/journal_codec.cpp"

mkdir -p /app/build /app/output

cmake -S /app/environment -B /app/build -DCMAKE_BUILD_TYPE=Release
cmake --build /app/build -j2

rustc "$ROOT/check_outputs.rs" -O -o /tmp/solution_check
/tmp/solution_check
