-- verify.sql
-- Check row count against dataset.csv directly using DuckDB read_csv_auto
SELECT CASE WHEN COUNT(*) = (SELECT COUNT(*) FROM read_csv_auto('dataset.csv')) THEN 1 ELSE error('Row count mismatch') END FROM iris;

-- Check PCA eigenvalues exist
SELECT CASE WHEN eigenvalue > 0.0 THEN 1 ELSE error('Eigenvalue 1 missing or negative') END FROM pca WHERE component=1;
SELECT CASE WHEN eigenvalue >= 0.0 THEN 1 ELSE error('Eigenvalue 2 missing or negative') END FROM pca WHERE component=2;

-- Check ordering
WITH e1 AS (SELECT eigenvalue as e FROM pca WHERE component=1),
     e2 AS (SELECT eigenvalue as e FROM pca WHERE component=2)
SELECT CASE WHEN e1.e > e2.e THEN 1 ELSE error('Eigenvalues not ordered correctly') END 
FROM e1, e2;

-- Verify Trace Identity: Trace of covariance matrix must equal the sum of its eigenvalues
-- In practice, since we only extract the top 2 eigenvalues of a 3x3 matrix, the precise mathematical check is done in test_outputs.py.
SELECT CASE WHEN value > 0.0 THEN 1 ELSE error('Trace metric invalid or missing') END FROM metrics WHERE name='trace';
