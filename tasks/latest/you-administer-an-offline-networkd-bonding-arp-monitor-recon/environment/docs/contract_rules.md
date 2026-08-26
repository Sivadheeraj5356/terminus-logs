# Contract rules

Same observable policy as `/app/environment/docs/formal_rules.md`. Operator-facing summary:

- Prep then seal (or compile then verify `--hook replay`) with matching `--variant-seed`.
- Outputs: `/app/output/failover_report.json`, `/app/output/runtime_state.json`, `/app/output/arp_journal.jsonl`, `/app/output/run_traces/phase.jsonl`, `/app/output/run_traces/session.journal`.
- Ghost / staging-only peers never become lanes. Report row **order is not required**; lanes are identified by `lane_id`.
- ARP pressure decays once on prep; seal merges with epoch+digest isolation and no second decay.
- **Digest mismatch:** stale or wrong `compile_fp` / `membership_digest` must not settle.
- **Seed mismatch:** prep and seal must share `--variant-seed`; mismatched seeds must not settle as a coherent workflow.
- **Session-journal epochs:** prep advances/writes journal `epoch`; seal keeps that epoch and sets `replay_ack=1` when fingerprints confirm. Journal rewrites replace fields; no duplicate field lines.
- **Lineage ledger:** `/app/environment/meta/lineage.json` persists across output resets. Prep advances `pack_epoch` by one; a settled seal sets `settle_epoch = pack_epoch` and extends the settle chain (`chain_prev`/`chain_bind`/`last_matrix`) per formal rule 5b. Idempotent re-seals leave the chain untouched; a poisoned ledger must not settle until reset to zero lineage.
- **q2m refresh durability:** every driver run restores policy from `/app/environment/q2m/`; recover must still settle.
- **vx_run existence:** `/app/bin/vx_run` (and `build/vx_bond`, `build/bond_probe`) must remain present and executable after rebuild.
- Probe settled iff `sync_label=settled` and some `img_rc` is 1.
- Seal bindings replace in place; no duplicate lane keys across reruns.

Weight and permutation inputs live under `/app/environment/data/bump_tbl.toml`, `/app/environment/data/perm_tbl.toml`, and `/app/environment/data/rank_tbl.toml`. The `triple` used in **both** `compile_fp` and `facet_hex` is the `rank_tbl.toml` entry for the current `--variant-seed` (identical lookup for both formulas).
