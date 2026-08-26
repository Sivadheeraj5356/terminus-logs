# Aurelia's regulator publishes civil-time ordinances, and since the 1991 amendmen

Submission: `eddac55d-8f97-4c03-b225-40d1828b90ca`  
Slug: `aurelia-s-regulator-publishes-civil-time-ordinances-and-sinc`  
Latest archive: `eddac55d-8f97-4c03-b225-40d1828b90ca_submission_2026-07-09T19_27_30.857Z.zip`  
Revisions in Dropbox: 2

## Task summary

Aurelia's regulator publishes civil-time ordinances, and since the 1991 amendments landed our zone files have disagreed with them for at least three jurisdictions. Bookings in the affected zones sit an hour off across half of every year. The ordinances are the source of truth now. They live under /app/data/ordinances, one directory per jurisdiction, with each jurisdiction's meridian recorded alongside them. The tzforge crate under /app already walks that corpus. Its build subcommand writes zone files into /app/out/zoneinfo, records a manifest at /app/out/manifest.json, loads a transition index into Postgres, and its serve subcommand answers lookups on port 8080. All of it was written against the legacy offset table we are retiring, not against the ordinance rules, and the emitter predates the layout we agreed with our consumers. The documents in /app/docs define the corpus grammar, the rules that govern which ordinance applies when, the exact bytes a zone file must contain, and the index and service we owe downstream. Key requirements: All of it was written against the legacy offset table we are retiring, not.

Required artifacts include: `/app/data/ordinances`, `/app/out/zoneinfo`, `/app/out/manifest.json`, `/app/docs`, `/app/config/tzforge.toml`, `/app/bin/pgstart.sh`, `/app/migrations`.

Author anonymous tagged this **hard** data-processing task (tzif, ordinance-precedence, dst-transitions, posix-tz-string, zdump, postgresql).

Time estimates: expert ~180 min, junior ~600 min.

Harbor timeouts: agent 1800.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `eddac55d-8f97-4c03-b225-40d1828b90ca_submission_2026-07-09T19_27_30.857Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
