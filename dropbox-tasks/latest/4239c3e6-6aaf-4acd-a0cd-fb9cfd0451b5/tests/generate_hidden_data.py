"""Deterministic hidden variant: subsample rows and jitter numeric inputs.

Dropping 15 percent of all rows (training and held-out alike) changes the held-out
row set, so hardcoded prediction files fail the coverage check; the
age/campaign/cons.conf.idx jitter forces a genuine refit. row_id is an explicit
column and is preserved, so the surviving held-out rows still key into
/tests/labels.csv. The education column is untouched, so the subgroup partition is
stable, and the verifier recomputes its reference model and every subgroup
statistic on this same variant. Categorical columns are untouched.
"""

import numpy as np
import pandas as pd

DATA = "/app/environment/data/bank_additional.csv"
SEED = 20260717


def main():
    rng = np.random.default_rng(SEED)
    df = pd.read_csv(DATA)
    if "row_id" not in df.columns:
        raise KeyError("row_id column missing from data file")
    keep = rng.random(len(df)) >= 0.15
    df = df.loc[keep].reset_index(drop=True)
    for col in ["age", "campaign", "cons.conf.idx"]:
        values = df[col].astype(float).to_numpy()
        df[col] = np.round(values * (1.0 + rng.normal(0.0, 0.03, len(df))), 4)
    df.to_csv(DATA, index=False)


if __name__ == "__main__":
    main()
