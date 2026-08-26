# Hey — the SVOD residual rollups under `/app/output/` are wrong and incomplete af

Submission: `4a631aa6-d9ba-47b2-9fcf-a0481acce205`  
Slug: `hey-the-svod-residual-rollups-under-app-output-are-wrong-and`  
Latest archive: `4a631aa6-d9ba-47b2-9fcf-a0481acce205_submission_2026-07-07T15_27_36.043Z.zip`  
Revisions: 1

## Task summary

Hey — the SVOD residual rollups under `/app/output/` are wrong and incomplete after we merged the new usage shards. Build the Go processor under `/app` so `go run ./cmd/residual` reads every JSONL shard under `/app/data/usage`, the catalog CSVs under `/app/data/`, and config under `/app/config/`, leaves all inputs byte-identical, and writes `/app/output/residual_daily.csv`, `/app/output/residual_weekly.csv`, and `/app/output/escrow_ledger.jsonl`. Use only the Go standard library (`GOPROXY=off`). Do not hardcode rollup results for the bundled feeds alone. The stub compiles but emits incorrect partial output — replace it with the full end-to-end pipeline. Key requirements: Load manifest-listed usage shards first, then unlisted `*.jsonl` shards by lexicographic basename.; Keep source-line metadata as the 1-based count of non-blank data lines; blank lines do not increment it.; Skip malformed rows after emitting the exact stderr audit line required by the usage feed contract.; Resolve aliases case-insensitively and ignore unknown aliases, inactive works, unknown territories, and unsupported media..

Required artifacts include: `/app/output/`, `/app/data/usage`, `/app/data/`, `/app/config/`, `/app/output/residual_daily.csv`, `/app/output/residual_weekly.csv`, `/app/output/escrow_ledger.jsonl`, `/app/docs/usage_feed_contract.md`.

Author anonymous tagged this **hard** data-processing task (go, royalties, residuals, deduplication, escrow, hmac).

Time estimates: expert ~150 min, junior ~420 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `4a631aa6-d9ba-47b2-9fcf-a0481acce205_submission_2026-07-07T15_27_36.043Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
