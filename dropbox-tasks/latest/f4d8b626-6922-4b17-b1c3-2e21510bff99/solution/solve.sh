#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/app}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILES="${SCRIPT_DIR}/files"

export PATH="/usr/local/cargo/bin:${PATH}"
export CARGO_INCREMENTAL=0

# Oracle: refresh lane arbitration, feature timeline, and atlas digest modules.
install_oracle_modules() {
  local src="$1"
  local dst="$2"
  mkdir -p "${dst}"
  cp -R "${src}/." "${dst}/"
}

cp "${FILES}/Cargo.toml" "${APP_ROOT}/Cargo.toml"
install_oracle_modules "${FILES}/src" "${APP_ROOT}/src"

cd "${APP_ROOT}"
cargo build --release --locked
test -x "${APP_ROOT}/target/release/expeditctl"
