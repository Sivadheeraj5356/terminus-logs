# The Go sources under `/app/environment` produce a broken unit-conversion graph. 

Submission: `0160b109-5123-40a9-b36e-388febc81d97`  
Slug: `the-go-sources-under-app-environment-produce-a-broken-unit-c`  
Latest archive: `0160b109-5123-40a9-b36e-388febc81d97_submission_2026-07-15T05_24_58.314Z.zip`  
Revisions in Dropbox: 5

## Task summary

The Go sources under `/app/environment` produce a broken unit-conversion graph. Fixture arms never land a coherent ledger; diagnose against the docs and data, fix the sources, rebuild, and regenerate artifacts. Hand-written outputs will not pass. Rebuild with `/app/environment/scripts/build_ucg.sh` after source edits. Drive `/app/bin/ucg_run` using `/app/environment/docs/operator_cmds.txt`. The test pipeline reruns that same driver pipeline. Regenerate `/app/output/conversion_ledger.json`, per-run phase transcripts under `/app/output/run_traces/` (run_traces means the directory of per-run phase/arm transcript files the driver writes, named like arm0_cold.trace, arm0_warm.trace, arm1_warm.trace), cache under `/app/output/cache/` including arm_tag, and the journal tip at `/app/output/journal/tip.toml`.

Required artifacts include: `/app/environment`, `/app/environment/scripts/build_ucg.sh`, `/app/bin/ucg_run`, `/app/environment/docs/operator_cmds.txt`, `/app/output/conversion_ledger.json`, `/app/output/run_traces/`, `/app/output/cache/`, `/app/output/journal/tip.toml`.

Author anonymous tagged this **hard** scientific-computing task (go, unit-conversion, scientific-computing, offline-build, cache-invalidation, provenance).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `0160b109-5123-40a9-b36e-388febc81d97_submission_2026-07-15T05_24_58.314Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
