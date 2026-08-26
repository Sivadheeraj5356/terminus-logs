# # Configure Lua PCA Analysis with DuckDB SQL Assertions

Submission: `27a17a21-a389-4a33-a5f5-ebc7a085e901`  
Slug: `configure-lua-pca-analysis-with-duckdb-sql-assertions`  
Latest archive: `27a17a21-a389-4a33-a5f5-ebc7a085e901_submission_2026-07-18T12_48_29.747Z.zip`  
Revisions: 1

## Task summary

The automated machine learning pipeline is failing its verification step. A Makefile drives a Lua workflow that fetches the `scikit-learn/iris` dataset from a local HTTP mock server, loads it into DuckDB, computes covariance and PCA eigenvalues natively in Lua, and writes the results back to the database. Finally, a SQL script executes strict assertions. The pipeline currently suffers from robustness issues and incorrect outputs. Your task is to diagnose and fix all issues preventing the pipeline from reliably processing data and passing the assertions. The pipeline must handle network failures and data format variations, accurately perform the required calculations, and write the output files correctly. Key requirements: `covariance` (i INT, j INT, val DOUBLE): The 3x3 covariance matrix.; `pca` (component INT, eigenvalue DOUBLE): The top 2 eigenvalues, sorted descending.; `metrics` (name VARCHAR, value DOUBLE): A table containing a single row where name='trace' and value is the matrix trace calculated specifically by calling `trace_ext.compute_trace()`..

Required artifacts include: `/app/iris.duckdb`, `/app/dataset.csv`.

Author Anonymous tagged this **hard** scientific-computing task (data-engineering, duckdb, pca, lua).

Time estimates: expert ~180.0 min, junior ~360.0 min.

Harbor timeouts: agent 1800.0s, verifier 420.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `27a17a21-a389-4a33-a5f5-ebc7a085e901_submission_2026-07-18T12_48_29.747Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
