# A transit authority runs several bus lines that all share one common headway: ev

Submission: `a9ecc381-19d3-4e47-ba9d-80a185d149bb`  
Slug: `a-transit-authority-runs-several-bus-lines-that-all-share-on`  
Latest archive: `a9ecc381-19d3-4e47-ba9d-80a185d149bb_submission_2026-07-17T10_21_26.372Z.zip`  
Revisions: 1

## Task summary

A transit authority runs several bus lines that all share one common headway: every line repeats on the same fixed cycle length, and the only thing left to decide for each line is its departure offset within that cycle. Every line calls at one interchange, landing at a platform of the concourse partway through its run and pulling out again from another platform a little later, both at times fixed by the line's offset plus its known running times. Each row of the transfer list is a body of passengers off one line who want another. They have to cross the concourse on foot, and that walk eats into the time they have to make the connection; the interchange's passage map gives the time of each passage running directly between a pair of platforms, in a building that grew piecemeal and confines nobody to a single passage. A connection is comfortable when the connecting bus pulls out a short, comfortable interval after its passengers reach its platform; because the timetable is cyclic, that interval is measured around the cycle, so a connection can be good even when the departure clock time is earlier than the arrival. Rows are grouped into passenger flows. A flow appearing in more than one row is one body of people offered a choice of connecting lines: they travel together and ride one bus. Nobody is dispatching them, and they get on the first bus they can catch: of the connections open to them they ride one that pulls out as soon as any of them does. The authority cannot wave them onto a later bus to keep an earlier one free, and cannot hold them back while a heavier crowd...

Required artifacts include: `/app/model.mzn`, `/app/instance.dzn`, `/app/docs/problem.md`, `/app/docs/data_dictionary.md`, `/app/docs/output_format.md`, `/app/run_model.sh`.

Author anonymous tagged this **hard** scientific-computing task (optimization, operations-research, scheduling, constraint-programming, minizinc).

Time estimates: expert ~40 min, junior ~120 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `a9ecc381-19d3-4e47-ba9d-80a185d149bb_submission_2026-07-17T10_21_26.372Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
