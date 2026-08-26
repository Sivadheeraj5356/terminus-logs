#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="${ROOT_DIR}/oracle_modules"
mkdir -p /app/output/reports /app/state
cd /app

install -m 644 "${SRC}/fdtd_op_a.cpp" /app/environment/lib/op_a.cpp
install -m 644 "${SRC}/fdtd_step_c.cpp" /app/environment/src/step_c.cpp
install -m 644 "${SRC}/fdtd_emit_d.cpp" /app/environment/src/emit_d.cpp
install -m 644 "${SRC}/fdtd_stage_mesh.cpp" /app/environment/mesh/stage_mesh.cpp
install -m 644 "${SRC}/fdtd_reconcile_b.cpp" /app/environment/lib/reconcile_b.cpp

if [ ! -f /app/environment/Makefile ]; then
    echo "missing /app/environment/Makefile" >&2
    exit 1
fi

bash -lc 'make -C /app/environment clean && make -C /app/environment'

if [ ! -x /app/bin/reso_sim ]; then
    echo "reso_sim missing after rebuild" >&2
    exit 1
fi

/app/bin/reso_sim batch --ct /app/data/ct --out /app/output/reports

for profile in amati_ct guarneri_ct; do
    if [ ! -f "/app/output/reports/${profile}/formants.json" ]; then
        echo "missing formants.json for ${profile}" >&2
        exit 1
    fi
    if [ ! -f "/app/output/reports/${profile}/pressure.wav" ]; then
        echo "missing pressure.wav for ${profile}" >&2
        exit 1
    fi
    if [ ! -f "/app/state/${profile}/cavity_mesh.json" ]; then
        echo "missing cavity_mesh.json for ${profile}" >&2
        exit 1
    fi
done

if [ ! -f /app/output/reports/summary.json ]; then
    echo "missing summary.json after batch" >&2
    exit 1
fi
