# AtlasBatch still promotes inference models by hand — someone eyeballs the Compos

Submission: `66f7bc77-ca73-450c-8f41-c184ce26d473`  
Slug: `atlasbatch-still-promotes-inference-models-by-hand-someone-e`  
Latest archive: `66f7bc77-ca73-450c-8f41-c184ce26d473_submission_2026-07-06T20_21_30.886Z.zip`  
Revisions: 1

## Task summary

AtlasBatch still promotes inference models by hand — someone eyeballs the Compose service, canary JSON, eval DB numbers, registry manifests, and whether the sklearn pin exists upstream. Wire up the Lua CLI at `/app/bin/atlas-promote` so `run --candidate <id> --compose <path>` evaluates every promotion gate and writes `/app/output/promotion-decision.json` per `/app/docs/promotion-decision.schema.json`. Several modules under `/app/src/` regressed during a refactor, including shared helpers split out of the gate logic. Gate rules and input contracts are spread across `/app/docs/` and `/app/archives/`; ratified comms supersede legacy engineering notes. Reject when any gate fails; list every failure in `reasons` sorted alphabetically; exit 0 for both approve and reject. Environment is offline.

Required artifacts include: `/app/bin/atlas-promote`, `/app/output/promotion-decision.json`, `/app/docs/promotion-decision.schema.json`, `/app/src/`, `/app/docs/`, `/app/archives/`.

Author Anonymous tagged this **medium** data-processing task (sqlite, docker-compose, model-promotion, scikit-learn).

Time estimates: expert ~150.0 min, junior ~360.0 min.

Harbor timeouts: agent 1800.0s, verifier 420.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `66f7bc77-ca73-450c-8f41-c184ce26d473_submission_2026-07-06T20_21_30.886Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
