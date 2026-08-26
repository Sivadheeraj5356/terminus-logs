# The Obsidian Vault WEBrick service at `/app` failed pen testing against the secu

Submission: `0d727b9a-6d60-407f-b486-40c70d99ceb6`  
Slug: `the-obsidian-vault-webrick-service-at-app-failed-pen-testing`  
Latest archive: `0d727b9a-6d60-407f-b486-40c70d99ceb6_submission_2026-07-15T09_45_43.276Z.zip`  
Revisions: 2

## Task summary

The Obsidian Vault WEBrick service at `/app` failed pen testing against the security contract in `/app/docs/api_spec.md`. Incident write-ups and exploit notes live in `/app/docs/vault_design_dossier.md`. Close the open vulnerabilities so the service matches that contract:

Required artifacts include: `/app/docs/api_spec.md`, `/app/docs/vault_design_dossier.md`, `/app/config/settings.yaml`, `/app/prop_test/`, `/app/prop_test`.

Author Anonymous tagged this **medium** security task (security, hardening, hmac, auth-bypass, rate-limiting, webrick).

Time estimates: expert ~90.0 min, junior ~180.0 min.

Harbor timeouts: agent 1800.0s, verifier 420.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `0d727b9a-6d60-407f-b486-40c70d99ceb6_submission_2026-07-15T09_45_43.276Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
