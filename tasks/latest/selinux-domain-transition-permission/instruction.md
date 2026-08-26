# SELinux Domain Transition Permission

The domain-transition lab replays three case batches through a hop-check CLI. After a clean rebuild and pipeline run, the emitted security report shows accepted transitions where policy traps should deny, disagreement between configured, sampled, and live grant masks on the same row, and incorrect accept tags when an identical role label appears under a different pivot key in a later batch.

Replay batches listed in `/app/docs/d8_run_notes.md`, then run `/app/tools/h2_runner` and `/app/tools/q1_emit`. The hop runner writes `/app/var/d8_raw.jsonl` and `/app/var/d8_pivot.jnl`; the emitter writes `/app/output/d8_observations.json` and `/app/var/d8_stamp.txt`. Tests delete generated artifacts, run `make -C /app/environment clean`, rebuild with `make -C /app/environment all -j2`, and rerun both tools. Row and gate digests recompute through `python3 /app/environment/lib/digest_check.py`.

Fix implementation modules under `/app/environment` so the normal pipeline produces a consistent report. Regenerate through the pipeline; hand-written JSON or static edits to generated artifacts are insufficient. Fixture-only edits, hop banner text changes, or replacing `/app/environment/lib/digest_check.py` are insufficient. Do not replace runner tools or edit verifier tests.

The emitted report uses profile `security_authority_split` with gate_digest, per-row case_id, entry_idx, role_text, line_text, gate_code, cfg_mask, sample_mask, live_mask, role_sample, and row_digest fields documented in `/app/docs/d8_contract.md`. Compare raw trace, pivot journal, and observation rows when symptoms diverge across surfaces.
