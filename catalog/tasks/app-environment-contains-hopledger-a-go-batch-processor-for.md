# `/app/environment` contains `hopledger`, a Go batch processor for relay-mesh hop

Submission: `cfe2f2a7-0da5-44c9-b3b3-c9df0ecc1bae`  
Slug: `app-environment-contains-hopledger-a-go-batch-processor-for`  
Latest archive: `cfe2f2a7-0da5-44c9-b3b3-c9df0ecc1bae_submission_2026-07-08T06_31_23.234Z.zip`  
Revisions: 1

## Task summary

`/app/environment` contains `hopledger`, a Go batch processor for relay-mesh hop journals. The current implementation handles only the legacy happy path and produces incorrect shift-close artifacts for mixed-version manifests, revised lane records, cancellation tombstones, policy changes, and resumed replay. Implement the replay contract documented under `/app/environment/docs/` so manifests like `/app/environment/fixtures/manifest.json` produce deterministic `report`, `digest`, and `audit` artifacts through the documented CLI. The tool must create missing output parent directories, reject invalid histories without leaving partial outputs, and make `--resume-tag` output byte-identical to an uninterrupted run over the same manifest.

Required artifacts include: `/app/environment`, `/app/environment/docs/`, `/app/environment/fixtures/manifest.json`.

Author anonymous tagged this **hard** data-processing task (go, ndjson, checkpoint, replay, deterministic-output, data-processing).

Time estimates: expert ~360 min, junior ~900 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `cfe2f2a7-0da5-44c9-b3b3-c9df0ecc1bae_submission_2026-07-08T06_31_23.234Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
