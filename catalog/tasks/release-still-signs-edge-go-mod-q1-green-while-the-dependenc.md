# Release still signs EDGE-GO-MOD-Q1 green while the dependency graph, live module

Submission: `3fbf9b62-caa3-44f3-82be-20107b3e97da`  
Slug: `release-still-signs-edge-go-mod-q1-green-while-the-dependenc`  
Latest archive: `3fbf9b62-caa3-44f3-82be-20107b3e97da_submission_2026-07-21T04_08_26.046Z.zip`  
Revisions: 8

## Task summary

Release still signs EDGE-GO-MOD-Q1 green while the dependency graph, live module registry posture, and reproducibility certificate disagree on the escalated pins. Some members keep sailing through as if the frozen January pack were enough, advisory waivers that release engineering already recorded are not showing up that way, and the digest export that is supposed to seal the batch does not match what sign-off expects on the production track. Bring the module dependency integrity gate under /app back in line so the compiled modgate entrypoint on PATH, run against the bundled primary manifest, prints MODGATE_OK and writes every contract-conforming artifact under /app/output. Observable shapes and invariants live in /app/docs/output-contract.md. Policy, overlays, helper interfaces, and digest formulas are defined by the signed materials named from the manifest. Native helpers named there must remain compiled ELF binaries. Hand-authored JSON does not satisfy the CLI contract. The same binary must generalize to other valid manifests that share the batch layout.

Required artifacts include: `/app/output`, `/app/docs/output-contract.md`, `/app/data`.

Author anonymous tagged this **hard** build-and-dependency-management task (golang-proxy, checksumdb, go-mod, retract, sumdb, integrity-gate).

Time estimates: expert ~300 min, junior ~900 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Harbor trials: 1 — 0 solved, 1 valid fail, 0 timeout, 0 infra.

## Agent summary

Skipping image OS validation for hb__d408663534d6d4267df063016344fda7: docker inspect returned 1 Collecting main service artifacts

## Stump the models?

- oracle: 1/1 valid fail (100.0%)
- Timeouts excluded: 0; infra excluded: 0
- Band: `stumps`
