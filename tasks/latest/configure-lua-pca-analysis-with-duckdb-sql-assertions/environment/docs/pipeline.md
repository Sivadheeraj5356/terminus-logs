# Pipeline Contract

## Table Schemas

1. **`covariance`**
   - `i` (INTEGER): Row index (1-3)
   - `j` (INTEGER): Column index (1-3)
   - `val` (DOUBLE): Covariance value

2. **`pca`**
   - `component` (INTEGER): Principal component index (1-2)
   - `eigenvalue` (DOUBLE): Eigenvalue of the principal component

3. **`metrics`**
   - `name` (VARCHAR): Metric name (e.g. 'trace')
   - `value` (DOUBLE): Metric value

## Expectations

1. **Covariance Mathematics**: The first column (`sepal_length`) is the weight vector. The pipeline calculates the **unbiased weighted sample covariance** matrix (3x3) over the remaining 3 feature columns.
2. **Missing Data**: The pipeline must be robust to missing data and adversarial file encodings. A missing value in a feature column is imputed with that column's own arithmetic mean over the rows where the value is present — an unweighted mean computed independently of the sample-weight column, before the weighted covariance step runs.
3. **Eigenvalues & Trace**: The top two PCA eigenvalues must be extracted from the 3x3 weighted covariance matrix. Additionally, the pipeline MUST compute the trace of the covariance matrix using the compiled C-extension and store it in the `metrics` table.
4. **Data Freshness**: The `make run` target must always use the latest dataset when the upstream HTTP server serves a newer version, even if `dataset.csv` exists locally.
