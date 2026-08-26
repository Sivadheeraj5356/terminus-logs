# Apexora Global Wave 3 campus segmentation is blocked across ninety-six devices u

Submission: `a5317367-9c2d-4fa2-aa05-dee9bab3e7ab`  
Slug: `apexora-global-wave-3-campus-segmentation-is-blocked-across-`  
Latest archive: `a5317367-9c2d-4fa2-aa05-dee9bab3e7ab_submission_2026-07-21T11_17_01.746Z.zip`  
Revisions in Dropbox: 6

## Task summary

Apexora Global Wave 3 campus segmentation is blocked across ninety-six devices under `/app/environment`. Inventory and identity still carry legacy VLAN IDs and deprecated VRF aliases, trunks and gateways violate selective policy, ACL names remain flat-network era, and deployment manifests still wire deprecated validation hooks with incomplete rollback indexing — several `/app/environment/scripts/run-netsegctl.sh` stages fail on the current tree. Repair declarative configuration under `/app/environment` only. Treat the rollout as one dependency graph. Export shapes, cumulative configuration-authority gates (`config_authoritative_m1` through `m3`), and the binding stage order are in `/app/environment/schemas/pipeline/`. Operational interpretation, the transitive dependency spine, inventory baselines, VLAN/VRF/ACL derivation, selective trunk and gateway rules, and rollback requirements are in `/app/environment/docs/OPERATIONS.md` and `/app/environment/docs/ROLLBACK.md` (index: `/app/environment/docs/segmentation_contract.md`).

Required artifacts include: `/app/environment`, `/app/environment/scripts/run-netsegctl.sh`, `/app/environment/schemas/pipeline/`, `/app/environment/docs/OPERATIONS.md`, `/app/environment/docs/ROLLBACK.md`, `/app/environment/docs/segmentation_contract.md`, `/app/output/`.

Author anonymous tagged this **hard** system-administration task (vlan, vrf, trunk-policy, acl, network-rollout, networking).

Time estimates: expert ~420 min, junior ~1080 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `a5317367-9c2d-4fa2-aa05-dee9bab3e7ab_submission_2026-07-21T11_17_01.746Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Identity, ACL, or permission mapping is close but fails the restore/authority contract. Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
