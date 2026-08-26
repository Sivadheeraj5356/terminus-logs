# Each structure in this dataset is a small square integer scalar field sampled on

Submission: `494c10a4-88c1-4e7f-80d9-acdb95de0926`  
Slug: `each-structure-in-this-dataset-is-a-small-square-integer-sca`  
Latest archive: `494c10a4-88c1-4e7f-80d9-acdb95de0926_submission_2026-07-19T19_44_52.318Z.zip`  
Revisions: 4

## Task summary

Each structure in this dataset is a small square integer scalar field sampled on a triangulated grid, the kind of coarse height map or density slice that arises in shape analysis. Its shape is summarized by a topological signature read from the persistence of the field: as a threshold sweeps through the values, connected components and loops are born and later die, and the spans from birth to death encode the structure's fold. This is a fold-recognition problem. Each reference structure carries a known fold group; the queries do not. For each query, compute its integer topological persistence signature, compare that signature to the signature of every reference under an L1 distance, and assign the query the fold group of the nearest reference.

Required artifacts include: `/app/data`, `/app/docs/contract.md`, `/app/analyze`.

Author anonymous tagged this **medium** machine-learning task (shape-classification, topological-data-analysis, persistent-homology, scalar-field, fold-recognition, nearest-neighbor).

Time estimates: expert ~240 min, junior ~540 min.

Harbor timeouts: agent 1200.0s, verifier 1200.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `494c10a4-88c1-4e7f-80d9-acdb95de0926_submission_2026-07-19T19_44_52.318Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
