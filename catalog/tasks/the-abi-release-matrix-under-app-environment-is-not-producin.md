# The ABI release matrix under /app/environment is not producing a trustworthy rel

Submission: `cd547b19-3d4d-4daa-a852-31c37e0d2d7c`  
Slug: `the-abi-release-matrix-under-app-environment-is-not-producin`  
Latest archive: `cd547b19-3d4d-4daa-a852-31c37e0d2d7c_submission_2026-07-20T10_34_38.692Z.zip`  
Revisions in Dropbox: 1

## Task summary

The ABI release matrix under /app/environment is not producing a trustworthy release. The artifacts that are published are produced by the SDK build process, but they do not hold together in their published form. The record of the lane that is written by the ABI generator does not agree with the compiled probe’s observation of the lane. Fix the pipeline source under /app/environment. Regenerate the matrix by running the public matrix command that is documented under /app/environment/docs/sdk-contract.md. That command will populate the following files under /app/output/sdk-abi-index: manifest.json, provenance.json, probe.jsonl, loader_journal.tsv, and trace.tsv. The schemas for those artifacts are documented under /app/environment/docs. The header that is previewed in the git commit is only a non-authoritative preview of the contents of the artifacts.

Required artifacts include: `/app/environment`, `/app/environment/docs/sdk-contract.md`, `/app/output/sdk-abi-index`, `/app/environment/docs`, `/app/build/sdk-abi-index`, `/app/environment/idl/pack.order`.

Author anonymous tagged this **hard** build-and-dependency-management task (cmake, generated-code, abi, provenance, cxx).

Time estimates: expert ~180 min, junior ~720 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `cd547b19-3d4d-4daa-a852-31c37e0d2d7c_submission_2026-07-20T10_34_38.692Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Git history or refs are only partially repaired.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
