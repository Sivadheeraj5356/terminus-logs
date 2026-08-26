# Operator duty notes

Default lanes can look coherent in stage summaries while the terminal
`audit_report.json` drifts under journal watermark replay and rotation remaps.
Rebuild through the published runner; do not hand-write `audit_report.json`.

## Coupling obligations

The runner must keep these stages coherent end to end. A local change that
ignores upstream materialization or downstream sealing will still fail grading.

1. Resolve rotation remaps from `rot_d.toml` to a fixpoint (every arm, file order).
2. Materialize live segment bytes and win_seal from the wal44 journal using
   WATERMARK eligibility (see `data/wal44/NOTE.txt`).
3. Fold materialized segments with ledger keys, the remapped fingerprint, and
   win_seal (see `data/annex44/NOTE.txt`).
4. Seal the digest cache to both fingerprint and win_seal before reuse; entries
   that do not match exactly must be ignored and overwritten.
5. Reduce zonotope inclusion under `math_b.toml` generators and `span_order`.
   Bias uses `key_bias_scale * nest_depth * len(fingerprint)` where fingerprint
   is the comma-joined sorted remapped key set. Index `span_order` by output
   dimension, not by nesting level.
6. Emit ledger-bound script bodies and publish `run_digest` over canonical lanes.

## Observed incident symptoms

- Terminal `digest_hex` and `nest_span` disagree with what a green stage echo
  suggests after watermark-bound journal replay.
- Back-to-back cold regenerations drift when a stage digest cache survives.
- Warm restarts diverge from the cold baseline after a poisoned or stale cache.
- History CHK blocks above the watermark, and trailing low-id blocks, appear to
  drive digests when they should not.
- Compaction index echoes retarget materialization away from the live journal.
- Intermediate rotation chain keys remain in `alg_keys`, shifting fingerprint
  length and nest bias together.
- Script bodies are sealed to row ids instead of ledger bind_ref strings.

Stage echoes are not graded. A poison digest cache under stage must not survive
into the terminal audit after a published cold or correctly sealed warm
regeneration.
