# Build a Node.js certificate worker (/app/src/worker.js) that manages a 2-tier PK

Submission: `5fdf58a3-9ca9-40d6-aa68-b54a30c666c3`  
Slug: `build-a-node-js-certificate-worker-app-src-worker-js-that-ma`  
Latest archive: `5fdf58a3-9ca9-40d6-aa68-b54a30c666c3_submission_2026-07-15T15_53_44.598Z.zip`  
Revisions in Dropbox: 1

## Task summary

Build a Node.js certificate worker (/app/src/worker.js) that manages a 2-tier PKI hierarchy, automates certificate lifecycle, and enforces cryptographic integrity constraints. The worker must support flags --ledger <path> (CSV service list) and --pki-dir <path> (PKI storage directory, defaults to /app/data/services.csv and /app/pki). **Multi-Tier PKI & Certificate Issuance** Implement a two-tier CA: root CA in `pki-dir/ca/` (`ca.key.pem`, `ca.crt.pem`), and per-service intermediate CAs (in `pki-dir/services/<service>/`). Each service's intermediate is signed by root; service certificates are signed by their intermediate (not root). Issue service certificates with exactly 90-day validity.

Required artifacts include: `/app/src/worker.js`, `/app/data/services.csv`, `/app/pki`.

Author anonymous tagged this **hard** system-administration task (openssl, pki, certificates, worker, csv).

Time estimates: expert ~90 min, junior ~210 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `5fdf58a3-9ca9-40d6-aa68-b54a30c666c3_submission_2026-07-15T15_53_44.598Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
