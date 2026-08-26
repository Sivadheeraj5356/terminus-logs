# Our Ruby quantization lab under `/app/environment` calibrates activation tensors

Submission: `a36f4d17-6dc8-4905-bcd8-78178bd1a0af`  
Slug: `our-ruby-quantization-lab-under-app-environment-calibrates-a`  
Latest archive: `a36f4d17-6dc8-4905-bcd8-78178bd1a0af_submission_2026-07-17T04_40_23.211Z.zip`  
Revisions in Dropbox: 1

## Task summary

Our Ruby quantization lab under `/app/environment` calibrates activation tensors into exportable scale buckets for offline inference bundles. After the last ops refresh, scale rows for `sage` look right in the staging report, but the terminal ledger from the matrix driver disagrees on row digests between live batch accumulation and replayed checkpoint bytes for the same seeded inputs. The built-in calibration profile ids are exactly `fp16_baseline`, `int8_strict`, and `mixed_edge`; do not rename them or substitute case ids as mode ids. Per-profile activation statistics must never bleed across incompatible profiles named in `/app/environment/docs/qcl_contract.md`. Statistics are computed from mode-clipped activation values, not raw tensor extrema, so different mode bounds can change `stat_min` and `stat_max` for the same case. Documented clipping bounds apply before rounding and bucket assignment, not after. Mixed-precision variants must reconcile every layer row independently using the per-layer scale derivation in the contract, including the documented `layer_id` byte-sum offset and dynamic-profile scale branch in `scale_u32`.

Required artifacts include: `/app/environment`, `/app/environment/docs/qcl_contract.md`, `/app/output/qcl_emit.json`, `/app/environment/docs/case_ids.txt`, `/app/environment/f5/scratch_arena.rb`, `/app/environment/docs/operators.md`, `/app/environment/h5/w1/`, `/app/environment/h5/pool/QZ-*.json`.

Author anonymous tagged this **hard** machine-learning task (machine-learning, ruby, quantization, calibration, int8, mixed-precision).

Time estimates: expert ~120 min, junior ~360 min.

Harbor timeouts: agent 900s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `a36f4d17-6dc8-4905-bcd8-78178bd1a0af_submission_2026-07-17T04_40_23.211Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
