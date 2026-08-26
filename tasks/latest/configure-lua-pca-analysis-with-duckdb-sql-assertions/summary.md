# # Configure Lua PCA Analysis with DuckDB SQL Assertions

- **UUID:** `27a17a21-a389-4a33-a5f5-ebc7a085e901`
- **Slug:** `configure-lua-pca-analysis-with-duckdb-sql-assertions`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

The automated machine learning pipeline is failing its verification step. A Makefile drives a Lua workflow that fetches the `scikit-learn/iris` dataset from a local HTTP mock server, loads it into DuckDB, computes covariance and PCA eigenvalues natively in Lua, and writes the results back to the database.

Finally, a SQL script executes strict assertions. The pipeline currently suffers from robustness issues and incorrect outputs.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
