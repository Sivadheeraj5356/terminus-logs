# Configure Lua PCA Analysis with DuckDB SQL Assertions

The automated machine learning pipeline is failing its verification step. A Makefile drives a Lua workflow that fetches the `scikit-learn/iris` dataset from a local HTTP mock server, loads it into DuckDB, computes covariance and PCA eigenvalues natively in Lua, and writes the results back to the database. Finally, a SQL script executes strict assertions.

The pipeline currently suffers from robustness issues and incorrect outputs. Your task is to diagnose and fix all issues preventing the pipeline from reliably processing data and passing the assertions. The pipeline must handle network failures and data format variations, accurately perform the required calculations, and write the output files correctly.

**Database Deliverables:** 
Fix the pipeline so it passes the SQL assertions and generates exactly two files: `/app/iris.duckdb` and `/app/dataset.csv`. The DuckDB tables must use `DOUBLE` precision for floats and conform exactly to this schema:
1. `covariance` (i INT, j INT, val DOUBLE): The 3x3 covariance matrix.
2. `pca` (component INT, eigenvalue DOUBLE): The top 2 eigenvalues, sorted descending.
3. `metrics` (name VARCHAR, value DOUBLE): A table containing a single row where name='trace' and value is the matrix trace calculated specifically by calling `trace_ext.compute_trace()`.

## Notes
- The pipeline should use the first column (`sepal_length` at column index 0) as a sample weight for the covariance matrix. Use the unbiased weighted covariance formula `sum(w) / (sum(w)^2 - sum(w^2)) * Σ w_i (x_i - μ_w)(x_i - μ_w)^T`.
- Ensure the network fetching handles transient 503 errors and avoids redundant downloads by utilizing conditional HTTP caching semantics.
- The dataset always lands at `dataset.csv`; the Makefile must not let an externally set `DATA_FILE` environment variable (e.g. `DATA_FILE=corrupted.csv`) redirect where data is fetched or read.
- The parser must gracefully handle adversarial formats such as UTF-8 BOM, random noise/junk strings, 'NA' and empty-string missing values, Windows carriage returns (CRLF), and unexpected zero-variance columns (e.g., `petal_width`).
- The full pipeline contract, including schema details and the weighted-covariance math, is documented in `environment/docs/pipeline.md`; follow it when the instruction and implementation details need a tie-breaker.
