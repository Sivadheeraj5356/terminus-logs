#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=shared_paths.sh
source "$SCRIPT_DIR/shared_paths.sh"

API_URL="$DEFAULT_API_URL"
BATCH_ID=""
DATA="$DEFAULT_TRAINING_DATA"
ARTIFACTS_DIR="$DEFAULT_ARTIFACTS_DIR"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-url) API_URL="$2"; shift 2 ;;
    --batch-id) BATCH_ID="$2"; shift 2 ;;
    --data) DATA="$2"; shift 2 ;;
    --artifacts-dir) ARTIFACTS_DIR="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done
[[ -n "$BATCH_ID" ]] || { echo "missing required option: --batch-id" >&2; exit 1; }

export API_URL BATCH_ID DATA ARTIFACTS_DIR
python3 - <<'PY'
import hashlib
import json
import math
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import requests
from scipy.stats import ks_2samp

FEATURES = ["feature_0", "feature_1", "feature_2", "feature_3"]
artifacts = Path(os.environ["ARTIFACTS_DIR"])
config = json.loads(Path("/app/config/repro_config.json").read_text())
metrics = json.loads((artifacts / "metrics.json").read_text())
profile = json.loads((artifacts / "drift_profile.json").read_text())
model = joblib.load(artifacts / "model.joblib")
response = requests.get(
    f"{os.environ['API_URL'].rstrip('/')}/inference-batches/{os.environ['BATCH_ID']}/",
    timeout=30,
)
response.raise_for_status()
records = sorted(response.json()["records"], key=lambda record: int(record["id"]))
batch = pd.DataFrame([record["features"] for record in records], columns=FEATURES)
positive_index = list(model.classes_).index(metrics["positive_class"])
probabilities = model.predict_proba(batch)[:, positive_index]
predictions = (probabilities >= metrics["decision_threshold"]).astype(int)
transcript = "".join(
    f"{record['id']}:{probability:.12f}:{prediction}\n"
    for record, probability, prediction in zip(records, probabilities, predictions, strict=True)
).encode()
feature_stats = {}
drifted_features = []
reference = pd.read_parquet(os.environ["DATA"])
for feature in FEATURES:
    ks = float(ks_2samp(reference[feature], batch[feature]).statistic)
    feature_profile = profile["features"][feature]
    cuts = np.asarray(feature_profile["cut_points"], dtype=float)
    assignments = np.searchsorted(cuts, batch[feature].to_numpy(), side="left")
    actual = np.bincount(assignments, minlength=len(cuts) + 1) / len(batch)
    psi = 0.0
    for expected_raw, actual_raw in zip(feature_profile["bin_proportions"], actual, strict=True):
        expected = max(float(expected_raw), config["psi_epsilon"])
        observed = max(float(actual_raw), config["psi_epsilon"])
        psi += (observed - expected) * math.log(observed / expected)
    drifted = ks > config["drift_ks_threshold"] or psi > config["drift_psi_threshold"]
    feature_stats[feature] = {
        "mean": float(batch[feature].mean()),
        "std": float(batch[feature].std(ddof=0)),
        "ks_statistic": ks,
        "psi": float(psi),
        "drifted": drifted,
    }
    if drifted:
        drifted_features.append(feature)
payload = {
    "batch_id": os.environ["BATCH_ID"],
    "model_version": metrics["model_version"],
    "champion": metrics["champion"],
    "training_oof_f1": metrics["oof_f1"],
    "decision_threshold": metrics["decision_threshold"],
    "prediction_count": len(predictions),
    "positive_predictions": int(predictions.sum()),
    "mean_positive_probability": float(probabilities.mean()),
    "prediction_digest": "sha256:" + hashlib.sha256(transcript).hexdigest(),
    "drift_detected": len(drifted_features) >= config["drift_feature_quorum"],
    "drifted_features": drifted_features,
    "feature_stats": feature_stats,
}
submitted = requests.post(
    f"{os.environ['API_URL'].rstrip('/')}/drift-evaluations/",
    json=payload,
    timeout=30,
)
submitted.raise_for_status()
print(f"submitted drift evaluation id {submitted.json()['id']}")
PY
