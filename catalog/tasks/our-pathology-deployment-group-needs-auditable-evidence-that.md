# Our pathology deployment group needs auditable evidence that one classifier beha

Submission: `269bc9ec-18f2-4abb-9b46-fb49fcb27c1c`  
Slug: `our-pathology-deployment-group-needs-auditable-evidence-that`  
Latest archive: `269bc9ec-18f2-4abb-9b46-fb49fcb27c1c_submission_2026-07-20T23_46_26.389Z.zip`  
Revisions: 4

## Task summary

Our pathology deployment group needs auditable evidence that one classifier behaves consistently when moved between DJL's PyTorch and ONNX Runtime engines. The Java trial workspace in `/app` is incomplete. Retrieve the immutable model revision named in `/app/config/model-source.properties` with `/app/scripts/fetch_model.sh`; the paired weights are intentionally absent and their live Hugging Face download has no local substitute. Complete the evaluator under `/app/src/main/java` and build it with `/app/scripts/build.sh`. The finished `/app/scripts/run_trial.sh` workflow must:

Required artifacts include: `/app/config/model-source.properties`, `/app/scripts/fetch_model.sh`, `/app/src/main/java`, `/app/scripts/build.sh`, `/app/scripts/run_trial.sh`, `/app/output/parity-report.json`, `/app/docs/trial-contract.md`.

Author anonymous tagged this **hard** machine-learning task (djl, pytorch, onnx-runtime, image-classification).

Time estimates: expert ~300 min, junior ~600 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `269bc9ec-18f2-4abb-9b46-fb49fcb27c1c_submission_2026-07-20T23_46_26.389Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
