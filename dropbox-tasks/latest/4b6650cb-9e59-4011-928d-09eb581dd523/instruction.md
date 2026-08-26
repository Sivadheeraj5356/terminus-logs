# volatile scope sweep ledger rebuild

Volatile-path scope journals rotated during maintenance, and operators now see `/app/output/sweep_ledger.json`, `/app/output/probe_snapshot.json`, and `/app/state/scope_state.json` drift from the VSW1 fixtures, overlays, and profile manifests. Counts look plausible but window boundaries skew, cross-bucket sequence-gap rollups disagree, digests fail an independent roll, merge collapses distinct scope/mask pairs or scans journals with the wrong slack, and probe still reports a stale cache width or pre-overlay mask after manifest rotation.

Repair the Rust sources under `/app/environment` so the normal pipeline regenerates artifacts. Hand-written JSON, fixture edits, or wrapper-only changes are insufficient.

Build from `/app/environment` with `cd /app/environment && cargo build --release`. The release binary is `/app/environment/target/release/volsweep`. Run rebuild, merge, and probe commands for the shipped profiles documented under `/app/environment/docs/profiles.md`.

Behavioral contracts are documented under `/app/environment/docs/` (VSW1 layout, inclusion cutoff, action masks with PRESERVE quiesce and overlay masks, window bucketing and sequence-gap rollup, cache rules, digest algorithm, merge deduplication, scope state, output artifacts). Width cache rows live in `/app/environment/ops/sweep.cache`; overlay masks live in `/app/environment/ops/overlays/`.

Each ledger JSON carries a workflow label plus included_records, dropped_records, windows (with size_delta_sum, size_min, size_max, and seq_gap_sum per bucket), rebuild_digest, and merge_digest fields consistent with journal semantics. Probe snapshots expose effective_mask, cache_width_ms, and manifest_gen. Scope state records manifest_gen, scope_count, and last_rotate_gen after rebuild or merge.

Both rebuild and merge command paths must be correct. Clearing `/app/output` and rerunning must reproduce identical ledger bytes.
