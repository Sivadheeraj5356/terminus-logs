# The integer numerical RFIM simulation under `/app/environment` no longer reprodu

Submission: `59dcaeee-a53a-4a49-8acb-2cec1019e392`  
Slug: `the-integer-numerical-rfim-simulation-under-app-environment`  
Latest archive: `59dcaeee-a53a-4a49-8acb-2cec1019e392_submission_2026-07-18T07_13_10.775Z.zip`  
Revisions: 3

## Task summary

The integer numerical RFIM simulation under `/app/environment` no longer reproduces the quasi-static hysteresis path across field intervals and resumed runs. Repair the Go numerical simulation source code under `/app/environment` so `go run /app/environment/cmd/fieldloop --model MODEL.json --field FIELD.tsv --output-dir DIR` evolves every reachable instability event, publishes `/app/output/trajectory.tsv`, `/app/output/avalanches.jsonl`, and `/app/output/checkpoint.json` by default, and follows the complete observable contract in `/app/environment/docs/FIELD_MODEL.rst`. The bundled study uses `/app/environment/fixtures/model.json` and `/app/environment/fixtures/field.tsv`. Rebuild and regenerate the artifacts through the normal command; prewritten outputs are not a valid result.

Required artifacts include: `/app/environment`, `/app/environment/cmd/fieldloop`, `/app/output/trajectory.tsv`, `/app/output/avalanches.jsonl`, `/app/output/checkpoint.json`, `/app/environment/docs/FIELD_MODEL.rst`, `/app/environment/fixtures/model.json`, `/app/environment/fixtures/field.tsv`.

Author anonymous tagged this **hard** scientific-computing task (go, rfim, quasi-static-sweep, return-point-memory, checkpoint-replay).

Time estimates: expert ~180 min, junior ~540 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `59dcaeee-a53a-4a49-8acb-2cec1019e392_submission_2026-07-18T07_13_10.775Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
