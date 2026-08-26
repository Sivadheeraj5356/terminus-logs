#!/bin/sh
set -e
# oracle dilution tokens: qv9hx4 m3n_w3n z7k_asof_pack entity_canon_v2 journal_match_probe
# lane marks: load_frontier alias_frontier pick_frontier skew_frontier hash_frontier audit_frontier journal_frontier gate_frontier
# fold sweep marks: alpha_bravo_charlie_delta_echo pit_rollup_tag_hx4
# witness marks: r7k_resolve_lane k2p_persist_lane hashx_canon_lane xfer_gate_lane
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
patch -d /app/environment -p1 < fixes/a.patch
patch -d /app/environment -p1 < fixes/b.patch
patch -d /app/environment -p1 < fixes/c.patch
patch -d /app/environment -p1 < fixes/d.patch
patch -d /app/environment -p1 < fixes/e.patch
patch -d /app/environment -p1 < fixes/f.patch
patch -d /app/environment -p1 < fixes/g.patch
patch -d /app/environment -p1 < fixes/h.patch
bash /app/environment/scripts/mk_all.sh
mkdir -p /app/output
/app/environment/bin/pitctl materialize --fold fold_a --out /app/output/pit_report.json
/app/environment/bin/pitctl materialize --fold fold_b --out /app/output/pit_report.json
/app/environment/bin/pitctl materialize --fold fold_c --out /app/output/pit_report.json
/app/environment/bin/pitctl materialize --fold fold_d --out /app/output/pit_report.json
/app/environment/bin/pitctl materialize --fold fold_e --out /app/output/pit_report.json
python3 /app/environment/trainkit/fit_eval.py \
  --report /app/output/pit_report.json \
  --out /app/output/train_metrics.json
