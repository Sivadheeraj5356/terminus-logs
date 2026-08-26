# The chamber escape desk under /app/environment is a terminal puzzle simulation: 

Submission: `fe0f2689-b834-4534-93fe-fbe813b371f1`  
Slug: `the-chamber-escape-desk-under-app-environment-is-a-terminal`  
Latest archive: `fe0f2689-b834-4534-93fe-fbe813b371f1_submission_2026-07-09T06_56_01.061Z.zip`  
Revisions: 2

## Task summary

The chamber escape desk under /app/environment is a terminal puzzle simulation: a Rust pathfinding planner, a local topology HTTP service, graph fixtures under vault, and a public route-manifest contract. Operators at the escape desk run bash /app/environment/scripts/run_escape.sh to rebuild desk_k, start the hidden-port topology service, recover live chamber evidence, compute an egress walk through the vault graph, and write /app/output/route_manifest.json.

Required artifacts include: `/app/environment`, `/app/environment/scripts/run_escape.sh`, `/app/output/route_manifest.json`, `/app/docs/escape_pipeline.md`, `/app/docs/manifest_contract.md`, `/app/docs/api_notes.md`, `/app/environment/schemas/route_manifest.schema.json`.

Author anonymous tagged this **hard** games task (rust, bash, lsof, strace, http, pathfinding).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `fe0f2689-b834-4534-93fe-fbe813b371f1_submission_2026-07-09T06_56_01.061Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
