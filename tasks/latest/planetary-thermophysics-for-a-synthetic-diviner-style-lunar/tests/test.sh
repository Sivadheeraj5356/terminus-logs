#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/cargo/bin:/root/.cargo/bin:${HOME:-/root}/.cargo/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt

if [ "${PWD:-/}" = "/" ]; then
  echo "Error: no working directory configured" >&2
  exit 1
fi

if [ ! -f /app/Cargo.toml ]; then
  echo "Error: /app/Cargo.toml missing" >&2
  exit 1
fi

cd /app

if ! cargo build --release --locked --offline; then
  echo "Error: candidate Cargo build failed" >&2
  exit 1
fi

mapfile -t bin_names < <(
  awk '
    /^\[\[bin\]\]$/ {
      in_bin = 1
      next
    }

    /^\[/ && in_bin {
      in_bin = 0
    }

    in_bin && /^name[[:space:]]*=/ {
      line = $0
      sub(/^[^"]*"/, "", line)
      sub(/".*$/, "", line)
      print line
    }
  ' /app/Cargo.toml
)

if [ "${#bin_names[@]}" -ne 1 ]; then
  echo "Error: expected one binary target, found ${#bin_names[@]}" >&2
  exit 1
fi

export CANDIDATE_BIN="/app/target/release/${bin_names[0]}"
export LUNAR_REGOLITH_SOLVER_BIN="$CANDIDATE_BIN"
export TEST_DIR="${TEST_DIR:-/tests}"

if [ ! -x "$CANDIDATE_BIN" ]; then
  echo "Error: candidate binary missing: $CANDIDATE_BIN" >&2
  exit 1
fi

set +e
python3 -m pytest \
  -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json \
  "$TEST_DIR/test_outputs.py" \
  -rA
rc=$?
if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
