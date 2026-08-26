# The offline Sigstore model-signing deploy gate under `/app/environment` is suppo

Submission: `185c0116-5994-4fef-88cf-842385e2adb7`  
Slug: `the-offline-sigstore-model-signing-deploy-gate-under-app-env`  
Latest archive: `185c0116-5994-4fef-88cf-842385e2adb7_submission_2026-07-20T11_57_20.856Z.zip`  
Revisions in Dropbox: 2

## Task summary

The offline Sigstore model-signing deploy gate under `/app/environment` is supposed to prove foreign-cloud signing principals cannot authorize home-cloud workload deploys after approval revoke windows (including cert validity windows, counter-sign quorum floors, and stale signing-cache residue). Independent deploy-probe replay must agree with the published package; local signing-witness success is not enough. That proof does not hold today. Repair the sources under `/app/environment` so `bash /app/environment/scripts/weld_bin.sh` then `bash /app/environment/tools/mx_run.sh gate --out /app/output/mx_pack.json` emits a schema-valid package at that path. Checks re-run that weld-and-gate sequence. A hand-written static artifact is not enough. Digests, freshness, classify, and seals must recompute from the live sign and xrow fixtures whenever those inputs change.

Required artifacts include: `/app/environment`, `/app/environment/scripts/weld_bin.sh`, `/app/environment/tools/mx_run.sh`, `/app/output/mx_pack.json`, `/app/environment/docs/`, `/app/environment/fixtures/sign/`, `/app/environment/fixtures/xrows/`, `/app/environment/fixtures/cache_stale/`.

Author anonymous tagged this **hard** build-and-dependency-management task (go, sigstore, attestation, quorum, weld, deploy-gate).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `185c0116-5994-4fef-88cf-842385e2adb7_submission_2026-07-20T11_57_20.856Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
