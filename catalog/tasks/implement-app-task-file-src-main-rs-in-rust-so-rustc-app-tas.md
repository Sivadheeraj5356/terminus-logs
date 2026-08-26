# Implement `/app/task_file/src/main.rs` in Rust so `rustc /app/task_file/src/main

Submission: `5cb313c2-d974-4dfa-8037-947fd8b51f33`  
Slug: `implement-app-task-file-src-main-rs-in-rust-so-rustc-app-tas`  
Latest archive: `5cb313c2-d974-4dfa-8037-947fd8b51f33_submission_2026-07-19T14_33_32.675Z.zip`  
Revisions: 9

## Task summary

Implement `/app/task_file/src/main.rs` in Rust so `rustc /app/task_file/src/main.rs -O -o /tmp/auditor && /tmp/auditor /app/task_file/input/release.txt /app/task_file/output/report.json` audits offline Sigstore-style release attestations. Input records are whitespace tokens: `KEY id issuer subject not_before not_after trusted`, `IMAGE name digest env tier`, `ATTEST name digest predicate builder key timestamp log_index source_digest`, `LOGROOT log_id root_hash not_before not_after trusted`, `BUNDLE log_index log_id integrated_time tree_size root_hash`, `CHECKPOINT log_id tree_size root_hash prev_root_hash prev_tree_size trusted`, `WITNESS log_id tree_size root_hash key timestamp source_digest trusted`, `WITNESSREQ log_id root_prefix min_count distinct-key|same-key-ok max_age [source_prefix]`, `ROOTPIN env tier log_id root_prefix not_before not_after trusted`, `SPLITVIEW log_id tree_size root_hash trusted`, `BIND builder issuer subject_prefix source_prefix env tier not_before not_after trusted`, `KEYSCOPE key env tier builder source_prefix not_before not_after trusted`, `EMBARGO env tier builder source_prefix start end`, `HOLD env tier builder source_prefix marker_predicate marker_builder marker_issuer marker_source_prefix start end`, `CHAIN env tier predicate builder prev_predicate prev_builder max_delta source_prefix`, `UNIQUE env tier`, `REQUIRE env tier predicate builder issuer max_age min_log hard|warn [subject_prefix] [source_prefix]`, `QUORUM env tier label min_count distinct-key|same-key-ok hard|warn [min_source_groups]`, `MEMBER label predicate builder issuer...

Required artifacts include: `/app/task_file/src/main.rs`, `/app/task_file/input/release.txt`, `/app/task_file/output/report.json`.

Author Anonymous tagged this **hard** security task (sigstore, supply-chain-security, attestation, release-policy, rekor).

Time estimates: expert ~240.0 min, junior ~1080.0 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `5cb313c2-d974-4dfa-8037-947fd8b51f33_submission_2026-07-19T14_33_32.675Z.zip` is a task submission, not a Harbor job. 9 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
