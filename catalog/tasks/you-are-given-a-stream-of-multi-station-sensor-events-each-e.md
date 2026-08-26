# You are given a stream of multi-station sensor events. Each event carries readin

Submission: `b202229b-72e6-4d7a-b964-6cca80d66970`  
Slug: `you-are-given-a-stream-of-multi-station-sensor-events-each-e`  
Latest archive: `b202229b-72e6-4d7a-b964-6cca80d66970_submission_2026-07-18T10_35_22.946Z.zip`  
Revisions: 1

## Task summary

You are given a stream of multi-station sensor events. Each event carries readings for a set of features (one per station) plus a target. Stations come and go: a feature is out of schema when its cell is empty, and can start reporting later. Run one online ridge (recursive least squares) regressor whose dimension changes as features appear and disappear; report its predictions and retained state. The model shares one precision matrix across the active features, so they are coupled: retiring one changes the weights of the others. A newly reporting feature is added; one absent past a disclosed grace window is retired; one that returns after retirement starts over, never resuming its old state.

Required artifacts include: `/app/docs/CONTRACT.md`, `/app/run.sh`, `/app/Main.java`, `/app/data`.

Author anonymous tagged this **unknown** machine-learning task (streaming, online-learning, ridge-regression, schema-evolution, exact-arithmetic, delayed-labels).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `b202229b-72e6-4d7a-b964-6cca80d66970_submission_2026-07-18T10_35_22.946Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
