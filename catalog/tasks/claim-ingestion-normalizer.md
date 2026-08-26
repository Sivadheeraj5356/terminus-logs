# # Claim ingestion normalizer

Submission: `e09c287a-5fea-4161-a6b8-5512dd09ed62`  
Slug: `claim-ingestion-normalizer`  
Latest archive: `e09c287a-5fea-4161-a6b8-5512dd09ed62_submission_2026-07-05T19_31_23.262Z.zip`  
Revisions: 1

## Task summary

Please finish the Go CLI in `/workspace` for this first step. The command I need is: `go run /workspace/cmd/claimtower ingest --claims-root <dir> --as-of YYYY-MM-DD --claims-out <json> --issues-out <tsv>`

Required artifacts include: not named as `/app` paths.

Author anonymous tagged this **hard** data-processing task (go, cli, insurance, claims, data-processing, scheduler).

Time estimates: expert ~240 min, junior ~540 min.

Harbor timeouts: agent Nones, verifier Nones.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=weak, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `e09c287a-5fea-4161-a6b8-5512dd09ed62_submission_2026-07-05T19_31_23.262Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
