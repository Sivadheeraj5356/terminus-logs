# Build a Go program reading /app/chunk_inbox NDJSON shards and writing /app/outpu

Submission: `a1135886-b3ce-495d-a9a8-6da04959ce8f`  
Slug: `build-a-go-program-reading-app-chunk-inbox-ndjson-shards-and`  
Latest archive: `a1135886-b3ce-495d-a9a8-6da04959ce8f_submission_2026-07-09T15_56_50.686Z (1).zip`  
Revisions in Dropbox: 2

## Task summary

Build a Go program reading /app/chunk_inbox NDJSON shards and writing /app/output/expected.json. Envelope: chunk_id, tenant_id, object_id, chunk_offset, size_bytes, hash, content_fingerprint, algorithm, refcount, registered_ts, tier, seal. Optional: force_admit, force_reject, schema_version, op. Tables in /app/dedup_arena, /app/hash_codec, /app/tier_dialer, /app/quarantine_cell, /app/cycle_witness, /app/tenant_oracle, /app/object_graph. The JSON has four top-level keys. chunks holds rows of chunk_id, object_id, registered_ts_ns, size_bytes, tenant_id, verdict, sorted by verdict severity descending then chunk_id ascending. Nineteen closed verdicts in severity order: VOIDED, REJECTED_CONTRADICTORY, INVALID, REJECTED_TYPE, REJECTED_SEAL, REJECTED_REPLAY, SCHEMA_DRIFT_QUARANTINED, QUARANTINED_TENANT, REJECTED_COLLISION, REJECTED_WEAK_HASH, REJECTED_DUPLICATE, DEFERRED_STALE, DEFERRED_COOLDOWN, DEFERRED_REHASH, DEFERRED_HOT, DEFERRED_BANDWIDTH, DEFERRED_RESERVED_OUT, DEHYDRATED, KEPT_CANONICAL. by_verdict zero-fills. by_tenant has one block per tenant in /app/tenant_oracle/tenant_map.psv with chunk_count (INVALID excluded), bytes_kept_canonical, bytes_dehydrated, top_verdict. summary holds total_chunks, run_ts_ns, bytes_kept_canonical, bytes_dehydrated, report_digest. /app/cycle_witness/output_contract.json pins types, digest formula, policy parameters.

Required artifacts include: `/app/chunk_inbox`, `/app/output/expected.json`, `/app/dedup_arena`, `/app/hash_codec`, `/app/tier_dialer`, `/app/quarantine_cell`, `/app/cycle_witness`, `/app/tenant_oracle`.

Author anonymous tagged this **hard** data-processing task (dedup, content-addressed, chunk-store, verdict-cascade, quarantine, tier-policy).

Time estimates: expert ~165.0 min, junior ~360.0 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `a1135886-b3ce-495d-a9a8-6da04959ce8f_submission_2026-07-09T15_56_50.686Z (1).zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
