# A sccache release guard must close a reproducible build attestation from depende

Submission: `299441da-a136-484d-b73c-1f698f87663b`  
Slug: `a-sccache-release-guard-must-close-a-reproducible-build-atte`  
Latest archive: `299441da-a136-484d-b73c-1f698f87663b_submission_2026-07-17T11_14_17.121Z.zip`  
Revisions: 10

## Task summary

A sccache release guard must close a reproducible build attestation from dependency lock pins, define-order lockfile traces, and compiler-wrapper SBOM hash segments before publish clears. Produce `/app/output/kq_report.json` through `/app/environment/tools/kq_run`. The lockfile reload rules, supply-chain pin blend, release-guard witness, and reproducibility digest are specified in `/app/environment/docs/kq_contract.md`, `/app/environment/docs/kq_notes.md`, and `/app/environment/docs/build-cache-sbom-lockfile.md`.

Required artifacts include: `/app/output/kq_report.json`, `/app/environment/tools/kq_run`, `/app/environment/docs/kq_contract.md`, `/app/environment/docs/kq_notes.md`, `/app/environment/docs/build-cache-sbom-lockfile.md`, `/app/output/kq_frames.ndjson`, `/app/environment/docs/`.

Author anonymous tagged this **hard** build-and-dependency-management task (sccache, build-cache, lockfile, sbom, reproducibility, attestation, release-guard, supply-chain).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1200s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `299441da-a136-484d-b73c-1f698f87663b_submission_2026-07-17T11_14_17.121Z.zip` is a task submission, not a Harbor job. 10 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
