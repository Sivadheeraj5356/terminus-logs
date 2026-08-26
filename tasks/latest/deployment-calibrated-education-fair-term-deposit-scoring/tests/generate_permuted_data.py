"""Permute only the protected attribute column.

A solution that never reads education produces byte-identical probabilities and
identical metrics on this variant. The education multiset and the row_id order are
preserved, so the held-out row set, the coverage check and the full-data subgroup
count are unchanged; only which education label sits on which contact changes.
"""

import numpy as np
import pandas as pd

DATA = "/app/environment/data/bank_additional.csv"
SEED = 20260717
PROTECTED = "education"


def main():
    rng = np.random.default_rng(SEED)
    df = pd.read_csv(DATA)
    if PROTECTED not in df.columns:
        raise KeyError("education column missing from data file")
    perm = rng.permutation(len(df))
    df[PROTECTED] = df[PROTECTED].to_numpy()[perm]
    df.to_csv(DATA, index=False)


if __name__ == "__main__":
    main()
