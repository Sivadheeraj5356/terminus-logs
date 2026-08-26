# The lab's checkpointed integrator ships a broken `demo_engine` binary under `/ap

Submission: `2b91c159-9be4-4c7d-b84b-b6d07a60e069`  
Slug: `the-lab-s-checkpointed-integrator-ships-a-broken-demo-engine`  
Latest archive: `2b91c159-9be4-4c7d-b84b-b6d07a60e069_submission_2026-07-05T14_57_26.173Z.zip`  
Revisions: 1

## Task summary

The lab's checkpointed integrator ships a broken `demo_engine` binary under `/app/build`. Coupled defects across checkpoint restore, pair-evaluation ledger accounting, periodic wrap crossing tally, journal CRC folding, and wrap-epoch reduction leave recovery reports off-spec. Repair the C++ sources under `/app/environment` so a clean CMake release rebuild produces a deterministic emitter again. Run `/app/build/demo_engine emit <scene_token> /app/output/recovery_report.json` after rebuilding from `/app/environment`. Nine bundled trials use scene tokens `Q0` through `Q8`. Each emitted JSON must echo the requested `scene_token` and include integer fields `ledger_tail`, `wrap_epoch`, `refresh_stamp`, `segment_generation`, `journal_crc32`, plus floating `scalar_near` and `addon_aux`.

Required artifacts include: `/app/build`, `/app/environment`, `/app/build/demo_engine`, `/app/output/recovery_report.json`, `/app/environment/docs/integrator_semantics.md`, `/app/environment/scripts/emit_matrix.sh`, `/app/environment/docs/runtime_contract.txt`.

Author anonymous tagged this **hard** scientific-computing task (molecular-dynamics, checkpointing, periodic-boundaries, numerical-regression).

Time estimates: expert ~120 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `2b91c159-9be4-4c7d-b84b-b6d07a60e069_submission_2026-07-05T14_57_26.173Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
