# After planned maintenance on a two-node highly available pair, automated failbac

Submission: `f7c2b75b-dc84-4210-b261-1db82d0eac44`  
Slug: `after-planned-maintenance-on-a-two-node-highly-available-pai`  
Latest archive: `f7c2b75b-dc84-4210-b261-1db82d0eac44_submission_2026-07-20T04_20_14.241Z.zip`  
Revisions in Dropbox: 5

## Task summary

After planned maintenance on a two-node highly available pair, automated failback brings the floating service endpoint back on the preferred node. Health probes on the VIP in `/app/environment/configs/pair.toml` stay green, yet downstream clients report intermittent reachability failures for several minutes when the maintenance window closes. Operator exports from maintenance returns list `endpoint_attach` ahead of `neighbor_replay` in `gate_timings`. A supervisor reload (`vivostep reopen`) leaves `vivostep examine --surface dual` with mismatched forwarding and journal epochs on the next maintenance return. The wp-maint cold boot path alone shows aligned dual epochs.

Required artifacts include: `/app/environment/configs/pair.toml`, `/app/environment`, `/app/environment/docs/toolchain.md`, `/app/output/wp_report.json`, `/app/environment/docs/contract.md`, `/app/environment/docs/coordination.md`, `/app/environment/docs/operations.md`, `/app/environment/scripts/run_failback_check.sh`.

Author anonymous tagged this **hard** system-administration task (ha-failback, neighbor-cache, go, operator-cli, vivostep).

Time estimates: expert ~45 min, junior ~150 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `f7c2b75b-dc84-4210-b261-1db82d0eac44_submission_2026-07-20T04_20_14.241Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
