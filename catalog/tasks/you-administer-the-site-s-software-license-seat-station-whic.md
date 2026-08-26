# You administer the site's software license-seat station, which provisions entitl

Submission: `b1d7c1b1-ab3a-41a0-b348-a6f9f96b6d5d`  
Slug: `you-administer-the-site-s-software-license-seat-station-whic`  
Latest archive: `b1d7c1b1-ab3a-41a0-b348-a6f9f96b6d5d_submission_2026-07-11T05_25_39.322Z.zip`  
Revisions in Dropbox: 1

## Task summary

You administer the site's software license-seat station, which provisions entitlement seats to onboarding accounts from the pool of covered seats. Its overnight allocation stage is unfinished: finish `/app/license/` so the night's request feed turns into the JSON allocation file the morning operators work from: node /app/bin/seat-allocate /app/data/onboarding_requests.ndjson /app/out/allocation.json

Required artifacts include: `/app/license/`, `/app/bin/seat-allocate`, `/app/data/onboarding_requests.ndjson`, `/app/out/allocation.json`, `/app/data`, `/app/docs/seat-allocate.md`.

Author Anonymous tagged this **medium** system-administration task (system-administration, license-management, entitlements, provisioning, json).

Time estimates: expert ~90.0 min, junior ~180.0 min.

Harbor timeouts: agent 900.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `b1d7c1b1-ab3a-41a0-b348-a6f9f96b6d5d_submission_2026-07-11T05_25_39.322Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
