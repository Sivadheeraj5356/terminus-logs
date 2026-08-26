# Architecture

`mode_seal` is a sealed FEM eigenmode proof engine. It reads numerical authorities under `data/num_auth`, live and shadow annex bands under `data/bands_live` and `data/bands_shadow`, peel timing under `data/tb_state`, stress fixtures under `data/fixtures`, runtime controls under `data/qv7_ctl`, and a crash-resume store under `data/ms_store` (tip, `seal.bind`, WAL). The emitted artifact is `/app/output/invariant_proof_log.json`.

Entry point: `/app/scripts/proof_run.sh` builds `bin/mode_seal` if needed and invokes the seal against `/app`.
