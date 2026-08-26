#!/usr/bin/env bash
set -euo pipefail
PROBE_ROOT="/opt/verifier-fixtures/b6lc-probes"
ZONE_POLY="${PROBE_ROOT}/zone-poly-window-trap"
BATCH_TRAP="${PROBE_ROOT}/poison-batch-trap"
mkdir -p "${ZONE_POLY}" "${BATCH_TRAP}"
chmod 700 /opt/verifier-fixtures 2>/dev/null || true
chmod 700 "${PROBE_ROOT}" 2>/dev/null || true

cat > "${ZONE_POLY}/conching-window-table.json" <<'JSON'
{
  "windows": [
    {"polymorph": "II", "min_c": 31.0, "max_c": 33.0, "hold_min_s": 200},
    {"polymorph": "V", "min_c": 36.0, "max_c": 38.0, "hold_min_s": 250}
  ],
  "shear_bonus_hz": 4.0
}
JSON

cat > "${BATCH_TRAP}/probe-batch.jsonl" <<'JSONL'
{"batch_id":"TRAP-99","formulation_id":"CPPM-ALPHA","cycle_seq":1,"ts":"2026-06-01T08:00:00Z","temp_c":32.0,"event":"HOLD","shear_hz":5.0,"duration_s":300}
JSONL

ORDER_TRAP="${PROBE_ROOT}/trace-order-trap"
mkdir -p "${ORDER_TRAP}"
# Lexicographic file order presents cycle_seq=2 before cycle_seq=1. Timestamps also
# put cycle 2 earlier. Only batch_id / cycle_seq / ts sorting recovers cycle 1 first.
cat > "${ORDER_TRAP}/a-late-cycle.jsonl" <<'JSONL'
{"batch_id":"ORDER-01","formulation_id":"CPPM-ALPHA","cycle_seq":2,"ts":"2026-06-01T09:00:00Z","temp_c":32.0,"event":"HOLD","shear_hz":5.0,"duration_s":100}
{"batch_id":"ORDER-01","formulation_id":"CPPM-ALPHA","cycle_seq":2,"ts":"2026-06-01T09:05:00Z","temp_c":32.5,"event":"HOLD","shear_hz":5.0,"duration_s":110}
JSONL
cat > "${ORDER_TRAP}/z-early-cycle.jsonl" <<'JSONL'
{"batch_id":"ORDER-01","formulation_id":"CPPM-ALPHA","cycle_seq":1,"ts":"2026-06-01T10:00:00Z","temp_c":37.0,"event":"HOLD","shear_hz":5.0,"duration_s":200}
{"batch_id":"ORDER-01","formulation_id":"CPPM-ALPHA","cycle_seq":1,"ts":"2026-06-01T10:05:00Z","temp_c":37.5,"event":"HOLD","shear_hz":5.0,"duration_s":210}
JSONL

SHEAR_TRAP="${PROBE_ROOT}/shear-bonus-trap"
mkdir -p "${SHEAR_TRAP}"
cat > "${SHEAR_TRAP}/conching-window-table.json" <<'JSON'
{
  "windows": [
    {"polymorph": "II", "min_c": 31.0, "max_c": 33.0, "hold_min_s": 80},
    {"polymorph": "V", "min_c": 36.0, "max_c": 38.0, "hold_min_s": 80}
  ],
  "shear_bonus_hz": 9.0
}
JSON
cat > "${SHEAR_TRAP}/probe-batch.jsonl" <<'JSONL'
{"batch_id":"SHEAR-01","formulation_id":"CPPM-ALPHA","cycle_seq":1,"ts":"2026-06-01T08:00:00Z","temp_c":37.0,"event":"HOLD","shear_hz":5.0,"duration_s":100}
{"batch_id":"SHEAR-01","formulation_id":"CPPM-ALPHA","cycle_seq":2,"ts":"2026-06-01T08:10:00Z","temp_c":32.0,"event":"HOLD","shear_hz":5.0,"duration_s":100}
JSONL

QUENCH_TRAP="${PROBE_ROOT}/quench-scale-trap"
mkdir -p "${QUENCH_TRAP}"
cat > "${QUENCH_TRAP}/formulation-catalog.json" <<'JSON'
{
  "formulations": [
    {
      "formulation_id": "CPPM-ALPHA",
      "display_name": "Quench probe alpha",
      "cocoa_solids_pct": 72.5,
      "fat_pct": 31.0,
      "seed_polymorph": "V",
      "quench_scale": 2.0
    }
  ]
}
JSON
cat > "${QUENCH_TRAP}/conching-window-table.json" <<'JSON'
{
  "windows": [
    {"polymorph": "V", "min_c": 36.0, "max_c": 38.0, "hold_min_s": 80}
  ],
  "shear_bonus_hz": 4.0
}
JSON
cat > "${QUENCH_TRAP}/probe-batch.jsonl" <<'JSONL'
{"batch_id":"QUENCH-01","formulation_id":"CPPM-ALPHA","cycle_seq":1,"ts":"2026-06-01T08:00:00Z","temp_c":37.0,"event":"HOLD","shear_hz":5.0,"duration_s":100}
JSONL

ADJ_TRAP="${PROBE_ROOT}/adjacency-gap-trap"
mkdir -p "${ADJ_TRAP}"
cat > "${ADJ_TRAP}/conching-window-table.json" <<'JSON'
{
  "windows": [
    {"polymorph": "II", "min_c": 31.0, "max_c": 33.0, "hold_min_s": 50},
    {"polymorph": "V", "min_c": 36.0, "max_c": 38.0, "hold_min_s": 50}
  ],
  "shear_bonus_hz": 4.0,
  "adjacency_gap_c": 2.0,
  "adjacency_pair_weight": 0.05
}
JSON
cat > "${ADJ_TRAP}/probe-batch.jsonl" <<'JSONL'
{"batch_id":"ADJ-01","formulation_id":"CPPM-ALPHA","cycle_seq":1,"ts":"2026-06-01T08:00:00Z","temp_c":32.0,"event":"HOLD","shear_hz":5.0,"duration_s":100}
{"batch_id":"ADJ-01","formulation_id":"CPPM-ALPHA","cycle_seq":2,"ts":"2026-06-01T08:10:00Z","temp_c":37.0,"event":"HOLD","shear_hz":5.0,"duration_s":120}
JSONL
