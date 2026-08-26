# security_authority_split

Submission: `68582dd2-eae7-413e-a2cb-5d572fcdc381`  
Slug: `security-authority-split`  
Latest archive: `68582dd2-eae7-413e-a2cb-5d572fcdc381_submission_2026-07-22T06_40_01.733Z.zip`  
Revisions in Dropbox: 2

## Task summary

The rootless deployment identity and ACL authority layer under `/app` enforces mapped ownership records, principal ACL metadata, inode-linked deployment content, and managed-path lifecycle rules for tbundle restores without elevated privileges. Recent bundle upgrades exposed wrong mapped ownership, duplicated hardlink payloads, missing ACL principal records, and non-deterministic repeat-restore logs. Repair the restore authority layer so archives from `/app/archives` reconstruct `/output/restore-root` and `/output/restore-log.json` per `/app/docs/restore-contract.md`, `/app/docs/manifest-format.md`, and `/app/docs/log-schema.md`. The layer must enforce the documented rootless identity boundary, subordinate UID/GID mapping, and POSIX/PAX restore contract rather than bypass verification with regenerated artifacts. Hand-written trees or logs are insufficient. The verifier exercises the documented restore workflow from current sources and validates through `/tests/test.sh` with pytest `--ctrf /logs/verifier/ctrf.json`. Platform pytest under `/tests` may import `fixture_factory` and `verifier_expect`; harness constants, CLI flags, and wrapper/module entrypoint parity are documented in `/app/docs/verification-contract.md` and `/app/docs/operations.md`. Subordinate UID and GID mapping rules are in `/app/config/idmap.toml`.

Required artifacts include: `/app/archives`, `/output/restore-root`, `/output/restore-log.json`, `/app/docs/restore-contract.md`, `/app/docs/manifest-format.md`, `/app/docs/log-schema.md`, `/app/docs/verification-contract.md`, `/app/docs/operations.md`.

Author anonymous tagged this **hard** security task (acl, identity-mapping, trust-boundary, rootless, xattrs, deployment-metadata).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1500s, verifier 300s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `68582dd2-eae7-413e-a2cb-5d572fcdc381_submission_2026-07-22T06_40_01.733Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Identity, ACL, or permission mapping is close but fails the restore/authority contract. Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
