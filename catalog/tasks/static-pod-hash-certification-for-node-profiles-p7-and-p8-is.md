# Static-pod hash certification for node profiles p7 and p8 is broken. Repair the 

Submission: `ec9aaa9c-66c5-4adc-9656-d68fc126b85f`  
Slug: `static-pod-hash-certification-for-node-profiles-p7-and-p8-is`  
Latest archive: `ec9aaa9c-66c5-4adc-9656-d68fc126b85f_submission_2026-07-18T08_19_03.317Z.zip`  
Revisions: 2

## Task summary

Static-pod hash certification for node profiles p7 and p8 is broken. Repair the watcher sources under `/app/environment` so the normal pipeline regenerates `/app/output/feasibility_certificate.json` with no violations. Matrix traversal is sorted set filename, source item order, then p7 followed by p8. Unit tags contain all sorted label tokens, including arbitrary keys such as rollout; annex-enabled profiles also contain only annotations matching the configured annex prefix in the configured relative order. Every emission contributes one newline-terminated GEN=<n>|BAND=<band>|BODY=<tokens> frame and a trailing rev=<n> tag token with the same contiguous generation. Repeated manifest IDs continue their prior generations rather than resetting. Journal lineage is byte-sensitive: each complete line, including its newline, is hashed separately and those line hashes form the journal tip chain; a whole-file hash is not equivalent. The digest uses the pre-append tip as parent_tip, while the certificate uses the post-append tip. Namespace and profile scope participate in the digest. Seal windows depend on set stems, seal selection includes GEN, and cache epochs differ across transitions in annex participation or seal window. A valid recovery keeps every contiguous complete frame, excludes a torn non-newline tail, and excludes the suffix from the first malformed or skipped GEN. Per-manifest *.kv cache files retain annex, window, and epoch state in ANNEX_LAST=, WINDOW_LAST=, and epoch lines. Each certificate row contains manifest_id, canonical_byte_digest, unit_tag, scope_band,...

Required artifacts include: `/app/environment`, `/app/output/feasibility_certificate.json`, `/app/environment/docs/layout_spec.md`, `/app/environment/docs/stage_rules.md`, `/app/environment/docs/tip_chain.md`, `/app/environment/docs/seal_windows.md`, `/app/environment/docs/recovery.md`, `/app/environment/fixtures/slices/q46.txt`.

Author anonymous tagged this **hard** system-administration task (system-administration, kubelet, static-pod, journal-recovery, config-policy, node-profiles).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1200s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `ec9aaa9c-66c5-4adc-9656-d68fc126b85f_submission_2026-07-18T08_19_03.317Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
