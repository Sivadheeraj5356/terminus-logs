# The annex-39 JWT lab under /app/environment builds witnesses that look fine on s

Submission: `b3b1041b-59ad-4e1e-87aa-46f898bb2d8e`  
Slug: `the-annex-39-jwt-lab-under-app-environment-builds-witnesses`  
Latest archive: `b3b1041b-59ad-4e1e-87aa-46f898bb2d8e_submission_2026-07-16T11_41_41.824Z.zip`  
Revisions: 1

## Task summary

The annex-39 JWT lab under /app/environment builds witnesses that look fine on smoke instances, but independent certificate replay fails on the same tokens under finite context. Infer a specification consistent with the observable traces and repair Ruby module sources under /app/environment so library and module-level behavior is correct, not only checker CLI output. Static or hand-written /app/output artifacts are insufficient; the normal build_lab.sh plus k9_verify pipeline must regenerate graded outputs. Edits without rebuild, or test changes, do not count. Success means /app/environment/tools/k9_verify exits 0 for grids pocket, ridge, slate, and marsh under profiles pri_hi and pri_lo, writing /app/output/replay_witness.json and /app/output/inferred_spec.json. Graded cells include grid, profile, rows (tid, kid, plan, gate, e_tag), meta_state (aligned on metamorphic remap agreement, otherwise diverged), instance_digest, eff_keys, and cfg_fp. Corpus and rotation inputs live at /app/environment/data/p39/batch.jsonl and /app/environment/data/p39/rot.log; scenarios under /app/environment/scenarios (including /app/environment/scenarios/pocket.json) supply base_cfg, overlay, and token ids such as p01, s01, s02, m01, m02, and r02. Graded ok rows must not use kid k_root or any kid starting with k_evil. Pollution keys such as __p and x_def must be absent from eff_keys (intersection with those banned keys is false). Digest and fingerprint formulas, pollution-key exclusions, epoch allow/rev tables, inferred_spec clauses (schema k84-spec-v1 with fields aid, kind, and note,...

Required artifacts include: `/app/environment`, `/app/output`, `/app/environment/tools/k9_verify`, `/app/output/replay_witness.json`, `/app/output/inferred_spec.json`, `/app/environment/data/p39/batch.jsonl`, `/app/environment/data/p39/rot.log`, `/app/environment/scenarios`.

Author anonymous tagged this **hard** security task (security, jwt, jwk, witness, replay, spec-inference).

Time estimates: expert ~120 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `b3b1041b-59ad-4e1e-87aa-46f898bb2d8e_submission_2026-07-16T11_41_41.824Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
