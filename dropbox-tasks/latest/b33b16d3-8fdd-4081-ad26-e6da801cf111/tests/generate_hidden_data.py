#!/usr/bin/env python3
"""Deterministic hidden-data variant for climate-crashes-cloglog.

Adds a small seeded perturbation to every tuning-parameter column while leaving the
failure outcome and the row count unchanged, so a solution that hardcodes or recalls
the public UCI fit no longer matches the re-estimate. The row count is preserved so
the committed permutation index stays aligned with the data.
"""

from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path("/app/data/climate_crashes.csv")
SEED = 20260716


def main():
    rng = np.random.default_rng(SEED)
    d = pd.read_csv(DATA)
    predictors = [c for c in d.columns if c != "failure"]
    for c in predictors:
        sd = float(d[c].std(ddof=1))
        d[c] = d[c] + rng.normal(0.0, 0.05 * sd, size=len(d))
    d.to_csv(DATA, index=False)


if __name__ == "__main__":
    main()
