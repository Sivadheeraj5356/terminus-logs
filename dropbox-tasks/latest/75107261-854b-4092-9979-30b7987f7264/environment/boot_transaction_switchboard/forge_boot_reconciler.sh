#!/bin/bash
# Authenticate the explicit Rust unit roster, compile with pinned rustc, install
# cells and contracts, and create the public administrator launcher.
set -euo pipefail

SRC_ROOT="${1:-/opt/boot_transaction_switchboard}"
APP_CELLS="/app/rust_unitgraph_cells"
APP_CONTRACTS="/app/systemd_boot_contracts"
CONSOLE="/app/boot_recovery_console"
BIN="${APP_CELLS}/reconcile_boot_graph"

UNIT_ROSTER=(
  reconcile_portal.rs
  bootyard_boundary.rs
  yard_inventory.rs
  order_reader.rs
  logical_seal.rs
  unit_name_codec.rs
  fragment_locator.rs
  unit_parser.rs
  dropin_merger.rs
  specifier_expander.rs
  install_graph.rs
  preset_resolver.rs
  alias_mask_state.rs
  dependency_graph.rs
  transaction_builder.rs
  cycle_witness.rs
  mount_unit_codec.rs
  device_alias_resolver.rs
  condition_evaluator.rs
  job_state_machine.rs
  boot_target_simulator.rs
  expected_job_checker.rs
  mutation_journal.rs
  unit_file_writer.rs
  symlink_custodian.rs
  generation_guard.rs
  cold_boot_replayer.rs
  effective_unit_ledger.rs
  boot_trace_writer.rs
  boot_accord_sealer.rs
  diagnostic_surface.rs
  boot_semantics.rs
  embedded_boot_semantics.rs
  reconcile_failure.rs
)

CONTRACT_ROSTER=(
  bootyard_custody_generation_protocol.md
  unit_fragment_precedence_contract.md
  specifier_instance_escape_register.md
  enablement_mask_preset_law.md
  dependency_job_transaction_code.md
  mount_automount_device_readiness.md
  condition_assert_outcome_rules.md
  cold_boot_evidence_receipt.md
)

CELLS_SRC="${SRC_ROOT}/rust_unitgraph_cells"
CONTRACTS_SRC="${SRC_ROOT}/systemd_boot_contracts"

test -d "${CELLS_SRC}"
test -d "${CONTRACTS_SRC}"

for u in "${UNIT_ROSTER[@]}"; do
  test -f "${CELLS_SRC}/${u}"
done
for c in "${CONTRACT_ROSTER[@]}"; do
  test -f "${CONTRACTS_SRC}/${c}"
done
test "${#UNIT_ROSTER[@]}" -eq 34
test "${#CONTRACT_ROSTER[@]}" -eq 8

BUILD="$(mktemp -d /tmp/unitgraph_build.XXXXXX)"
cleanup() { rm -rf "${BUILD}"; }
trap cleanup EXIT

cp -a "${CELLS_SRC}/." "${BUILD}/"
cd "${BUILD}"

# Compile the portal as a single binary; path attributes pull in the other units.
rustc --edition 2021 -O -o reconcile_boot_graph reconcile_portal.rs

install -d -m 0755 "${APP_CELLS}" "${APP_CONTRACTS}" "${CONSOLE}"
install -m 0644 "${CELLS_SRC}/"* "${APP_CELLS}/"
install -m 0644 "${CONTRACTS_SRC}/"* "${APP_CONTRACTS}/"
install -m 0755 "${BUILD}/reconcile_boot_graph" "${BIN}"

cat > "${CONSOLE}/reconcile_boot_graph.sh" <<'EOF'
#!/bin/bash
set -euo pipefail
exec /app/rust_unitgraph_cells/reconcile_boot_graph "$@"
EOF
chmod 0755 "${CONSOLE}/reconcile_boot_graph.sh"

# Contracts stay read-only; application sources remain writable so repairs can be rebuilt.
chmod -R a-w "${APP_CONTRACTS}" || true
# Keep a rebuild helper next to the public console.
install -m 0755 "${SRC_ROOT}/forge_boot_reconciler.sh" "${CONSOLE}/rebuild_from_switchboard.sh" || true
