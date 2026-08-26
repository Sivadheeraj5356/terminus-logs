# Fleet rollout desk token k9sa7r for systemd host daemon lifecycle. Rollout stage

Submission: `71e0f726-9b33-4a8b-bc79-14e1e3fa4f27`  
Slug: `fleet-rollout-desk-token-k9sa7r-for-systemd-host-daemon-life`  
Latest archive: `71e0f726-9b33-4a8b-bc79-14e1e3fa4f27_submission_2026-07-13T09_26_00.198Z.zip`  
Revisions: 3

## Task summary

Fleet rollout desk token k9sa7r for systemd host daemon lifecycle. Rollout stages, daemon lifecycle rules, topology drift envelopes, and operational report seals are documented in /app/docs/system-administration-workflow.md. Operator commands live in /app/docs/fleet-operator-commands.md. Field contracts for the graded desk-trace live in /app/docs/k9_contract.md. Linux fleet operators publish a socket-activation start-race operational report for host daemons that receive file-descriptor pass handoffs. In this desk, a desk is the operations console that coordinates per-scenario daemon starts; socket-activation means systemd brings a daemon up when its listener socket accepts work; the k9 tools are the fleet operator binaries that invoke a scenario, recover checkpoint state, and emit the operational seal. The working baseline under /app/environment already builds those tools. Implement the fleet rollout workflow so /app/environment/tools/k9_invoke, /app/environment/tools/k9_recover, and /app/environment/tools/k9_emit produce /app/output/k9_trace.json from fixtures under /app/cases/seq into /app/desk-state.

Required artifacts include: `/app/docs/system-administration-workflow.md`, `/app/docs/fleet-operator-commands.md`, `/app/docs/k9_contract.md`, `/app/environment`, `/app/environment/tools/k9_invoke`, `/app/environment/tools/k9_recover`, `/app/environment/tools/k9_emit`, `/app/output/k9_trace.json`.

Author anonymous tagged this **hard** system-administration task (rust, systemd, socket-activation, daemon-lifecycle, fleet-rollout, topology, operational, host).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `71e0f726-9b33-4a8b-bc79-14e1e3fa4f27_submission_2026-07-13T09_26_00.198Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
