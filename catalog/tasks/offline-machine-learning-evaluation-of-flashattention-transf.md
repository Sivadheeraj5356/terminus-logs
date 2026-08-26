# Offline machine-learning evaluation of FlashAttention transformer inference: cal

Submission: `9323bb30-2b2c-4857-aa46-4c8ba0fdeaa1`  
Slug: `offline-machine-learning-evaluation-of-flashattention-transf`  
Latest archive: `9323bb30-2b2c-4857-aa46-4c8ba0fdeaa1_submission_2026-07-15T09_23_39.020Z.zip`  
Revisions: 10

## Task summary

Offline machine-learning evaluation of FlashAttention transformer inference: calibrate Q/K/V tile geometry from the attention model profile at /app/config/attn-profile.json onto the paged KV-cache, track online-softmax logit features under the quantized sparse-mask graph from packs under /app/fixtures/public/, and grade the attention path into an offline residency seal. Keep the evaluator offline with no network listeners. Deliverables are native ELF binaries at /app/bin/kvtile-plan, /app/bin/kvtile-advance, and /app/bin/kvtile-seal (not script wrappers). Normative contracts (required): /app/docs/behavior-register.md, /app/docs/tile-schedule-contract.md, /app/docs/online-softmax-contract.md, /app/docs/block-table-contract.md, /app/docs/sparse-mask-contract.md, /app/docs/residency-seal-schema.md, /app/docs/module-scope.md, /app/docs/cli-reference.md, /app/docs/runtime-env.md. Seal JSON at /app/output/kvtile-residency-seal.json must write keys in exact order seq_id, run_epoch, tiles_planned, pages_resident, mask_bits, m_stats, ell_stats, seal_digest. seal_digest is the lowercase SHA-256 hex of the UTF-8 pipe string (no trailing newline) whose field order is defined in residency-seal-schema.md (including prior_fold, compact_gen, visit_checksum, merkle_tip, compiler_epoch, rebuild_nonce, schedule_crc from /app/data/schedule.mir, and residue_u64). visit_checksum, spine tip folding, spine_trailer.hex, prior_fold / prior_seal.hex, and build.sh versus rebuild.sh compiler-epoch.json rules are normative in that schema and cli-reference.md. Candidate binaries must not read...

Required artifacts include: `/app/config/attn-profile.json`, `/app/fixtures/public/`, `/app/bin/kvtile-plan`, `/app/bin/kvtile-advance`, `/app/bin/kvtile-seal`, `/app/docs/behavior-register.md`, `/app/docs/tile-schedule-contract.md`, `/app/docs/online-softmax-contract.md`.

Author anonymous tagged this **hard** machine-learning task (rust, flashattention, kv-cache, inference, softmax).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `9323bb30-2b2c-4857-aa46-4c8ba0fdeaa1_submission_2026-07-15T09_23_39.020Z.zip` is a task submission, not a Harbor job. 10 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
