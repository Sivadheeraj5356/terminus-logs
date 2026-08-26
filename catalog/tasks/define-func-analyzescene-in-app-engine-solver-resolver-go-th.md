# Define `func AnalyzeScene` in `/app/engine/solver/resolver.go` — the stub still 

Submission: `e4904d46-ffc2-4a2f-ae58-d0bb152c7b3e`  
Slug: `define-func-analyzescene-in-app-engine-solver-resolver-go-th`  
Latest archive: `e4904d46-ffc2-4a2f-ae58-d0bb152c7b3e_submission_2026-07-12T06_53_47.725Z.zip`  
Revisions: 1

## Task summary

Define `func AnalyzeScene` in `/app/engine/solver/resolver.go` — the stub still panics there today. Wire it up so `make build` from `/app` produces `/app/bin/contact-resolver` over 2048 bytes (the verifier greps that file for `func AnalyzeScene`). The binary must write `/app/results/contact_stability_report.json` (UTF-8, trailing newline, byte-identical across runs). Specs live in `/app/spec/OUTPUT_SCHEMA.md` and `/app/spec/INPUT_FORMAT.md`; thresholds in `/app/rules/contact_policy.yaml`. Bundled summary on the stock scenes is 20 / 12 unstable / 8 stable / 13 violations. Each scene row: `scene_id`, `unstable`, `violations`, `max_penetration_m`, `impulse_chain_len`, `stress`. `impulse_chain_len` is `0` only when every frame has an empty `contacts` array; if any frame has contacts it is at least `1` (longest same-frame chain where each contact's `body_b` matches the next contact's `body_a` — bundled `scene_05` is `2`). Each violation's `detail` string must match the normative table in OUTPUT_SCHEMA exactly (e.g. `monotonic penetration growth`, `manifold survived after contact removal`). For `impulse_chain_break`, `bodies` is exactly `[first_body_in_chain, last_body_in_chain]` (two entries — not every body in the chain). For `stale_manifold`, `bodies` is `[manifold_id]` and emit once per manifold on the first frame where survival exceeds the policy limit.

Required artifacts include: `/app/engine/solver/resolver.go`, `/app/bin/contact-resolver`, `/app/results/contact_stability_report.json`, `/app/spec/OUTPUT_SCHEMA.md`, `/app/spec/INPUT_FORMAT.md`, `/app/rules/contact_policy.yaml`, `/app/scenarios/`.

Author anonymous tagged this **hard** games task (physics, collision, contact-resolution, rigid-body, simulation, go).

Time estimates: expert ~120 min, junior ~180 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `e4904d46-ffc2-4a2f-ae58-d0bb152c7b3e_submission_2026-07-12T06_53_47.725Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
