#!/bin/bash
set -euo pipefail

# 6-phase build-from-scratch walkthrough for a fresh reader. Deterministic,
# offline, and idempotent — runs against the same warm cargo cache the
# reviewer sees.

SOLUTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ────────────────────────────────────────────────────────────────
# Phase 1 — inventory. What's in the crate, what's the stub surface.
# ────────────────────────────────────────────────────────────────
echo "== phase 1 : inventory =="
ls -1 /app/src
ls -1 /app/src/src
ls -1 /app/src/docs
# `head` closes the pipe after N lines; guard the producer from SIGPIPE
# (exit 141) so pipefail cannot kill the oracle.
ls -1 /app/src/fixtures | { head -10 || true; }
wc -l /app/src/src/lib.rs /app/src/src/main.rs /app/src/src/json.rs \
      /app/src/src/fibonacci.rs /app/src/src/zeckendorf.rs \
      /app/src/src/fibonacci_code.rs /app/src/src/elias_gamma.rs \
      /app/src/src/primes.rs /app/src/src/bracket.rs \
      /app/src/src/wythoff.rs

# ────────────────────────────────────────────────────────────────
# Phase 2 — read the contract. Contracts live under docs/contracts/;
# SPEC.md is a redirect and INCIDENT_LOG.md is narrative addenda.
# ────────────────────────────────────────────────────────────────
echo "== phase 2 : contract =="
ls -1 /app/src/docs/contracts/
sed -n '1,80p'  /app/src/docs/contracts/decomposition.md
sed -n '1,80p'  /app/src/docs/contracts/canonical.md
sed -n '1,80p'  /app/src/docs/contracts/zeckendorf.md
sed -n '1,80p'  /app/src/docs/contracts/prefix_code.md
sed -n '1,80p'  /app/src/docs/contracts/variants.md
sed -n '1,80p'  /app/src/docs/contracts/roundtrip.md
sed -n '1,120p' /app/src/docs/contracts/witnesses.md
sed -n '1,80p'  /app/src/docs/contracts/policy.md
cat /app/config/zeckendorf_policy.json; echo

# ────────────────────────────────────────────────────────────────
# Phase 3 — inspect the raw framed bytes: 4 magic + 8 salt + 1 variant + JSON.
# ────────────────────────────────────────────────────────────────
echo "== phase 3 : fixtures =="
od -An -c -N 24 /app/src/fixtures/fx01.json
od -An -c -N 24 /app/src/fixtures/fx26.json
od -An -c -N 24 /app/src/fixtures/fx25.json
od -An -c -N 24 /app/src/fixtures/fx30.json

# ────────────────────────────────────────────────────────────────
# Phase 4 — confirm the stub compiles but panics; that pins the baseline.
# ────────────────────────────────────────────────────────────────
echo "== phase 4 : baseline =="
cd /app/src
cargo build --release --offline --locked 2>&1 | { tail -3 || true; }
set +e
./target/release/zeckendorf-encode --fixtures /app/src/fixtures --out /tmp/baseline.json 2>&1 | { tail -5 || true; }
set -e

# ────────────────────────────────────────────────────────────────
# Phase 5 — drop in the reference implementation across the five
# per-concern modules plus the trimmed lib.rs.
# ────────────────────────────────────────────────────────────────
echo "== phase 5 : apply =="
cp "$SOLUTION_DIR/lib_fixed.rs"            /app/src/src/lib.rs
cp "$SOLUTION_DIR/bracket_fixed.rs"        /app/src/src/bracket.rs
cp "$SOLUTION_DIR/fibonacci_fixed.rs"      /app/src/src/fibonacci.rs
cp "$SOLUTION_DIR/zeckendorf_fixed.rs"     /app/src/src/zeckendorf.rs
cp "$SOLUTION_DIR/fibonacci_code_fixed.rs" /app/src/src/fibonacci_code.rs
cp "$SOLUTION_DIR/elias_gamma_fixed.rs"    /app/src/src/elias_gamma.rs
cp "$SOLUTION_DIR/primes_fixed.rs"         /app/src/src/primes.rs
cp "$SOLUTION_DIR/wythoff_fixed.rs"        /app/src/src/wythoff.rs
cp "$SOLUTION_DIR/negafibonacci_fixed.rs"  /app/src/src/negafibonacci.rs
cp "$SOLUTION_DIR/pisano_fixed.rs"         /app/src/src/pisano.rs
cargo build --release --offline --locked 2>&1 | { tail -3 || true; }

# ────────────────────────────────────────────────────────────────
# Phase 6 — run the batch driver end-to-end + inspect the invariants.
# ────────────────────────────────────────────────────────────────
echo "== phase 6 : run =="
./target/release/zeckendorf-encode --fixtures /app/src/fixtures --out /app/src/results.json
python3 -c "
import json
d = json.load(open('/app/src/results.json'))
print('chain_sha256      :', d['chain_sha256'])
print('codeword_witness  :', d['codeword_witness'])
print('policy_witness    :', d['policy_witness'])
print('roundtrip_witness :', d['roundtrip_witness'])
print('salt_witness      :', d['salt_witness'])
print('variant_witness   :', d['variant_witness'])
print('wythoff_witness   :', d['wythoff_witness'])
print('witness           :', d['witness'])
print('decoded len       :', len(d['decoded']))
print('first entry       :', d['decoded'][0])
print('last entry        :', d['decoded'][-1])
"

echo "== oracle solve complete =="
