# Data dictionary

The records arrive as five comma-separated files in the directory named by the
environment variable `CAUSAL_DATA_DIR`, which defaults to `/app/data`. Every file
has one row per employee and joins to the others on `employee_id`. Per-variable
notes are under `docs/variables/`.

## baseline_covariates.csv

Pre-enrollment baseline measures recorded at the start of the year.

- `employee_id`: employee identifier (string).
- `age_index`: standardized age index.
- `bmi_index`: standardized body-mass index.
- `activity_index`: standardized physical-activity index.
- `chronic_index`: standardized chronic-condition burden index.
- `diet_index`: standardized diet-quality index.
- `sleep_index`: standardized sleep-quality index.
- `stress_index`: standardized stress-level index.
- `income_index`: standardized income index.

## tenure.csv

- `employee_id`: employee identifier.
- `tenure_years`: years the employee has been with the company at the start of the
  year.

## outreach.csv

- `employee_id`: employee identifier.
- `outreach_contacts`: number of program reminder contacts sent to the employee
  during the enrollment window.

## enrollment.csv

- `employee_id`: employee identifier.
- `enrolled`: 1 if the employee enrolled in the program, 0 otherwise.

## outcome.csv

- `employee_id`: employee identifier.
- `wellbeing_index`: end-of-year composite wellbeing score.
