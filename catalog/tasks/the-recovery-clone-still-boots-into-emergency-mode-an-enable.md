# The recovery clone still boots into emergency mode: an enabled target never gath

Submission: `75107261-854b-4092-9979-30b7987f7264`  
Slug: `the-recovery-clone-still-boots-into-emergency-mode-an-enable`  
Latest archive: `75107261-854b-4092-9979-30b7987f7264_submission_2026-07-19T08_42_01.722Z.zip`  
Revisions: 1

## Task summary

The recovery clone still boots into emergency mode: an enabled target never gathers its real dependency set, a masked mount is reported active, and the service that owns the data path is missing from the final membership list. Repair the captured-host reconciler so every published yard artifact matches the operating contracts on the public command the verifier invokes. Editable maintenance sources live under `/opt/boot_transaction_switchboard/rust_unitgraph_cells/` (installed for execution under `/app/rust_unitgraph_cells/`). The eight contracts in `/app/systemd_boot_contracts/` (mirrored under `/opt/boot_transaction_switchboard/systemd_boot_contracts/`) are normative. Decision tables and fallbacks wired through those cells must produce contract outcomes; rebuilding with the forge below is how the public launcher picks up your repair.

Required artifacts include: `/app/rust_unitgraph_cells/`, `/app/systemd_boot_contracts/`, `/app/boot_recovery_console/reconcile_boot_graph.sh`.

Author anonymous tagged this **hard** system-administration task (systemd-units, boot-transactions, service-enablement, recovery-operations).

Time estimates: expert ~300 min, junior ~600 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `75107261-854b-4092-9979-30b7987f7264_submission_2026-07-19T08_42_01.722Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
