Tower defense live-ops wants a trustworthy wave-balancer certificate for published pressure.

Do not hand-author `/app/output/feasibility_cert.json`.

Repair the Java under `/app/environment` so `/app/environment/drv/run_td.sh` regenerates it.

From `/app`, run `/app/environment/drv/run_td.sh`.

Cover every pack under `/app/environment/data/m9` and every stress pack under `/app/environment/data/z2`.

Rows must include map_id, wave_index, spawn_hex, pressure_score, leftover_budget, and leak_margin, plus top-level seal_hex as 64 lowercase hex chars.

Read hard caps in `/app/environment/pol/cap.toml` and soft floors in `/app/environment/pol/q_floor.json`.

Packing detail lives in `/app/environment/docs/abi_notes.md`.

Each pack directory ships bag.json and meta.json.

Bag field order may shuffle between presentations; pressure_score, leak_margin, leftover_budget, and seal_hex must stay identical. Maximize pressure_score under budget without exits. Seeded reruns must match. Offline only.
