# Registry data and analysis configuration

## Registry

`/app/data/registry.csv` has one row per patient with these columns:

- `row_id`: stable positive integer identifier, unique per row.
- `age`: age in years at cohort entry.
- `sex`: recorded sex, either `F` or `M`.
- `hgb`: haemoglobin (g/dL) at entry. May be blank (missing).
- `creat`: serum creatinine (mg/dL) at entry. May be blank (missing).
- `mspike`: size of the monoclonal serum protein spike (g/dL). May be blank.
- `ptime`: months from entry to progression (PCM) or last progression-free contact.
- `pstat`: `1` when progression (PCM) was observed, `0` otherwise.
- `futime`: months from entry to death or last contact.
- `death`: `1` when death was observed, `0` otherwise.

### Labelled (active) vs held-out patients

A patient is **held-out** exactly when the four outcome columns `ptime`,
`pstat`, `futime`, `death` are all blank. Held-out rows keep `row_id` and their
covariates (`age`, `sex`, `hgb`, `creat`, `mspike`). Every other patient is
**active** and carries complete outcomes. Fit all estimators and models on the
active patients only; the held-out patients are the prediction targets.

For an active progressed patient (`pstat == 1`), `futime >= ptime`. `age`,
`ptime`, `futime` are positive; multiple events may share a month (ties occur).

### Missing covariates

`hgb`, `creat`, `mspike` may be blank for active or held-out patients. Impute a
blank covariate with the **median of that covariate over the active patients**
before any standardization or model fitting.

## Configuration

`/app/config/analysis.csv` has columns `parameter,value` with one `age_cutpoint`
row and exactly two `horizon` rows. Horizons are positive, strictly increasing
in file order, and are the two prediction/reporting time points (in months).

Environment overrides are full paths:

- `DATA_PATH` defaults to `/app/data/registry.csv`
- `CONFIG_PATH` defaults to `/app/config/analysis.csv`
- `OUTPUT_PATH` defaults to `/app/outputs`
