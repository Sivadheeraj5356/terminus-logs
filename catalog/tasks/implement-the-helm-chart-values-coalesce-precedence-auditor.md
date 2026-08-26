# Implement the Helm chart values coalesce precedence auditor at /app/bin/helmvals

Submission: `b7feeb58-639a-4730-ad07-7dd52797d28f`  
Slug: `implement-the-helm-chart-values-coalesce-precedence-auditor`  
Latest archive: `b7feeb58-639a-4730-ad07-7dd52797d28f_submission_2026-07-10T09_02_13.457Z.zip`  
Revisions: 2

## Task summary

Implement the Helm chart values coalesce precedence auditor at /app/bin/helmvals. The CLI walks a local chart tree (Chart.yaml, values.yaml, nested charts/) and emits a resolved values manifest with a precedence trail. Authoritative behavior is defined in /app/docs/chart-contract.md, /app/docs/coalesce-contract.md, /app/docs/global-contract.md, /app/docs/condition-contract.md, /app/docs/cli-contract.md, and /app/docs/manifest-output.md. Read those documents end-to-end before changing code.

Required artifacts include: `/app/bin/helmvals`, `/app/docs/chart-contract.md`, `/app/docs/coalesce-contract.md`, `/app/docs/global-contract.md`, `/app/docs/condition-contract.md`, `/app/docs/cli-contract.md`, `/app/docs/manifest-output.md`, `/app/scripts/verifier-rebuild.sh`.

Author anonymous tagged this **hard** build-and-dependency-management task (helm, kubernetes, values-coalesce, dependency-management, yaml).

Time estimates: expert ~300 min, junior ~720 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `b7feeb58-639a-4730-ad07-7dd52797d28f_submission_2026-07-10T09_02_13.457Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
