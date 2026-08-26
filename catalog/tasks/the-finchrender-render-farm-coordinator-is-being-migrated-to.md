# The FinchRender render-farm coordinator is being migrated to systemd. Under `/ap

Submission: `537f2158-beb1-4c07-bfcf-a4abb2d4f8a5`  
Slug: `the-finchrender-render-farm-coordinator-is-being-migrated-to`  
Latest archive: `537f2158-beb1-4c07-bfcf-a4abb2d4f8a5_submission_2026-07-13T05_19_11.107Z.zip`  
Revisions in Dropbox: 3

## Task summary

The FinchRender render-farm coordinator is being migrated to systemd. Under `/app/docs/` you will find an operations dossier, a migration requirements spec, and an architecture overview. Under `/app/traces/` are strace and lsof captures from the coordinator's startup and steady-state operation. Under `/app/legacy/` are the original YAML and TOML configuration files. Implement `/app/src/extract.ts` (and any helpers you need under `/app/src/`) so that running

Required artifacts include: `/app/docs/`, `/app/traces/`, `/app/legacy/`, `/app/src/extract.ts`, `/app/src/`, `/app/src/cli.ts`, `/app/output/contracts.json`, `/app/docs/ops-dossier.md`.

Author Anonymous tagged this **hard** system-administration task (systemd, strace, lsof, migration, long-context, syscall-audit).

Time estimates: expert ~90.0 min, junior ~270.0 min.

Harbor timeouts: agent Nones, verifier Nones.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `537f2158-beb1-4c07-bfcf-a4abb2d4f8a5_submission_2026-07-13T05_19_11.107Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
