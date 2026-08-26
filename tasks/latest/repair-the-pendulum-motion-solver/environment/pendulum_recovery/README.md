# Pendulum motion recovery

The `/app` tree ships a seeded capture store, a read only report CLI, and `schema.sql` documenting the input and output contracts for the damped oscillator experiment.

## Solver deliverable

Create `recover_motion.py` in `/app`. When executed from `/app`, it should:

1. open `pendulum_captures.duckdb` (often referenced as `DB_PATH` in solver code);
2. process pending capture rows in ascending `job_id` order;
3. decode each montage, track the bob, fit damped oscillation parameters, and write the output tables and graph files named in `schema.sql`, including
   `recovery_graph.dot` (`DOT_PATH`) and `recovery_graph.svg` (`SVG_PATH`);
4. mark completed rows `done`.

Example:

```bash
python3 recover_motion.py
python3 /app/environment/pendulum_recovery/report.py
```

## Layout

| File | Purpose |
| --- | --- |
| `pendulum_captures.duckdb` | Seeded capture store with PNG montage blobs. |
| `schema.sql` | Input/output DDL and column contract. |
| `report.py` | Read only stdout summary of fitted parameters. |
| `recovery_graph.dot` | Graphviz audit diagram of per frame nodes. |
| `recovery_graph.svg` | Rendered SVG view of the diagram. |

## Numerical contract

`schema.sql` documents the output tables. `fit_results` carries `frequency_hz`,
`decay_per_second`, and `rejected_frames` per capture. `recovery_edges` records one
accepted or rejected row per frame. Verification applies relative error tolerances
of `0.05` on `frequency_hz` and `0.10` on `decay_per_second`.
