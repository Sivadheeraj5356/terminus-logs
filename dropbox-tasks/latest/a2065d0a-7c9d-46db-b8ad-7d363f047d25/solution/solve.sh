#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/cargo/bin:/opt/verifier-venv/bin:/usr/local/bin:${PATH}"
export CARGO_NET_OFFLINE=true
cd /app
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOL=""
for candidate in "${SCRIPT_DIR}/files" "${SCRIPT_DIR}" "/solution/files" "/solution" "/oracle/solution"; do
  if [ -f "${candidate}/golden_corpus.rs" ]; then SOL="${candidate}"; break; fi
done
[[ -n "${SOL}" ]] || { echo "golden modules not found" >&2; exit 1; }
for module in corpus vocab rng sampler ledger retention ranking publication; do
  mkdir -p "/app/crates/ldacore/src/${module}"
  cp -f "${SOL}/golden_${module}.rs" "/app/crates/ldacore/src/${module}/mod.rs"
done
cargo build --offline --release --locked -p ldactl
install -m 0755 /app/target/release/ldactl /usr/local/bin/ldactl
bash /app/scripts/reset-state.sh
