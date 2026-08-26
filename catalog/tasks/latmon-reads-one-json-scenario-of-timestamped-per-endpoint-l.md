# `latmon` reads one JSON scenario of timestamped per-endpoint latency samples on 

Submission: `d27f9ad2-3e98-4e4a-993a-c9c1aad5343a`  
Slug: `latmon-reads-one-json-scenario-of-timestamped-per-endpoint-l`  
Latest archive: `d27f9ad2-3e98-4e4a-993a-c9c1aad5343a_submission_2026-07-09T06_57_17.295Z.zip`  
Revisions in Dropbox: 5

## Task summary

`latmon` reads one JSON scenario of timestamped per-endpoint latency samples on standard input and writes one canonical JSON alarm ledger on standard output. Build it with `go build -o latmon ./cmd/latmon` and run it as `./latmon < scenario.json > ledger.json`. Your job is to implement the missing computation that turns a validated scenario into its ledger. `latmon` already reads standard input, validates it, and writes standard output; leave that wiring and the command-line interface as they are. Every quantity is an integer: timestamps, latency values in ms, and the `limit`, `arm`, `reset`, and `budget` parameters measured in seconds (except `limit`).

Required artifacts include: not named as `/app` paths.

Author anonymous tagged this **hard** data-processing task (endpoint-latency, alarm-ledger, event-stream, protection-relay, debounce-dwell, continuous-time).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=weak, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `d27f9ad2-3e98-4e4a-993a-c9c1aad5343a_submission_2026-07-09T06_57_17.295Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
