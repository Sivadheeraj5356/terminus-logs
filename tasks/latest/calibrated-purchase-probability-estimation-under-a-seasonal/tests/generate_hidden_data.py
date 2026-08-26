"""Deterministic hidden variant: subsample rows and jitter numeric inputs.

Dropping 15 percent of all rows (source, pilot and unscored alike) changes the
unscored row set, so hardcoded prediction files fail the coverage check; the
duration jitter forces a genuine refit. row_id is an explicit column and is
preserved, so the surviving unscored rows still key into /tests/labels.csv.
ProductRelated is untouched, so the engagement bands are stable, and the verifier
recomputes its reference model and every band statistic on this same variant.
Categorical columns are untouched.
"""

import numpy as np
import pandas as pd

DATA = "/app/environment/data/online_shoppers.csv"
SEED = 20260713


def main():
    rng = np.random.default_rng(SEED)
    df = pd.read_csv(DATA)
    if "row_id" not in df.columns:
        raise KeyError("row_id column missing from data file")
    keep = rng.random(len(df)) >= 0.15
    df = df.loc[keep].reset_index(drop=True)
    for col in [
        "Administrative_Duration",
        "Informational_Duration",
        "ProductRelated_Duration",
    ]:
        values = df[col].astype(float).to_numpy()
        df[col] = np.round(values * (1.0 + rng.normal(0.0, 0.03, len(df))), 4)
    df["target"] = df["target"].map(lambda v: "" if pd.isna(v) else str(int(v)))
    df.to_csv(DATA, index=False)


if __name__ == "__main__":
    main()
