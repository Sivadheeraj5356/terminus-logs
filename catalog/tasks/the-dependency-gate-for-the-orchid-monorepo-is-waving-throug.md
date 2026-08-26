# The dependency gate for the Orchid monorepo is waving through things it should b

Submission: `081b841a-dbb7-4af4-9459-e2c9fef3e732`  
Slug: `the-dependency-gate-for-the-orchid-monorepo-is-waving-throug`  
Latest archive: `081b841a-dbb7-4af4-9459-e2c9fef3e732_submission_2026-07-07T08_12_09.301Z.zip`  
Revisions in Dropbox: 3

## Task summary

The dependency gate for the Orchid monorepo is waving through things it should be blocking. The gate is an OPA bundle at /app/policy that scores every row of the build ledger at /app/ledger/dependency_ledger.csv — most visibly, it approved a quarantined model artifact last week, and several exception clauses from the maintainer handbook were never carried into the policy correctly. Repair the policy bundle so its decisions match the handbook under /app/docs/handbook/ — that is the authority for quarantine handling, model artifact integrity, license classes and waivers, release channels, and lockfile provenance. The handbook has been amended over the program's life, so a threshold or clause as stated in one chapter is not necessarily still in force.

Required artifacts include: `/app/policy`, `/app/ledger/dependency_ledger.csv`, `/app/docs/handbook/`, `/app/bin/ledger-audit`, `/app/models/`, `/app/out/decisions.json`, `/app/docs/decisions-format.md`, `/app/bin/qa-check`.

Author Anonymous tagged this **medium** build-and-dependency-management task (rego, opa, bash, openssl, dependency-management, long-context).

Time estimates: expert ~120.0 min, junior ~300.0 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `081b841a-dbb7-4af4-9459-e2c9fef3e732_submission_2026-07-07T08_12_09.301Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
