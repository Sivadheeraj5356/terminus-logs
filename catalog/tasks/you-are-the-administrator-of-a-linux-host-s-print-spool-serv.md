# You are the administrator of a Linux host's **print-spool service** — the system

Submission: `57793566-4577-40a6-a25e-6ccb14e3043a`  
Slug: `you-are-the-administrator-of-a-linux-host-s-print-spool-serv`  
Latest archive: `57793566-4577-40a6-a25e-6ccb14e3043a_submission_2026-07-17T04_50_25.483Z.zip`  
Revisions: 3

## Task summary

You are the administrator of a Linux host's **print-spool service** — the system daemon (in the spirit of `lpd`/CUPS) that drives the machine's print devices, manages the shared spool queue of pending jobs, enforces each user's page quota, and copes with device faults. Build `spoold`, the operator control tool that replays the service's operations journal and reports the resulting service state. The complete normative rules are in `/app/docs/spec.md` — read it carefully. Several administrative rules (quota accounting, device pause/resume, fair-share dispatch, fault handling, priority preemption) are stated deliberately and differ from a conventional priority print queue; the graded answer follows the stated rule, not the intuitive default. There is exactly one correct output per input.

Required artifacts include: `/app/docs/spec.md`, `/app/bin/spoold`, `/app/internal/sp/sp.go`, `/app/data/schedules/`, `/app/data/examples/`.

Author anonymous tagged this **hard** system-administration task (go, system-administration, print-spool, lpd, quota, preemption).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `57793566-4577-40a6-a25e-6ccb14e3043a_submission_2026-07-17T04_50_25.483Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
