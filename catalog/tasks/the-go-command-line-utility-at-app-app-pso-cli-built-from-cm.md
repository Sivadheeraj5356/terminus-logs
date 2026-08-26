# The Go command-line utility at `/app` (`/app/pso_cli` built from `./cmd/pso`) is

Submission: `5fb99e55-805c-4031-92bc-f23ac00684ae`  
Slug: `the-go-command-line-utility-at-app-app-pso-cli-built-from-cm`  
Latest archive: `5fb99e55-805c-4031-92bc-f23ac00684ae_submission_2026-07-18T08_54_17.940Z.zip`  
Revisions: 2

## Task summary

The Go command-line utility at `/app` (`/app/pso_cli` built from `./cmd/pso`) is a system administration utility designed for automated infrastructure configuration management and server parameter tuning across Linux clusters. Site reliability engineers (SREs) and system administrators invoke `/app/pso_cli` to tune multi-dimensional operating thresholds, service quotas, and kernel resource limits. The CLI evaluates candidate server configurations using an internal parameter evaluation engine (`/app/internal/pso/pso.go`). However, the current engine implementation fails to enforce several critical operating boundary invariants, parameter step constraints, and configuration history formatting rules required by the infrastructure management suite. You must fix `/app/internal/pso/pso.go` so that `/app/pso_cli` strictly conforms to the operational specifications and observable behavioral invariants defined below. Do not modify `/app/internal/pso/rng.go` or `/app/internal/config/config.go`. **System Administration Operational & Behavioral Invariants:** 1. **Configuration Throttle Linear Decay (`w(t)`)**: Across configuration tuning steps `t` from `0` up to `max_iterations - 1`, the configuration step throttle `w(t)` must strictly follow a linear decay schedule from `w_start` down to `w_end`. The linear decay denominator must be `max_iterations - 1` (for `max_iterations > 1`), ensuring that `w(0)` exactly equals `w_start` and `w(max_iterations - 1)` exactly equals `w_end`. 2. **Independent Parameter Step Jitter Sampling (`r1`, `r2`)**: For every server configuration dimension,...

Required artifacts include: `/app/pso_cli`, `/app/internal/pso/pso.go`, `/app/internal/pso/rng.go`, `/app/internal/config/config.go`.

Author anonymous tagged this **hard** system-administration task (go, system-administration, cli, infrastructure-tuning, parameter-management, configuration-automation, sysadmin, linux, service-limits, tool-specific, sre, devops, server-management, configuration-drift, service-quotas, resource-allocation).

Time estimates: expert ~75 min, junior ~150 min.

Harbor timeouts: agent 900.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `5fb99e55-805c-4031-92bc-f23ac00684ae_submission_2026-07-18T08_54_17.940Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
