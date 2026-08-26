#!/usr/bin/env bash
set -euo pipefail
ENV="${VX_ENV_ROOT:-/app/environment}"

# Restore policy bodies from /app/environment/q2m mirrors, then rebuild.
for m in p3k q7n t2w u8m v5r x1h w4z n9p g6k k7r; do
  mkdir -p "${ENV}/${m}/src"
  if [[ -d "${ENV}/q2m/${m}/src" ]]; then
    cp -a "${ENV}/q2m/${m}/src/." "${ENV}/${m}/src/"
  fi
done

printf '"axle": "0000000000000000"\n"rotor": "1111111111111111"\n' > "${ENV}/meta/seal.bin"

cd "${ENV}"
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
mkdir -p /app/bin
cp -f build/vx_bond /app/bin/vx_run
echo "recovered"
