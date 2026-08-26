#!/usr/bin/env bash
# Oracle solve for gaa-extract CLI — implements calibration closure artifacts.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

required_inputs=(
  /app/data/bundled/iv_sweep.csv
  /app/data/bundled/cv_sweep.csv
  /app/data/bundled/geometry_manifest.json
  /app/data/bundled/contact_resistance.json
  /app/config/parameter_bounds.toml
)
for input_path in "${required_inputs[@]}"; do
  test -f "$input_path"
done

install -m 0644 "$ROOT_DIR/files/tb3/src/lab_corpus/mod.rs" /app/tb3/src/lab_corpus/mod.rs
install -m 0644 "$ROOT_DIR/files/tb3/src/calib_seal/rollup_stage.rs" /app/tb3/src/calib_seal/rollup_stage.rs
install -m 0644 "$ROOT_DIR/files/tb3/src/calib_seal/mod.rs" /app/tb3/src/calib_seal/mod.rs
install -m 0644 "$ROOT_DIR/files/tb3/src/calib_seal/seal_tape.rs" /app/tb3/src/calib_seal/seal_tape.rs
install -m 0644 "$ROOT_DIR/files/tb3/src/nsheet_physics/compact_eq.rs" /app/tb3/src/nsheet_physics/compact_eq.rs
install -m 0644 "$ROOT_DIR/files/tb3/src/nsheet_physics/coord_descent.rs" /app/tb3/src/nsheet_physics/coord_descent.rs
install -m 0644 "$ROOT_DIR/files/tb3/src/nsheet_physics/mod.rs" /app/tb3/src/nsheet_physics/mod.rs
install -m 0644 "$ROOT_DIR/files/tb3/src/foundry_card/spice_body.rs" /app/tb3/src/foundry_card/spice_body.rs
install -m 0644 "$ROOT_DIR/files/tb3/src/foundry_card/validation_card.rs" /app/tb3/src/foundry_card/validation_card.rs
install -m 0644 "$ROOT_DIR/files/tb3/src/main.rs" /app/tb3/src/main.rs

cd /app
cargo build --release --locked -p tb3
test -x /app/target/release/gaa-extract
mkdir -p /app/bin /app/state /app/out
install -m 0755 /app/target/release/gaa-extract /app/bin/gaa-extract
test -x /app/bin/gaa-extract

/app/bin/gaa-extract run \
  --data-dir /app/data/bundled \
  --tapeout /app/state/calibration_tapeout.json \
  --bounds /app/config/parameter_bounds.toml \
  --spice /app/out/gaa_model.sp \
  --validation /app/out/model_validation.json

test -s /app/state/calibration_tapeout.json
test -s /app/state/geometry_rollup.json
test -s /app/out/gaa_model.sp
test -s /app/out/model_validation.json
python3 "$ROOT_DIR/run_oracle.py" --verify-only


