# Restore the fail-closed `PFSEAL2` cryptographic trust decision at `/app/bin/pfse

Submission: `284e04c7-43cb-4ce7-b18f-f75a11d3dcc8`  
Slug: `restore-the-fail-closed-pfseal2-cryptographic-trust-decision`  
Latest archive: `284e04c7-43cb-4ce7-b18f-f75a11d3dcc8_submission_2026-07-15T13_18_09.864Z.zip`  
Revisions in Dropbox: 1

## Task summary

Restore the fail-closed `PFSEAL2` cryptographic trust decision at `/app/bin/pfseal-worker`. Every Prefect image annotation and split-key row is untrusted evidence: reject ambiguous transport, noncanonical framing, forged key-set attestations or lineage, altered headers, invalid GCM tags, cross-deployment payloads, retired or future keys, stale counters, and invalid validity windows without exposing plaintext. Reassemble direct or chunked envelopes, require a revision-eligible 2-of-3 Ed25519 witness quorum over the canonical decoded key shares, derive independent AES-256-GCM and HMAC-SHA256 keys with the documented HKDF schedule, compare the header MAC in constant time before decryption, and authenticate any revision-bound successor proof. `/app/docs/pfseal2-wire.md`, `/app/docs/transparency-contract.md`, `/app/docs/threat-model.md`, and the failure precedence are the security contract. The verifier interface remains exactly `pfseal-worker --db ABSOLUTE_PATH --worker-id ID [--once | --idle-limit N] [--poll-ms N] [--at RFC3339]`; `--help` alone prints it with `Usage: `. Canonical millisecond UTC `--at` defaults once at startup. Reject duplicate, unknown, missing, empty, relative-path, invalid-id, and conflicting options before opening DuckDB; `--poll-ms` is 10–60000 and `--idle-limit` is 0–1000. Exit 0 emits exactly one minified, claim-ordered summary using key order `workerId`, `claimed`, `succeeded`, `failed`, `rotations`, `jobs`; the empty form is `{"workerId":"ID","claimed":0,"succeeded":0,"failed":0,"rotations":0,"jobs":[]}`. Usage failures print only `pfseal-worker:...

Required artifacts include: `/app/bin/pfseal-worker`, `/app/docs/pfseal2-wire.md`, `/app/docs/transparency-contract.md`, `/app/docs/threat-model.md`.

Author anonymous tagged this **medium** security task (security-audit, cryptography, aes-gcm, hmac-sha256, hkdf, replay-protection).

Time estimates: expert ~240 min, junior ~480 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `284e04c7-43cb-4ce7-b18f-f75a11d3dcc8_submission_2026-07-15T13_18_09.864Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
