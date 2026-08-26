#!/bin/bash
# Sealed BGR1 memfd oracle. Does not modify the 34 application sources, the
# ordinary compiled application, contracts, tests, or the embedded flawed capsule.
set -euo pipefail

SOLUTION_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_BIN="/app/rust_unitgraph_cells/reconcile_boot_graph"
LAUNCHER="/app/boot_recovery_console/reconcile_boot_graph.sh"
ORACLE_DIR="/opt/unitgraph_bgr1_oracle"
EXPECTED_HASH_FILE="${SOLUTION_DIR}/expected_bgr1_capsule.sha256"
ATOMS="${SOLUTION_DIR}/corrected_rule_atoms"
LEXICON="${SOLUTION_DIR}/boot_rule_lexicon.tsv"
CUSTODY="${SOLUTION_DIR}/rule_capsule_custody.tsv"

mkdir -p "${ORACLE_DIR}"

sha256() { sha256sum "$1" | awk '{print $1}'; }

# Idempotence: matching installed oracle launcher is a no-op.
if [[ -f "${ORACLE_DIR}/oracle_boot_rules.bgr1" && -f "${ORACLE_DIR}/sealed_rule_memfd_courier" ]]; then
  if grep -q 'sealed_rule_memfd_courier' "${LAUNCHER}" 2>/dev/null; then
    got="$(sha256 "${ORACLE_DIR}/oracle_boot_rules.bgr1")"
    exp="$(tr -d ' \n' < "${EXPECTED_HASH_FILE}")"
    if [[ "${got}" == "${exp}" ]]; then
      echo "unitgraph oracle: sealed capsule already installed"
      exit 0
    fi
  fi
fi

test -x "${APP_BIN}"
test -f "${LAUNCHER}"
test -d "${ATOMS}"
test -f "${LEXICON}"
test -f "${EXPECTED_HASH_FILE}"

STAGE1="$(mktemp -d /tmp/bgr1_stage1.XXXXXX)"
STAGE2="$(mktemp -d /tmp/bgr1_stage2.XXXXXX)"
cleanup() { rm -rf "${STAGE1}" "${STAGE2}"; }
trap cleanup EXIT

# Build forge twice under distinct absolute roots.
rustc --edition 2021 -O -o "${STAGE1}/bgr1_capsule_forge" "${SOLUTION_DIR}/bgr1_capsule_forge.rs"
rustc --edition 2021 -O -o "${STAGE2}/bgr1_capsule_forge" "${SOLUTION_DIR}/bgr1_capsule_forge.rs"
cmp -s "${STAGE1}/bgr1_capsule_forge" "${STAGE2}/bgr1_capsule_forge"

"${STAGE1}/bgr1_capsule_forge" "${ATOMS}" "${LEXICON}" "${STAGE1}/oracle_boot_rules.bgr1"
"${STAGE2}/bgr1_capsule_forge" "${ATOMS}" "${LEXICON}" "${STAGE2}/oracle_boot_rules.bgr1"
cmp -s "${STAGE1}/oracle_boot_rules.bgr1" "${STAGE2}/oracle_boot_rules.bgr1"

got="$(sha256 "${STAGE1}/oracle_boot_rules.bgr1")"
exp="$(tr -d ' \n' < "${EXPECTED_HASH_FILE}")"
if [[ "${got}" != "${exp}" ]]; then
  echo "unitgraph oracle: capsule hash mismatch" >&2
  echo "got=${got}" >&2
  echo "exp=${exp}" >&2
  exit 1
fi

# Build courier twice.
rustc --edition 2021 -O -o "${STAGE1}/sealed_rule_memfd_courier" "${SOLUTION_DIR}/sealed_rule_memfd_courier.rs"
rustc --edition 2021 -O -o "${STAGE2}/sealed_rule_memfd_courier" "${SOLUTION_DIR}/sealed_rule_memfd_courier.rs"
cmp -s "${STAGE1}/sealed_rule_memfd_courier" "${STAGE2}/sealed_rule_memfd_courier"

# Static inspection: courier must reference memfd sealing symbols and not embed yard paths.
strings_out="$(strings "${STAGE1}/sealed_rule_memfd_courier")"
case "${strings_out}" in
  *memfd_create*) ;;
  *)
    echo "unitgraph oracle: courier missing memfd strings" >&2
    exit 1
    ;;
esac
case "${strings_out}" in
  *.bootyard*)
    echo "unitgraph oracle: courier contains forbidden paths" >&2
    exit 1
    ;;
esac

install -m 0755 "${STAGE1}/sealed_rule_memfd_courier" "${ORACLE_DIR}/sealed_rule_memfd_courier"
install -m 0644 "${STAGE1}/oracle_boot_rules.bgr1" "${ORACLE_DIR}/oracle_boot_rules.bgr1"
install -m 0644 "${EXPECTED_HASH_FILE}" "${ORACLE_DIR}/expected_bgr1_capsule.sha256"
install -m 0644 "${STAGE1}/bgr1_capsule_forge" "${ORACLE_DIR}/bgr1_capsule_forge" 2>/dev/null || true

# Atomically replace only the public launcher with a hash-gated courier invocation.
tmp_launcher="$(mktemp /tmp/reconcile_boot_graph.sh.XXXXXX)"
cat > "${tmp_launcher}" <<'EOF'
#!/bin/bash
set -euo pipefail
CAPSULE="/opt/unitgraph_bgr1_oracle/oracle_boot_rules.bgr1"
COURIER="/opt/unitgraph_bgr1_oracle/sealed_rule_memfd_courier"
APP="/app/rust_unitgraph_cells/reconcile_boot_graph"
HASHFILE="/opt/unitgraph_bgr1_oracle/expected_bgr1_capsule.sha256"
exp=$(tr -d ' \n' < "${HASHFILE}")
got=$(sha256sum "${CAPSULE}" | awk '{print $1}')
if [[ "${got}" != "${exp}" ]]; then
  echo "unitgraph error 10: capsule custody" >&2
  exit 10
fi
exec "${COURIER}" "${APP}" "${CAPSULE}" "$@"
EOF
chmod 0755 "${tmp_launcher}"
mv -f "${tmp_launcher}" "${LAUNCHER}"

# Refresh custody roster fingerprints for installed artifacts.
{
  echo "key	value"
  echo "app_bin_sha256	$(sha256 "${APP_BIN}")"
  echo "launcher_sha256	$(sha256 "${LAUNCHER}")"
  echo "capsule_sha256	${got}"
  echo "courier_sha256	$(sha256 "${ORACLE_DIR}/sealed_rule_memfd_courier")"
  echo "forge_sha256	$(sha256 "${STAGE1}/bgr1_capsule_forge")"
  echo "rustc	$(rustc --version | tr ' ' '_')"
  echo "expected_capsule	${exp}"
} > "${ORACLE_DIR}/install_custody.tsv"

# Optional local custody file update is not required for runtime.
if [[ -f "${CUSTODY}" ]]; then
  :
fi

echo "unitgraph oracle: sealed BGR1 courier installed"
