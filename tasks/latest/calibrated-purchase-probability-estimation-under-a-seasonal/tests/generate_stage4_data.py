"""Deterministic fourth variant: independent subsample and multiplicative jitter.

An independent 12 percent row drop (seed distinct from the other variants)
changes the unscored set again, so a pipeline whose numbers were hardcoded or
whose adaptation does not derive from the active data no longer matches the
reference recomputed on this variant. Multiplicative jitter on the duration and
page-value features forces a genuine refit. row_id is an explicit column and is
preserved, so the surviving unscored rows still key into /tests/labels.csv.
ProductRelated is untouched, so the engagement bands are stable; categorical
columns are untouched.
"""

import numpy as np
import pandas as pd

DATA = "/app/environment/data/online_shoppers.csv"
SEED = 31415927


def main():
    rng = np.random.default_rng(SEED)
    df = pd.read_csv(DATA)
    if "row_id" not in df.columns:
        raise KeyError("row_id column missing from data file")
    keep = rng.random(len(df)) >= 0.12
    df = df.loc[keep].reset_index(drop=True)
    for col in [
        "Administrative_Duration",
        "Informational_Duration",
        "ProductRelated_Duration",
        "PageValues",
    ]:
        values = df[col].astype(float).to_numpy()
        df[col] = np.round(values * (1.0 + rng.normal(0.0, 0.02, len(df))), 4)
    df["target"] = df["target"].map(lambda v: "" if pd.isna(v) else str(int(v)))
    df.to_csv(DATA, index=False)


if __name__ == "__main__":
    main()
