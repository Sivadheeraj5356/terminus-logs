"""Deterministic shift-amplification variant: skew the source composition.

Dropping 30 percent of the source-domain rows in the high-engagement band
(ProductRelated >= 21) skews the training composition away from the deployment
mix, so a pipeline whose numbers were hardcoded from the original file, or whose
shift handling does not derive from the active data, no longer matches the
reference recomputed on this variant. Target-domain rows, the pilot survey and
the unscored row set are untouched, and ProductRelated (the band key) is left
intact so the bands are stable.
"""

import numpy as np
import pandas as pd

DATA = "/app/environment/data/online_shoppers.csv"
SEED = 4242


def main():
    rng = np.random.default_rng(SEED)
    df = pd.read_csv(DATA)
    if "row_id" not in df.columns:
        raise KeyError("row_id column missing from data file")
    mask_hi = (df["domain"].astype(str) == "source") & (
        df["ProductRelated"].astype(float) >= 21
    )
    drop = rng.random(len(df)) < 0.30
    df = df.loc[~(mask_hi.to_numpy() & drop)].reset_index(drop=True)
    df["target"] = df["target"].map(lambda v: "" if pd.isna(v) else str(int(v)))
    df.to_csv(DATA, index=False)


if __name__ == "__main__":
    main()
