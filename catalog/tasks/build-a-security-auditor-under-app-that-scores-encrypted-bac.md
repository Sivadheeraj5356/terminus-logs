# Build a security auditor under /app that scores encrypted backup trustworthiness

Submission: `a42dfd18-6e62-4b62-9a15-1bada2e83212`  
Slug: `build-a-security-auditor-under-app-that-scores-encrypted-bac`  
Latest archive: `a42dfd18-6e62-4b62-9a15-1bada2e83212_submission_2026-07-18T19_37_12.367Z.zip`  
Revisions in Dropbox: 4

## Task summary

Build a security auditor under /app that scores encrypted backup trustworthiness against adversarial tampering. Twenty archive files live in /app/archives as archive_01.json through archive_20.json. Security contracts are /app/contracts/TRUST_REPORT.md, /app/contracts/ARCHIVE_FORMAT.md, and /app/rules/escrow_matrix.yaml. Write /app/verdicts/backup_trust_report.json with cryptographic coverage gaps, unauthorized mutations, escrow integrity breaks, retention tampering, restore forgery, silent corruption, and adversarial resilience failures. Implement vault.ResolveArchivesDir and vault.LoadArchive in /app/vault/archive.go, and audit.AssessArchive in /app/audit/trust.go. Leave the bootstrap, orchestrate, emit, and schema packages alone. Produce an executable /app/bin/ebta larger than 2048 bytes.

Required artifacts include: `/app/archives`, `/app/contracts/TRUST_REPORT.md`, `/app/contracts/ARCHIVE_FORMAT.md`, `/app/rules/escrow_matrix.yaml`, `/app/verdicts/backup_trust_report.json`, `/app/vault/archive.go`, `/app/audit/trust.go`, `/app/bin/ebta`.

Author anonymous tagged this **hard** security task (cryptography, encrypted-backup, key-escrow, unauthorized-access, adversarial-resilience, go).

Time estimates: expert ~120 min, junior ~240 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `a42dfd18-6e62-4b62-9a15-1bada2e83212_submission_2026-07-18T19_37_12.367Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
