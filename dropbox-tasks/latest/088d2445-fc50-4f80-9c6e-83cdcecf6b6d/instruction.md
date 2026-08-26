The satellite crop-stress zonotope audit stack under /app/environment regenerates
/app/output/audit_report.json through the published runner. Default lanes can look
coherent in stage echoes, then the terminal audit drifts under watermark-bound
journal replay and rotation remaps: lane digests and floating-point nest spans
disagree with the stage echo, cold regenerations drift across reruns if stage
residue survives, a warm restart can diverge from the cold baseline, and history
CHK blocks above the watermark (or compaction echoes beside the journal) appear
to drive numerical digests when they should not. Do not hand-write the JSON;
rebuild through the published runner.

/app/environment/tools/hs_run.sh --all-lanes --rotations /app/environment/docs/rot_d.toml

Rebuild with /app/environment/build.sh. Optional env vars include DRV_ROOT,
DRV_OUT, and DRV_BUILD_DIR. The same runner accepts an optional --warm flag. A
warm path must publish the same terminal digests, nest spans, and seals as a
cold regeneration. Read /app/environment/docs/pact_a.md for schema fields
lane_ids, digest_hex, seg_order, script_rows, cite_pairs, nest_span, nest_depth,
alg_keys, run_digest, and rot_arms. Coupling obligations live in
/app/environment/docs/duty_c.md. Stress journal notes live under
/app/environment/data/wal44/. Annex fold notes live under
/app/environment/data/annex44/. Fixture constants for the zonotope generator
matrix and numeric bias scale live in /app/environment/docs/math_b.toml (short
notes in math_b.md). Ledger rows live in /app/environment/data/store_q.sqlite.
Static or hand-written audit_report files are insufficient; outputs are cleared
and regenerated through hs_run.sh for grading. Back-to-back cold regenerations
must keep digest_hex, nest_span, and run_digest stable. Stage summary.json may
carry a status field that reads coherent while the terminal audit is still wrong.
History CHK epochs above the watermark and trailing low-id windows must not drive
digests.
