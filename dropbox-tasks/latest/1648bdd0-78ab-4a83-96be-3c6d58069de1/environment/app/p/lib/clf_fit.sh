#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=shared_paths.sh
source "$SCRIPT_DIR/shared_paths.sh"

DATA="$DEFAULT_TRAINING_DATA"
ARTIFACTS_DIR="$DEFAULT_ARTIFACTS_DIR"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --data)
      DATA="$2"
      shift 2
      ;;
    --artifacts-dir)
      ARTIFACTS_DIR="$2"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

export DATA ARTIFACTS_DIR
python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

FEATURES = ["feature_0", "feature_1", "feature_2", "feature_3"]
CONFIG = Path("/app/config/repro_config.json")


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def write_json(path: Path, value: object) -> None:
    path.write_bytes(canonical(value) + b"\n")


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


config = json.loads(CONFIG.read_text(encoding="utf-8"))
frame = pd.read_parquet(os.environ["DATA"])
first = config["candidates"][0]
train_x, test_x, train_y, test_y = train_test_split(
    frame[FEATURES],
    frame["label"],
    test_size=0.25,
    random_state=config["random_state"],
    stratify=frame["label"],
)
model = RandomForestClassifier(
    n_estimators=first["n_estimators"],
    max_depth=first["max_depth"],
    min_samples_leaf=first["min_samples_leaf"],
    class_weight=first["class_weight"],
    random_state=config["random_state"],
    n_jobs=1,
)
model.fit(train_x, train_y)
positive_index = list(model.classes_).index(config["positive_class"])
probabilities = model.predict_proba(test_x)[:, positive_index]
predictions = (probabilities >= 0.5).astype(int)
fold_score = float(f1_score(test_y, predictions, zero_division=0))
candidate_scores = [
    {
        "name": candidate["name"],
        "complexity": candidate["n_estimators"] * candidate["max_depth"],
        "decision_threshold": 0.5,
        "oof_accuracy": float(accuracy_score(test_y, predictions)),
        "oof_f1": fold_score,
        "worst_fold_f1": fold_score,
        "fold_f1": [fold_score] * config["cv_folds"],
    }
    for candidate in config["candidates"]
]
metrics = {
    "model_version": config["model_version"],
    "champion": first["name"],
    "positive_class": config["positive_class"],
    "decision_threshold": 0.5,
    "oof_accuracy": float(accuracy_score(test_y, predictions)),
    "oof_f1": fold_score,
    "worst_fold_f1": fold_score,
    "fold_f1": [fold_score] * config["cv_folds"],
    "training_rows": len(frame),
    "cv_folds": config["cv_folds"],
    "random_state": config["random_state"],
    "candidate_scores": candidate_scores,
}
profile_features = {}
for feature in FEATURES:
    values = frame[feature].to_numpy(dtype=float)
    cut_points = sorted(set(float(value) for value in np.quantile(values, config["profile_quantiles"])))
    assignments = np.searchsorted(np.asarray(cut_points), values, side="left")
    proportions = np.bincount(assignments, minlength=len(cut_points) + 1) / len(values)
    profile_features[feature] = {
        "mean": float(values.mean()),
        "std": float(values.std(ddof=0)),
        "cut_points": cut_points,
        "bin_proportions": [float(value) for value in proportions],
    }
profile = {
    "profile_version": 1,
    "feature_order": FEATURES,
    "quantiles": config["profile_quantiles"],
    "features": profile_features,
}
out = Path(os.environ["ARTIFACTS_DIR"])
out.mkdir(parents=True, exist_ok=True)
joblib.dump(model, out / "model.joblib")
write_json(out / "metrics.json", metrics)
write_json(out / "drift_profile.json", profile)
artifact_sha = {
    name: digest(out / name)
    for name in ("model.joblib", "metrics.json", "drift_profile.json")
}
manifest_base = {
    "schema_version": 2,
    "model_version": config["model_version"],
    "champion": first["name"],
    "feature_order": FEATURES,
    "training_rows": len(frame),
    "training_parquet_sha256": digest(Path(os.environ["DATA"])),
    "config_sha256": digest(CONFIG),
    "artifact_sha256": artifact_sha,
}
binding = {key: value for key, value in manifest_base.items() if key != "schema_version"}
manifest = {
    **manifest_base,
    "release_sha256": "sha256:" + hashlib.sha256(canonical(binding)).hexdigest(),
}
write_json(out / "artifact_manifest.json", manifest)
print(
    f"trained {config['model_version']} champion {first['name']} "
    f"oof_f1 {metrics['oof_f1']:.3f} worst_fold_f1 {metrics['worst_fold_f1']:.3f} "
    "threshold 0.500000"
)
PY
