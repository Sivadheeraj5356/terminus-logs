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
import math
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold

FEATURES = ["feature_0", "feature_1", "feature_2", "feature_3"]
INPUT_COLUMNS = ["id", *FEATURES, "label"]
CORRELATION_PAIRS = [
    (FEATURES[left], FEATURES[right])
    for left in range(len(FEATURES))
    for right in range(left + 1, len(FEATURES))
]
CONFIG_PATH = Path("/app/config/repro_config.json")
ARTIFACT_NAMES = (
    "model.joblib",
    "calibrator.joblib",
    "metrics.json",
    "drift_profile.json",
)


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def write_json(path: Path, value: object) -> None:
    path.write_bytes(canonical_bytes(value) + b"\n")


def candidate_params(candidate: dict[str, Any], random_state: int) -> dict[str, Any]:
    return {
        "n_estimators": int(candidate["n_estimators"]),
        "max_depth": int(candidate["max_depth"]),
        "min_samples_leaf": int(candidate["min_samples_leaf"]),
        "class_weight": candidate["class_weight"],
        "random_state": random_state,
        "n_jobs": 1,
    }


def calibrator_params(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "C": float(config["calibration_c"]),
        "solver": "lbfgs",
        "max_iter": 1000,
    }


def validate_policy(config: dict[str, Any]) -> None:
    if config.get("classifier") != "RandomForestClassifier":
        raise ValueError("unsupported classifier policy")
    if config.get("positive_class") != 1:
        raise ValueError("positive_class must be integer one")
    if not isinstance(config.get("cv_folds"), int) or config["cv_folds"] < 2:
        raise ValueError("cv_folds must be at least two")
    if not isinstance(config.get("cv_repeats"), int) or config["cv_repeats"] < 2:
        raise ValueError("cv_repeats must be at least two")
    if not isinstance(config.get("random_state"), int):
        raise ValueError("random_state must be an integer")
    if (
        not isinstance(config.get("repeat_seed_stride"), int)
        or isinstance(config["repeat_seed_stride"], bool)
        or config["repeat_seed_stride"] <= config["cv_folds"]
    ):
        raise ValueError("repeat_seed_stride must exceed cv_folds")
    if config.get("calibration_method") != "sigmoid":
        raise ValueError("unsupported calibration method")
    calibration_c = config.get("calibration_c")
    if (
        isinstance(calibration_c, bool)
        or not isinstance(calibration_c, (int, float))
        or not math.isfinite(float(calibration_c))
        or float(calibration_c) <= 0
    ):
        raise ValueError("calibration_c must be positive finite numeric")
    if config.get("threshold_metric") != "f1":
        raise ValueError("unsupported threshold metric")
    if config.get("threshold_tie_break") != "highest":
        raise ValueError("unsupported threshold tie break")
    if config.get("champion_tie_break") != [
        "oof_f1",
        "lower_calibrated_brier",
        "worst_repeat_f1",
        "worst_fold_f1",
        "lower_complexity",
        "name",
    ]:
        raise ValueError("unsupported champion tie break")
    candidates = config.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("candidates must be a non-empty array")
    names = []
    for candidate in candidates:
        if set(candidate) != {
            "name",
            "n_estimators",
            "max_depth",
            "min_samples_leaf",
            "class_weight",
        }:
            raise ValueError("invalid candidate schema")
        names.append(candidate["name"])
        if not isinstance(candidate["name"], str) or not candidate["name"]:
            raise ValueError("candidate name must be non-empty")
        for key in ("n_estimators", "max_depth", "min_samples_leaf"):
            if not isinstance(candidate[key], int) or candidate[key] <= 0:
                raise ValueError(f"invalid candidate {key}")
        if candidate["class_weight"] not in (None, "balanced", "balanced_subsample"):
            raise ValueError("invalid class_weight")
    if len(names) != len(set(names)):
        raise ValueError("candidate names must be unique")
    quantiles = config.get("profile_quantiles")
    if (
        not isinstance(quantiles, list)
        or not quantiles
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 < float(value) < 1
            for value in quantiles
        )
        or [float(value) for value in quantiles]
        != sorted(set(float(value) for value in quantiles))
    ):
        raise ValueError("profile_quantiles must be sorted unique interior values")
    if config.get("profile_ddof") != 0:
        raise ValueError("profile_ddof must be zero")
    for key in (
        "psi_epsilon",
        "drift_ks_threshold",
        "drift_psi_threshold",
        "prediction_drift_psi_threshold",
        "disagreement_drift_psi_threshold",
    ):
        value = config.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) <= 0
        ):
            raise ValueError(f"invalid {key}")
    correlation_threshold = config.get("correlation_drift_threshold")
    if (
        isinstance(correlation_threshold, bool)
        or not isinstance(correlation_threshold, (int, float))
        or not math.isfinite(float(correlation_threshold))
        or not 0 <= float(correlation_threshold) <= 2
    ):
        raise ValueError("invalid correlation_drift_threshold")
    quorum = config.get("drift_feature_quorum")
    if not isinstance(quorum, int) or isinstance(quorum, bool) or not 1 <= quorum <= len(FEATURES):
        raise ValueError("invalid drift_feature_quorum")
    page_size = config.get("inference_page_size")
    if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size <= 0:
        raise ValueError("invalid inference_page_size")
    leaf_epsilon = config.get("leaf_js_epsilon")
    if (
        isinstance(leaf_epsilon, bool)
        or not isinstance(leaf_epsilon, (int, float))
        or not math.isfinite(float(leaf_epsilon))
        or not 0 < float(leaf_epsilon) < 1
    ):
        raise ValueError("invalid leaf_js_epsilon")
    leaf_quantile = config.get("leaf_drift_quantile")
    if (
        isinstance(leaf_quantile, bool)
        or not isinstance(leaf_quantile, (int, float))
        or not math.isfinite(float(leaf_quantile))
        or not 0 < float(leaf_quantile) < 1
    ):
        raise ValueError("invalid leaf_drift_quantile")
    leaf_threshold = config.get("leaf_drift_threshold")
    if (
        isinstance(leaf_threshold, bool)
        or not isinstance(leaf_threshold, (int, float))
        or not math.isfinite(float(leaf_threshold))
        or not 0 <= float(leaf_threshold) <= math.log(2.0)
    ):
        raise ValueError("invalid leaf_drift_threshold")
    buckets = config.get("path_sketch_buckets")
    if not isinstance(buckets, int) or isinstance(buckets, bool) or buckets < 2:
        raise ValueError("invalid path_sketch_buckets")
    salt = config.get("path_sketch_salt")
    if not isinstance(salt, str) or not salt or "\n" in salt or "|" in salt:
        raise ValueError("invalid path_sketch_salt")
    path_epsilon = config.get("path_sketch_epsilon")
    if (
        isinstance(path_epsilon, bool)
        or not isinstance(path_epsilon, (int, float))
        or not math.isfinite(float(path_epsilon))
        or not 0 < float(path_epsilon) < 1
    ):
        raise ValueError("invalid path_sketch_epsilon")
    path_threshold = config.get("path_sketch_drift_threshold")
    if (
        isinstance(path_threshold, bool)
        or not isinstance(path_threshold, (int, float))
        or not math.isfinite(float(path_threshold))
        or not 0 <= float(path_threshold) <= math.log(2.0)
    ):
        raise ValueError("invalid path_sketch_drift_threshold")


def sigmoid_calibrate(
    calibrator: LogisticRegression,
    raw_probabilities: np.ndarray,
) -> np.ndarray:
    positive_index = list(calibrator.classes_).index(1)
    return calibrator.predict_proba(raw_probabilities.reshape(-1, 1))[
        :, positive_index
    ]


def distribution_profile(
    values: np.ndarray,
    quantiles: list[float],
    ddof: int,
) -> dict[str, Any]:
    raw_points = np.quantile(values, quantiles, method="linear")
    cut_points: list[float] = []
    for raw_value in raw_points:
        value = float(raw_value)
        if not cut_points or value > cut_points[-1]:
            cut_points.append(value)
    assignments = np.searchsorted(
        np.asarray(cut_points, dtype=float),
        values,
        side="left",
    )
    proportions = np.bincount(
        assignments,
        minlength=len(cut_points) + 1,
    ) / len(values)
    return {
        "mean": float(np.mean(values)),
        "std": float(np.std(values, ddof=ddof)),
        "cut_points": cut_points,
        "bin_proportions": [float(value) for value in proportions],
    }


def leaf_occupancy_profile(
    model: RandomForestClassifier,
    features: pd.DataFrame,
) -> dict[str, Any]:
    leaves = model.apply(features)
    trees: list[dict[str, Any]] = []
    for tree_number in range(leaves.shape[1]):
        leaf_ids, counts = np.unique(
            leaves[:, tree_number].astype(int),
            return_counts=True,
        )
        trees.append(
            {
                "leaf_ids": [int(value) for value in leaf_ids],
                "bin_proportions": [
                    float(value) for value in counts / len(features)
                ],
            }
        )
    return {
        "metric": "jensen_shannon_natural_log",
        "trees": trees,
    }


def tree_disagreement(
    model: RandomForestClassifier,
    features: pd.DataFrame,
) -> np.ndarray:
    feature_values = features.to_numpy(dtype=float)
    tree_probabilities = np.empty((len(features), len(model.estimators_)), dtype=float)
    for tree_number, estimator in enumerate(model.estimators_):
        classes = list(estimator.classes_)
        if 1 in classes:
            tree_probabilities[:, tree_number] = estimator.predict_proba(feature_values)[
                :, classes.index(1)
            ]
        else:
            tree_probabilities[:, tree_number] = 0.0
    row_means = np.mean(tree_probabilities, axis=1, keepdims=True)
    return np.sqrt(np.mean((tree_probabilities - row_means) ** 2, axis=1))


def path_sketch_assignments(
    model: RandomForestClassifier,
    features: pd.DataFrame,
    bucket_count: int,
    salt: str,
) -> np.ndarray:
    leaves = model.apply(features).astype(int)
    assignments = np.empty(len(features), dtype=int)
    for row_number, row in enumerate(leaves):
        binding = f"{salt}|" + ",".join(str(int(value)) for value in row)
        hash_bytes = hashlib.sha256(binding.encode("utf-8")).digest()
        assignments[row_number] = int.from_bytes(hash_bytes[:8], "big") % bucket_count
    return assignments


def path_sketch_profile(
    model: RandomForestClassifier,
    features: pd.DataFrame,
    bucket_count: int,
    salt: str,
) -> dict[str, Any]:
    assignments = path_sketch_assignments(model, features, bucket_count, salt)
    proportions = np.bincount(assignments, minlength=bucket_count) / len(features)
    return {
        "metric": "joint_leaf_path_jensen_shannon_natural_log",
        "hash": "sha256_first_u64_be_mod",
        "salt": salt,
        "bucket_count": bucket_count,
        "bin_proportions": [float(value) for value in proportions],
    }


def spearman_coefficient(left: np.ndarray, right: np.ndarray) -> float:
    left_ranks = pd.Series(left).rank(method="average").to_numpy(dtype=float)
    right_ranks = pd.Series(right).rank(method="average").to_numpy(dtype=float)
    left_centered = left_ranks - float(np.mean(left_ranks))
    right_centered = right_ranks - float(np.mean(right_ranks))
    denominator = math.sqrt(
        float(np.dot(left_centered, left_centered))
        * float(np.dot(right_centered, right_centered))
    )
    if denominator == 0.0:
        return 0.0
    coefficient = float(np.dot(left_centered, right_centered) / denominator)
    return float(np.clip(coefficient, -1.0, 1.0))


def correlation_profile(features: pd.DataFrame) -> dict[str, Any]:
    pairs = []
    for left, right in CORRELATION_PAIRS:
        pairs.append(
            {
                "key": f"{left}|{right}",
                "left": left,
                "right": right,
                "coefficient": spearman_coefficient(
                    features[left].to_numpy(dtype=float),
                    features[right].to_numpy(dtype=float),
                ),
            }
        )
    return {"metric": "spearman_rank", "pairs": pairs}


def fit_candidate(
    frame: pd.DataFrame,
    config: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    labels = frame["label"].to_numpy(dtype=int)
    features = frame[FEATURES]
    repeat_count = int(config["cv_repeats"])
    fold_count = int(config["cv_folds"])
    base_seed = int(config["random_state"])
    stride = int(config["repeat_seed_stride"])
    raw_repeats = np.empty((repeat_count, len(frame)), dtype=float)
    calibrated_repeats = np.empty((repeat_count, len(frame)), dtype=float)
    fold_ids = np.empty((repeat_count, len(frame)), dtype=int)

    for repeat_number in range(repeat_count):
        split_seed = base_seed + repeat_number * stride
        splitter = StratifiedKFold(
            n_splits=fold_count,
            shuffle=True,
            random_state=split_seed,
        )
        for fold_number, (train_indices, validation_indices) in enumerate(
            splitter.split(features, labels)
        ):
            model = RandomForestClassifier(
                **candidate_params(candidate, split_seed + fold_number + 1)
            )
            model.fit(features.iloc[train_indices], labels[train_indices])
            positive_index = list(model.classes_).index(1)
            raw_repeats[repeat_number, validation_indices] = model.predict_proba(
                features.iloc[validation_indices]
            )[:, positive_index]
            fold_ids[repeat_number, validation_indices] = fold_number

        for fold_number in range(fold_count):
            validation_mask = fold_ids[repeat_number] == fold_number
            calibration_mask = ~validation_mask
            fold_calibrator = LogisticRegression(**calibrator_params(config))
            fold_calibrator.fit(
                raw_repeats[repeat_number, calibration_mask].reshape(-1, 1),
                labels[calibration_mask],
            )
            calibrated_repeats[repeat_number, validation_mask] = sigmoid_calibrate(
                fold_calibrator,
                raw_repeats[repeat_number, validation_mask],
            )

    raw_oof = np.mean(raw_repeats, axis=0)
    calibrated_oof = np.mean(calibrated_repeats, axis=0)
    release_calibrator = LogisticRegression(**calibrator_params(config))
    release_calibrator.fit(raw_oof.reshape(-1, 1), labels)

    threshold_rows: list[tuple[float, float, np.ndarray]] = []
    for threshold in sorted({0.0, 1.0, *map(float, calibrated_oof)}):
        predictions = (calibrated_oof >= threshold).astype(int)
        score = float(f1_score(labels, predictions, zero_division=0))
        threshold_rows.append((score, float(threshold), predictions))
    best_f1, best_threshold, best_predictions = max(
        threshold_rows,
        key=lambda item: (item[0], item[1]),
    )
    fold_f1 = [
        float(
            f1_score(
                labels[fold_ids[repeat_number] == fold_number],
                best_predictions[fold_ids[repeat_number] == fold_number],
                zero_division=0,
            )
        )
        for repeat_number in range(repeat_count)
        for fold_number in range(fold_count)
    ]
    repeat_f1 = [
        float(
            f1_score(
                labels,
                (calibrated_repeats[repeat_number] >= best_threshold).astype(int),
                zero_division=0,
            )
        )
        for repeat_number in range(repeat_count)
    ]
    summary = {
        "name": candidate["name"],
        "complexity": int(candidate["n_estimators"]) * int(candidate["max_depth"]),
        "decision_threshold": float(best_threshold),
        "raw_brier": float(np.mean((labels - raw_oof) ** 2)),
        "calibrated_brier": float(np.mean((labels - calibrated_oof) ** 2)),
        "oof_accuracy": float(accuracy_score(labels, best_predictions)),
        "oof_f1": float(best_f1),
        "worst_repeat_f1": float(min(repeat_f1)),
        "repeat_f1": repeat_f1,
        "worst_fold_f1": float(min(fold_f1)),
        "fold_f1": fold_f1,
    }
    return {
        "summary": summary,
        "raw_oof": raw_oof,
        "calibrated_oof": calibrated_oof,
        "release_calibrator": release_calibrator,
    }


data_path = Path(os.environ["DATA"])
artifacts_dir = Path(os.environ["ARTIFACTS_DIR"])
config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
validate_policy(config)
frame = pd.read_parquet(data_path)
if list(frame.columns) != INPUT_COLUMNS:
    raise ValueError("training parquet columns do not match the release schema")
if frame["id"].duplicated().any():
    raise ValueError("training ids must be unique")
if sorted(frame["label"].unique().tolist()) != [0, 1]:
    raise ValueError("training labels must contain both binary classes")
if frame[FEATURES + ["label"]].isna().any().any():
    raise ValueError("training data must not contain null model values")
if not np.isfinite(frame[FEATURES].to_numpy(dtype=float)).all():
    raise ValueError("training features must be finite")
if min(frame["label"].value_counts()) < int(config["cv_folds"]):
    raise ValueError("each label needs at least cv_folds rows")

candidate_results = [
    fit_candidate(frame, config, candidate) for candidate in config["candidates"]
]
champion_result = min(
    candidate_results,
    key=lambda item: (
        -float(item["summary"]["oof_f1"]),
        float(item["summary"]["calibrated_brier"]),
        -float(item["summary"]["worst_repeat_f1"]),
        -float(item["summary"]["worst_fold_f1"]),
        int(item["summary"]["complexity"]),
        str(item["summary"]["name"]),
    ),
)
champion_score = champion_result["summary"]
champion_config = next(
    candidate
    for candidate in config["candidates"]
    if candidate["name"] == champion_score["name"]
)
final_model = RandomForestClassifier(
    **candidate_params(champion_config, int(config["random_state"]))
)
final_model.fit(frame[FEATURES], frame["label"].to_numpy(dtype=int))
release_calibrator = champion_result["release_calibrator"]
raw_training_probability = final_model.predict_proba(frame[FEATURES])[
    :, list(final_model.classes_).index(1)
]
calibrated_training_probability = sigmoid_calibrate(
    release_calibrator,
    raw_training_probability,
)
disagreement_training = tree_disagreement(final_model, frame[FEATURES])

metrics = {
    "model_version": config["model_version"],
    "champion": champion_score["name"],
    "positive_class": 1,
    "calibration_method": config["calibration_method"],
    "calibration_c": float(config["calibration_c"]),
    "calibration_intercept": float(release_calibrator.intercept_[0]),
    "calibration_coefficient": float(release_calibrator.coef_[0, 0]),
    "decision_threshold": float(champion_score["decision_threshold"]),
    "raw_brier": float(champion_score["raw_brier"]),
    "calibrated_brier": float(champion_score["calibrated_brier"]),
    "oof_accuracy": float(champion_score["oof_accuracy"]),
    "oof_f1": float(champion_score["oof_f1"]),
    "worst_repeat_f1": float(champion_score["worst_repeat_f1"]),
    "repeat_f1": list(champion_score["repeat_f1"]),
    "worst_fold_f1": float(champion_score["worst_fold_f1"]),
    "fold_f1": list(champion_score["fold_f1"]),
    "training_rows": int(len(frame)),
    "cv_folds": int(config["cv_folds"]),
    "cv_repeats": int(config["cv_repeats"]),
    "random_state": int(config["random_state"]),
    "repeat_seed_stride": int(config["repeat_seed_stride"]),
    "candidate_scores": [result["summary"] for result in candidate_results],
}
quantiles = [float(value) for value in config["profile_quantiles"]]
profile = {
    "profile_version": 6,
    "feature_order": FEATURES,
    "quantiles": quantiles,
    "features": {
        feature: distribution_profile(
            frame[feature].to_numpy(dtype=float),
            quantiles,
            int(config["profile_ddof"]),
        )
        for feature in FEATURES
    },
    "prediction_profile": distribution_profile(
        calibrated_training_probability,
        quantiles,
        int(config["profile_ddof"]),
    ),
    "disagreement_profile": distribution_profile(
        disagreement_training,
        quantiles,
        int(config["profile_ddof"]),
    ),
    "correlation_profile": correlation_profile(frame[FEATURES]),
    "leaf_profile": leaf_occupancy_profile(final_model, frame[FEATURES]),
    "path_sketch_profile": path_sketch_profile(
        final_model,
        frame[FEATURES],
        int(config["path_sketch_buckets"]),
        str(config["path_sketch_salt"]),
    ),
}

artifacts_dir.mkdir(parents=True, exist_ok=True)
for existing in artifacts_dir.iterdir():
    if existing.is_file() or existing.is_symlink():
        existing.unlink()
    elif existing.is_dir():
        import shutil

        shutil.rmtree(existing)
joblib.dump(final_model, artifacts_dir / "model.joblib")
joblib.dump(release_calibrator, artifacts_dir / "calibrator.joblib")
write_json(artifacts_dir / "metrics.json", metrics)
write_json(artifacts_dir / "drift_profile.json", profile)
artifact_sha256 = {
    name: digest(artifacts_dir / name) for name in ARTIFACT_NAMES
}
manifest_without_release = {
    "schema_version": 7,
    "model_version": config["model_version"],
    "champion": champion_score["name"],
    "feature_order": FEATURES,
    "training_rows": int(len(frame)),
    "training_parquet_sha256": digest(data_path),
    "config_sha256": digest(CONFIG_PATH),
    "artifact_sha256": artifact_sha256,
}
release_binding = {
    key: value
    for key, value in manifest_without_release.items()
    if key != "schema_version"
}
manifest = {
    **manifest_without_release,
    "release_sha256": "sha256:"
    + hashlib.sha256(canonical_bytes(release_binding)).hexdigest(),
}
write_json(artifacts_dir / "artifact_manifest.json", manifest)
print(
    f"trained {config['model_version']} champion {champion_score['name']} "
    f"oof_f1 {champion_score['oof_f1']:.3f} "
    f"worst_repeat_f1 {champion_score['worst_repeat_f1']:.3f} "
    f"worst_fold_f1 {champion_score['worst_fold_f1']:.3f} "
    f"calibrated_brier {champion_score['calibrated_brier']:.6f} "
    f"threshold {champion_score['decision_threshold']:.6f}"
)
PY
