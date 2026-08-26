# Ferry operations needs a crew-recovery plan for disrupted sailings before the ne

Submission: `a4dff906-8783-4950-b02d-21cc26de6adc`  
Slug: `ferry-operations-needs-a-crew-recovery-plan-for-disrupted-sa`  
Latest archive: `a4dff906-8783-4950-b02d-21cc26de6adc_submission_2026-07-05T08_28_15.832Z.zip`  
Revisions: 1

## Task summary

Ferry operations needs a crew-recovery plan for disrupted sailings before the next tide cycle closes. Submit one single standalone `.go` file with `package main` source under `/app` or `/tmp`; that file must compile by itself with `/usr/local/go/bin/go build <file>`, must not rely on companion Go files or modules, must accept `<input_dir> <output_dir>`, finish each run within 90 seconds, read the mounted files in `/app/task_file/input_data/`, and write only to `/app/task_file/output_data/`. The same solver must also handle two copied input directories: in one, `FERRY-0228` becomes a mandatory high-impact sailing for windows 2 through 4 and must be included with no hard-constraint errors and raw `total_score >= 0.780`; in the other, `FERRY-0189`, `FERRY-0203`, `FERRY-0217`, and `FERRY-0221` become mandatory high-impact sailings while vessel-class capacity in windows 3 and 4 is reduced by 2 each, and that stress run must include all four IDs, assign exactly 160 sailings, use all 24 window/base cells, protect at least 3,500,000 passenger-minutes, avoid hard-constraint errors, and reach raw `total_score >= 0.940`. The original-input strict subscore floors below apply only to the original mounted input. Create `/app/task_file/output_data/ferry_recovery_plan.jsonl`, one JSON object per assigned sailing, with exactly `sailing_id`, `crew_id`, `relief_terminal_id`, `recovery_window`, `priority_rank`, `handoff_mode`, and `rest_buffer_minutes`. `recovery_window` is an integer 1 through 6; `priority_rank` over assigned rows must be the permutation 1..N; `handoff_mode` must be...

Required artifacts include: `/app/task_file/input_data/`, `/app/task_file/output_data/`, `/app/task_file/output_data/ferry_recovery_plan.jsonl`, `/app/task_file/output_data/ferry_recovery_summary.json`, `/app/task_file/scripts/model.py`.

Author Anonymous tagged this **medium** data-processing task (ferry-operations, crew-recovery, scheduling, optimization, go).

Time estimates: expert ~150 min, junior ~900 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `a4dff906-8783-4950-b02d-21cc26de6adc_submission_2026-07-05T08_28_15.832Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
