# # Contain archive extraction attacks

Submission: `ddaf8052-e913-4c1a-a68d-180a40b3cad6`  
Slug: `contain-archive-extraction-attacks`  
Latest archive: `ddaf8052-e913-4c1a-a68d-180a40b3cad6_submission_2026-07-20T18_48_05.647Z.zip`  
Revisions in Dropbox: 1

## Task summary

An incident-response quarantine service received hostile nested submissions that escaped review roots, spoofed trusted paths, and exhausted workers. Harden the archive security boundary implemented under `/app/src` so it enforces the complete extraction security contract in `/app/docs/EXTRACTION_SECURITY.md`. Keep the documented two-argument CLI. The hardened extractor must safely handle the documented TAR and ZIP inputs, recursively expand content-identified nested archives, preserve documented safe files and in-tree links, and enforce every path, entry-type, Unicode-collision, sparse-file, nesting, size, compression-ratio, and aggregate containment limit in the contract.

Required artifacts include: `/app/src`, `/app/docs/EXTRACTION_SECURITY.md`.

Author anonymous tagged this **hard** security task (archive-security, zip-slip, decompression-bomb, symlink-escape, filesystem-containment).

Time estimates: expert ~380 min, junior ~600 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `ddaf8052-e913-4c1a-a68d-180a40b3cad6_submission_2026-07-20T18_48_05.647Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
