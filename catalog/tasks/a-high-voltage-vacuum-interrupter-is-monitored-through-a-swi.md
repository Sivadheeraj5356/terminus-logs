# A high-voltage vacuum interrupter is monitored through a switching window while 

Submission: `7356ac80-ef38-43ec-a2fa-8d66117cf29e`  
Slug: `a-high-voltage-vacuum-interrupter-is-monitored-through-a-swi`  
Latest archive: `7356ac80-ef38-43ec-a2fa-8d66117cf29e_submission_2026-07-16T11_31_53.455Z.zip`  
Revisions in Dropbox: 12

## Task summary

A high-voltage vacuum interrupter is monitored through a switching window while contact current, chamber pressure, and contact gap drift between instrument samples. Complete the C++17 numerical model in `/app/src/main.cpp` so the existing `/app/Makefile` builds `/app/arcguard`; the self-contained executable must perform the reconstruction without helper processes, read newline-delimited JSON from stdin, and print one JSON array of operating spans to stdout. The first line is `{"window_start":T0,"window_end":T1,"strike_level":SL,"clear_level":CL,"current_weight":CW,"pressure_weight":PW,"gap_weight":GW,"current_slope":CS,"pressure_slope":PS,"gap_slope":GS,"conditioning_relief":CR,"qualify_sec":QS,"erosion_limit":EL,"start_current":SI,"start_pressure":SP,"start_gap":SG}` with `clear_level < strike_level`. Later lines are `{"t":TS,"kind":"current_sample","value":V}`, `{"t":TS,"kind":"pressure_sample","value":V}`, `{"t":TS,"kind":"gap_sample","value":V}`, `{"t":TS,"kind":"conditioning_on"}`, or `{"t":TS,"kind":"conditioning_off"}`. The three sampled quantities reset only on their matching sample and otherwise advance at their named slopes per second, including during conditioning. At the smallest remaining event time, collect all events no more than `1e-9` later, advance to that smallest time, then apply that group in original input-line order. The instantaneous dielectric stress is `current_weight*current^2 + pressure_weight*pressure^2 - gap_weight*gap - conditioning_relief` while conditioning is on, and the same expression without the final relief otherwise. This task is...

Required artifacts include: `/app/src/main.cpp`, `/app/Makefile`, `/app/arcguard`.

Author anonymous tagged this **hard** scientific-computing task (high-voltage, vacuum-interrupter, continuous-time, dielectric-physics, numerical-modeling).

Time estimates: expert ~100 min, junior ~300 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `7356ac80-ef38-43ec-a2fa-8d66117cf29e_submission_2026-07-16T11_31_53.455Z.zip` is a task submission, not a Harbor job. 12 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
