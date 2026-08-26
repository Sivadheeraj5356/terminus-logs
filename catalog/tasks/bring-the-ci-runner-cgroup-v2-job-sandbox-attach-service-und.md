# Bring the CI runner cgroup v2 job-sandbox attach service under `/app/environment

Submission: `4e8a157c-e3d3-44d0-bb7d-600de063f6fd`  
Slug: `bring-the-ci-runner-cgroup-v2-job-sandbox-attach-service-und`  
Latest archive: `4e8a157c-e3d3-44d0-bb7d-600de063f6fd_submission_2026-07-19T17_36_05.769Z.zip`  
Revisions in Dropbox: 1

## Task summary

Bring the CI runner cgroup v2 job-sandbox attach service under `/app/environment` back into operational compliance for nesting policy. Follow the documented procedure: build with `/app/environment/k4m/build_wrap.sh /app/environment /app/bin/cg_xmit`, then rematerialize `/app/output/protocol_transcript.json` with `/app/bin/cg_xmit` from the pinned hierarchy annex and the nesting arm catalog. Hierarchy migrate packing, durable controller claim, nest handshake combine, and transcript emit must stay synchronized so the attach pipeline rematerializes a coherent operational artifact. A static transcript file is not an accepted substitute for the build_wrap plus `cg_xmit run` rematerialization path; static or manual output writes are insufficient, including hand-placed latch journal or accept stamp files under `/app/environment/engine/seg_v`. Offline container, no network. After controller grants fold through handshake nonces, closed fixture algebra stays at zero violations across held-out nesting arms, and residual bands stay inside the fixture 49 tolerance policy under leftover-parent-procs cutoffs, nested-rebind boundary cutoffs, and shallow-versus-deep nesting swaps. Fixture id is 49. Annex is `/app/environment/fixtures/fx_h49.jsonl`. Arm table is `/app/environment/fixtures/arm_tbl.toml` (including held-out arms). Formal identities, row/summary field contracts, CLI argv, residual band rules, durable latch journal authority, durable `.seg` grammar, combine-stage ownership, temporal arm chaining, and accept-stamp lifecycle live in `/app/environment/docs/pact_r8.md`,...

Required artifacts include: `/app/environment`, `/app/environment/k4m/build_wrap.sh`, `/app/bin/cg_xmit`, `/app/output/protocol_transcript.json`, `/app/environment/engine/seg_v`, `/app/environment/fixtures/fx_h49.jsonl`, `/app/environment/fixtures/arm_tbl.toml`, `/app/environment/docs/pact_r8.md`.

Author anonymous tagged this **hard** system-administration task (rust, cgroup, systemd, sandbox, nesting, runner).

Time estimates: expert ~120 min, junior ~480 min.

Harbor timeouts: agent 1200s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `4e8a157c-e3d3-44d0-bb7d-600de063f6fd_submission_2026-07-19T17_36_05.769Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
