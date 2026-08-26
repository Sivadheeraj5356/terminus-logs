# Architecture

Offline snapper timeline replay lab under `/app/environment`. Fragment units `u0_a` through `u3_d` implement checkpoint stamping, WAL folding, label/list/recycle binding, and mount voting (`u0_a/warm_gate.sh`, `u1_b/wal_fold.sh`, `u2_c/label_lane.sh`, `u2_c/list_lane.sh`, `u2_c/recycle_lane.sh`, `u3_d/vote_lane.sh`). The `snaplab/scenario_driver.sh` driver replays catalog profiles in replay-order sequence; `hrun/journal_lane.sh` maintains handoff journal carry-forward under `/app/state/handoff`.

Pipeline entrypoints: `scripts/build.sh` (noop warm-up), `scripts/replay_exec.sh`, and `scripts/emit_exec.sh`. Catalog and policy inputs live in `config/scenario_catalog.toml`, `config/resume_policy.toml`, and `config/view_policy.toml`. Trace bundles are under `traces/` (for example `traces/journal_batch.trace`); ledger snapshots under `ledgers/` (for example `ledgers/gen-003.snapshot.json`). Replay writes per-scenario material files such as `journal_batch.json` and `catalog_c.json` under `/app/svc-state/replay_material`, with checkpoint stamp `/app/svc-state/checkpoint/epoch.json`. Seeded warm-lane drift fixtures ship in `svc-state-seed/replay_material` and `svc-state-seed/checkpoint/epoch.json`.

Behavioral precedence lives in `docs/precedence_notes.md`. Output schema and digests are in `docs/resume_contract.md`.
