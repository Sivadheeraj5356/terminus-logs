from pathlib import Path

import pandas as pd
from sklearn.datasets import make_classification

FEATURES = ["feature_0", "feature_1", "feature_2", "feature_3"]
OUTPUT = Path("/app/data/training.parquet")


def main() -> None:
    features, labels = make_classification(
        n_samples=240,
        n_features=4,
        n_informative=4,
        n_redundant=0,
        weights=[0.61, 0.39],
        class_sep=0.9,
        random_state=31415,
    )
    frame = pd.DataFrame(features, columns=FEATURES)
    frame.insert(0, "id", range(5001, 5001 + len(frame)))
    frame["label"] = labels.astype(int)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(OUTPUT, index=False)


if __name__ == "__main__":
    main()
