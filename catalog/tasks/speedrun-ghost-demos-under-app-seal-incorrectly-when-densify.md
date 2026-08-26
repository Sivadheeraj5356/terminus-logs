# Speedrun ghost demos under `/app` seal incorrectly when densify packing and inde

Submission: `6e0cf6ff-faf1-431f-9a90-0135f6858277`  
Slug: `speedrun-ghost-demos-under-app-seal-incorrectly-when-densify`  
Latest archive: `6e0cf6ff-faf1-431f-9a90-0135f6858277_submission_2026-07-15T10_56_19.390Z.zip`  
Revisions: 1

## Task summary

Speedrun ghost demos under `/app` seal incorrectly when densify packing and independent replay diverge. Fix the Java library sources under `/app/environment` so `bash /app/driver/emit_ghost.sh` (also `/app/environment/driver/emit_ghost.sh`) rebuilds a valid `/app/output/ghost_seal.json` from `/app/data/annex_slice36`, band profiles under `/app/data/bands/profiles`, and `/app/fixtures/closed_algebra.json`. Digest and densify rules live in `/app/docs/pol_contract.md`. The checker recompiles `sep_tool`, `fold_tool`, and `tie_tool` with javac from the libraries under `/app` and runs those tools. Static or manual ghost seal writes are insufficient; the normal pipeline must regenerate `/app/output/ghost_seal.json`. Stay offline; no package downloads.

Required artifacts include: `/app/environment`, `/app/driver/emit_ghost.sh`, `/app/environment/driver/emit_ghost.sh`, `/app/output/ghost_seal.json`, `/app/data/annex_slice36`, `/app/data/bands/profiles`, `/app/fixtures/closed_algebra.json`, `/app/docs/pol_contract.md`.

Author anonymous tagged this **hard** games task (java, games, speedrun, ghost-demo, tick-budget, ghost-seal).

Time estimates: expert ~150 min, junior ~420 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `6e0cf6ff-faf1-431f-9a90-0135f6858277_submission_2026-07-15T10_56_19.390Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
