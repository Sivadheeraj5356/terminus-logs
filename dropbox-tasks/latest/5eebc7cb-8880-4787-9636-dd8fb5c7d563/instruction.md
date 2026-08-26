fxctl under `/app/environment` finishes the parquet column encryption metadata desk.

The desk reads encrypted column blobs from `/app/environment/payload/`, resolves lane authority and column-key epochs from the durable ring at `/app/environment/payload/ring_seg.bin`, unwraps segment bytes with per-group AAD plus key material, and writes `/app/output/sync_record.json`.

Build with `make -C /app/environment`. Run catalog ids from `/app/environment/payload/cases.json` through seal, verify, and append using `/app/environment/docs/runbook.md`.

Graded sync_record.json must carry run_meta (case_id, phase, seq), bind_rows, optional cross_aad_digest, part_sig only for catalog ids r2, f7, and b2 on verify, and record_digest as defined in `/app/environment/docs/footer_contract.md`.

Ring projection, authority merge, bind row rules, AAD rotation, slice context, trailer store policy, and remaining field rules live in that footer contract. JSON must validate against `/app/environment/contracts/sync_record.schema.json` and `/app/environment/contracts/sync_record_contract.json`.

Multi-component binding across the ring, lane authority, AAD rotation, chunk unwrap, and digest assembly must agree. Append must clear stale trailer store entries before verify reread. Consecutive verify runs must replay bit-stable sync records.

Update Go sources under `/app/environment` so rebuilt fxctl regenerates `/app/output/sync_record.json` through the normal ingestion path. Package-level and library-level behavior under `/app/environment` must be correct, not only CLI wrapper wiring.

fxctl must match footer_contract.md end to end. Static or manual output writes are insufficient. Hand-written JSON, `/app/environment/tools/peek` preview stdout, or fx_expect alone will not pass.
