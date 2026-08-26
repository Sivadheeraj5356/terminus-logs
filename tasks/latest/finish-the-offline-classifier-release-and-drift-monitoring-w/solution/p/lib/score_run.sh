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

if [[ -z "$BATCH_ID" ]]; then
  echo "missing required option: --batch-id" >&2
  exit 1
fi

export API_URL BATCH_ID DATA ARTIFACTS_DIR
export PREFECT_LOGGING_TO_API_ENABLED="${PREFECT_LOGGING_TO_API_ENABLED:-false}"
export PREFECT_SERVER_ANALYTICS_ENABLED="${PREFECT_SERVER_ANALYTICS_ENABLED:-false}"
export PREFECT_API_SERVICES_SCHEDULER_ENABLED="${PREFECT_API_SERVICES_SCHEDULER_ENABLED:-false}"
export PREFECT_API_SERVICES_LATE_RUNS_ENABLED="${PREFECT_API_SERVICES_LATE_RUNS_ENABLED:-false}"
export PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED="${PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED:-false}"
export PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_ENABLED="${PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_ENABLED:-false}"
export PREFECT_API_SERVICES_CANCELLATION_CLEANUP_ENABLED="${PREFECT_API_SERVICES_CANCELLATION_CLEANUP_ENABLED:-false}"
export PREFECT_API_SERVICES_FOREMAN_ENABLED="${PREFECT_API_SERVICES_FOREMAN_ENABLED:-false}"
export PREFECT_API_SERVICES_EVENT_LOGGER_ENABLED="${PREFECT_API_SERVICES_EVENT_LOGGER_ENABLED:-false}"
export PREFECT_API_SERVICES_TRIGGERS_ENABLED="${PREFECT_API_SERVICES_TRIGGERS_ENABLED:-false}"
export PREFECT_API_SERVICES_EVENT_PERSISTER_ENABLED="${PREFECT_API_SERVICES_EVENT_PERSISTER_ENABLED:-false}"

python3 - <<'PY'
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import requests
from prefect import flow, task
from scipy.stats import ks_2samp
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
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
MANIFEST_KEYS = {
    "schema_version",
    "model_version",
    "champion",
    "feature_order",
    "training_rows",
    "training_parquet_sha256",
    "config_sha256",
    "artifact_sha256",
    "release_sha256",
}
METRICS_KEYS = {
    "model_version",
    "champion",
    "positive_class",
    "calibration_method",
    "calibration_c",
    "calibration_intercept",
    "calibration_coefficient",
    "decision_threshold",
    "raw_brier",
    "calibrated_brier",
    "oof_accuracy",
    "oof_f1",
    "worst_repeat_f1",
    "repeat_f1",
    "worst_fold_f1",
    "fold_f1",
    "training_rows",
    "cv_folds",
    "cv_repeats",
    "random_state",
    "repeat_seed_stride",
    "candidate_scores",
}
CANDIDATE_SCORE_KEYS = {
    "name",
    "complexity",
    "decision_threshold",
    "raw_brier",
    "calibrated_brier",
    "oof_accuracy",
    "oof_f1",
    "worst_repeat_f1",
    "repeat_f1",
    "worst_fold_f1",
    "fold_f1",
}
PROFILE_KEYS = {
    "profile_version",
    "feature_order",
    "quantiles",
    "features",
    "prediction_profile",
    "disagreement_profile",
    "correlation_profile",
    "leaf_profile",
    "path_sketch_profile",
}
PROFILE_VALUE_KEYS = {"mean", "std", "cut_points", "bin_proportions"}
CORRELATION_PROFILE_KEYS = {"metric", "pairs"}
CORRELATION_PAIR_KEYS = {"key", "left", "right", "coefficient"}
LEAF_PROFILE_KEYS = {"metric", "trees"}
LEAF_TREE_KEYS = {"leaf_ids", "bin_proportions"}
PATH_SKETCH_PROFILE_KEYS = {
    "metric",
    "hash",
    "salt",
    "bucket_count",
    "bin_proportions",
}
PAGE_KEYS = {"batch_id", "cursor", "records", "next_cursor", "page_sha256"}


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def digest(path: Path) -> str:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"integrity mismatch: {path}") from exc
    return digest_bytes(content)


def fail(path: Path) -> None:
    raise RuntimeError(f"integrity mismatch: {path}")


def read_json(path: Path, *, canonical: bool = False) -> Any:
    try:
        content = path.read_bytes()
        value = json.loads(content.decode("utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise RuntimeError(f"integrity mismatch: {path}") from exc
    if canonical and content != canonical_bytes(value) + b"\n":
        fail(path)
    return value


def is_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def require_digest(value: object, path: Path) -> str:
    if not isinstance(value, str) or DIGEST_RE.fullmatch(value) is None:
        fail(path)
    return value


def same_number(left: object, right: object, *, tolerance: float = 1e-12) -> bool:
    return is_number(left) and is_number(right) and math.isclose(
        float(left),
        float(right),
        rel_tol=tolerance,
        abs_tol=tolerance,
    )


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


def calibrate(
    calibrator: LogisticRegression,
    raw_probabilities: np.ndarray,
) -> np.ndarray:
    positive_index = list(calibrator.classes_).index(1)
    return calibrator.predict_proba(raw_probabilities.reshape(-1, 1))[
        :, positive_index
    ]


def expected_profile_value(
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
            calibrated_repeats[repeat_number, validation_mask] = calibrate(
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
    return {
        "summary": {
            "name": candidate["name"],
            "complexity": int(candidate["n_estimators"])
            * int(candidate["max_depth"]),
            "decision_threshold": float(best_threshold),
            "raw_brier": float(np.mean((labels - raw_oof) ** 2)),
            "calibrated_brier": float(np.mean((labels - calibrated_oof) ** 2)),
            "oof_accuracy": float(accuracy_score(labels, best_predictions)),
            "oof_f1": float(best_f1),
            "worst_repeat_f1": float(min(repeat_f1)),
            "repeat_f1": repeat_f1,
            "worst_fold_f1": float(min(fold_f1)),
            "fold_f1": fold_f1,
        },
        "release_calibrator": release_calibrator,
    }


def expected_training(
    frame: pd.DataFrame,
    config: dict[str, Any],
) -> dict[str, Any]:
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
        item
        for item in config["candidates"]
        if item["name"] == champion_score["name"]
    )
    final_model = RandomForestClassifier(
        **candidate_params(champion_config, int(config["random_state"]))
    )
    final_model.fit(frame[FEATURES], frame["label"].to_numpy(dtype=int))
    release_calibrator = champion_result["release_calibrator"]
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
    return {
        "model": final_model,
        "calibrator": release_calibrator,
        "metrics": metrics,
    }

def validate_manifest(manifest: Any, path: Path) -> dict[str, Any]:
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
        fail(path)
    if manifest.get("schema_version") != 7:
        fail(path)
    if not isinstance(manifest.get("model_version"), str):
        fail(path)
    if not isinstance(manifest.get("champion"), str):
        fail(path)
    if manifest.get("feature_order") != FEATURES:
        fail(path)
    if (
        not isinstance(manifest.get("training_rows"), int)
        or isinstance(manifest.get("training_rows"), bool)
        or manifest["training_rows"] <= 0
    ):
        fail(path)
    require_digest(manifest.get("training_parquet_sha256"), path)
    require_digest(manifest.get("config_sha256"), path)
    require_digest(manifest.get("release_sha256"), path)
    artifact_map = manifest.get("artifact_sha256")
    if not isinstance(artifact_map, dict) or set(artifact_map) != set(ARTIFACT_NAMES):
        fail(path)
    for value in artifact_map.values():
        require_digest(value, path)
    binding = {
        key: manifest[key]
        for key in (
            "model_version",
            "champion",
            "feature_order",
            "training_rows",
            "training_parquet_sha256",
            "config_sha256",
            "artifact_sha256",
        )
    }
    if manifest["release_sha256"] != digest_bytes(canonical_bytes(binding)):
        fail(path)
    return manifest


def validate_config(config: Any, path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(config, dict):
        fail(path)
    if config.get("model_version") != manifest["model_version"]:
        fail(path)
    if config.get("classifier") != "RandomForestClassifier":
        fail(path)
    if config.get("positive_class") != 1:
        fail(path)
    for key in ("cv_folds", "cv_repeats"):
        if (
            not isinstance(config.get(key), int)
            or isinstance(config.get(key), bool)
            or config[key] < 2
        ):
            fail(path)
    if not isinstance(config.get("random_state"), int) or isinstance(
        config.get("random_state"), bool
    ):
        fail(path)
    if (
        not isinstance(config.get("repeat_seed_stride"), int)
        or isinstance(config.get("repeat_seed_stride"), bool)
        or config["repeat_seed_stride"] <= config["cv_folds"]
    ):
        fail(path)
    if config.get("calibration_method") != "sigmoid":
        fail(path)
    if not is_number(config.get("calibration_c")) or float(config["calibration_c"]) <= 0:
        fail(path)
    if config.get("threshold_metric") != "f1":
        fail(path)
    if config.get("threshold_tie_break") != "highest":
        fail(path)
    if config.get("champion_tie_break") != [
        "oof_f1",
        "lower_calibrated_brier",
        "worst_repeat_f1",
        "worst_fold_f1",
        "lower_complexity",
        "name",
    ]:
        fail(path)
    quantiles = config.get("profile_quantiles")
    if (
        not isinstance(quantiles, list)
        or not quantiles
        or any(not is_number(value) or not 0 < float(value) < 1 for value in quantiles)
        or [float(value) for value in quantiles]
        != sorted(set(float(value) for value in quantiles))
    ):
        fail(path)
    if config.get("profile_ddof") != 0:
        fail(path)
    for key in (
        "psi_epsilon",
        "drift_ks_threshold",
        "drift_psi_threshold",
        "prediction_drift_psi_threshold",
        "disagreement_drift_psi_threshold",
    ):
        if not is_number(config.get(key)) or float(config[key]) <= 0:
            fail(path)
    if (
        not is_number(config.get("correlation_drift_threshold"))
        or not 0 <= float(config["correlation_drift_threshold"]) <= 2
    ):
        fail(path)
    quorum = config.get("drift_feature_quorum")
    if (
        not isinstance(quorum, int)
        or isinstance(quorum, bool)
        or not 1 <= quorum <= len(FEATURES)
    ):
        fail(path)
    page_size = config.get("inference_page_size")
    if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size <= 0:
        fail(path)
    if (
        not is_number(config.get("leaf_js_epsilon"))
        or not 0 < float(config["leaf_js_epsilon"]) < 1
    ):
        fail(path)
    if (
        not is_number(config.get("leaf_drift_quantile"))
        or not 0 < float(config["leaf_drift_quantile"]) < 1
    ):
        fail(path)
    if (
        not is_number(config.get("leaf_drift_threshold"))
        or not 0 <= float(config["leaf_drift_threshold"]) <= math.log(2.0)
    ):
        fail(path)
    if (
        not isinstance(config.get("path_sketch_buckets"), int)
        or isinstance(config.get("path_sketch_buckets"), bool)
        or config["path_sketch_buckets"] < 2
    ):
        fail(path)
    salt = config.get("path_sketch_salt")
    if not isinstance(salt, str) or not salt or "\n" in salt or "|" in salt:
        fail(path)
    if (
        not is_number(config.get("path_sketch_epsilon"))
        or not 0 < float(config["path_sketch_epsilon"]) < 1
    ):
        fail(path)
    if (
        not is_number(config.get("path_sketch_drift_threshold"))
        or not 0 <= float(config["path_sketch_drift_threshold"]) <= math.log(2.0)
    ):
        fail(path)
    candidates = config.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        fail(path)
    names: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or set(candidate) != {
            "name",
            "n_estimators",
            "max_depth",
            "min_samples_leaf",
            "class_weight",
        }:
            fail(path)
        if not isinstance(candidate["name"], str) or not candidate["name"]:
            fail(path)
        names.append(candidate["name"])
        for key in ("n_estimators", "max_depth", "min_samples_leaf"):
            if (
                not isinstance(candidate[key], int)
                or isinstance(candidate[key], bool)
                or candidate[key] <= 0
            ):
                fail(path)
        if candidate["class_weight"] not in (None, "balanced", "balanced_subsample"):
            fail(path)
    if len(names) != len(set(names)):
        fail(path)
    return config

def validate_metrics(
    observed: Any,
    expected: dict[str, Any],
    path: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(observed, dict) or set(observed) != METRICS_KEYS:
        fail(path)
    if observed.get("model_version") != manifest["model_version"]:
        fail(path)
    if observed.get("champion") != manifest["champion"]:
        fail(path)
    for key in (
        "positive_class",
        "training_rows",
        "cv_folds",
        "cv_repeats",
        "random_state",
        "repeat_seed_stride",
    ):
        if not isinstance(observed.get(key), int) or isinstance(observed.get(key), bool):
            fail(path)
    if (
        not isinstance(observed.get("fold_f1"), list)
        or not isinstance(observed.get("repeat_f1"), list)
        or len(observed["fold_f1"]) != observed["cv_folds"] * observed["cv_repeats"]
        or len(observed["repeat_f1"]) != observed["cv_repeats"]
    ):
        fail(path)
    scores = observed.get("candidate_scores")
    if not isinstance(scores, list) or len(scores) != len(expected["candidate_scores"]):
        fail(path)
    for score in scores:
        if not isinstance(score, dict) or set(score) != CANDIDATE_SCORE_KEYS:
            fail(path)
    if not equivalent(observed, expected):
        fail(path)
    return observed


def equivalent(observed: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return (
            isinstance(observed, dict)
            and set(observed) == set(expected)
            and all(equivalent(observed[key], value) for key, value in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(observed, list)
            and len(observed) == len(expected)
            and all(equivalent(left, right) for left, right in zip(observed, expected, strict=True))
        )
    if isinstance(expected, float):
        return same_number(observed, expected)
    return observed == expected


def load_joblib(path: Path) -> Any:
    try:
        return joblib.load(path)
    except Exception as exc:
        raise RuntimeError(f"integrity mismatch: {path}") from exc


def validate_model(
    observed: Any,
    expected: RandomForestClassifier,
    reference: pd.DataFrame,
    path: Path,
) -> RandomForestClassifier:
    if not isinstance(observed, RandomForestClassifier):
        fail(path)
    for key in (
        "n_estimators",
        "max_depth",
        "min_samples_leaf",
        "class_weight",
        "random_state",
        "n_jobs",
    ):
        if observed.get_params().get(key) != expected.get_params().get(key):
            fail(path)
    if observed.n_features_in_ != len(FEATURES) or list(observed.classes_) != [0, 1]:
        fail(path)
    try:
        observed_probabilities = observed.predict_proba(reference[FEATURES])
        expected_probabilities = expected.predict_proba(reference[FEATURES])
        observed_leaves = observed.apply(reference[FEATURES])
        expected_leaves = expected.apply(reference[FEATURES])
    except Exception:
        fail(path)
    if not np.array_equal(observed_probabilities, expected_probabilities):
        fail(path)
    if not np.array_equal(observed_leaves, expected_leaves):
        fail(path)
    return observed


def validate_calibrator(
    observed: Any,
    expected: LogisticRegression,
    config: dict[str, Any],
    path: Path,
) -> LogisticRegression:
    if not isinstance(observed, LogisticRegression):
        fail(path)
    for key, expected_value in calibrator_params(config).items():
        if observed.get_params().get(key) != expected_value:
            fail(path)
    if observed.n_features_in_ != 1 or list(observed.classes_) != [0, 1]:
        fail(path)
    if not np.array_equal(observed.coef_, expected.coef_):
        fail(path)
    if not np.array_equal(observed.intercept_, expected.intercept_):
        fail(path)
    return observed


def validate_profile_value(observed: Any, expected: dict[str, Any], path: Path) -> None:
    if not isinstance(observed, dict) or set(observed) != PROFILE_VALUE_KEYS:
        fail(path)
    if not equivalent(observed, expected):
        fail(path)


def validate_leaf_profile(observed: Any, expected: dict[str, Any], path: Path) -> None:
    if not isinstance(observed, dict) or set(observed) != LEAF_PROFILE_KEYS:
        fail(path)
    if observed.get("metric") != "jensen_shannon_natural_log":
        fail(path)
    trees = observed.get("trees")
    if not isinstance(trees, list) or len(trees) != len(expected["trees"]):
        fail(path)
    for actual_tree, expected_tree in zip(trees, expected["trees"], strict=True):
        if not isinstance(actual_tree, dict) or set(actual_tree) != LEAF_TREE_KEYS:
            fail(path)
        leaf_ids = actual_tree.get("leaf_ids")
        proportions = actual_tree.get("bin_proportions")
        if (
            not isinstance(leaf_ids, list)
            or not leaf_ids
            or any(not isinstance(value, int) or isinstance(value, bool) for value in leaf_ids)
            or leaf_ids != sorted(set(leaf_ids))
            or not isinstance(proportions, list)
            or len(proportions) != len(leaf_ids)
            or any(not is_number(value) or float(value) < 0 for value in proportions)
            or not same_number(sum(proportions), 1.0)
        ):
            fail(path)
        if not equivalent(actual_tree, expected_tree):
            fail(path)


def validate_path_sketch_profile(
    observed: Any,
    expected: dict[str, Any],
    path: Path,
) -> None:
    if not isinstance(observed, dict) or set(observed) != PATH_SKETCH_PROFILE_KEYS:
        fail(path)
    if observed.get("metric") != "joint_leaf_path_jensen_shannon_natural_log":
        fail(path)
    if observed.get("hash") != "sha256_first_u64_be_mod":
        fail(path)
    if (
        not isinstance(observed.get("bucket_count"), int)
        or isinstance(observed.get("bucket_count"), bool)
        or observed["bucket_count"] < 2
        or not isinstance(observed.get("salt"), str)
    ):
        fail(path)
    proportions = observed.get("bin_proportions")
    if (
        not isinstance(proportions, list)
        or len(proportions) != observed["bucket_count"]
        or any(not is_number(value) or float(value) < 0 for value in proportions)
        or not same_number(sum(proportions), 1.0)
        or not equivalent(observed, expected)
    ):
        fail(path)


def validate_correlation_profile(
    observed: Any,
    expected: dict[str, Any],
    path: Path,
) -> None:
    if not isinstance(observed, dict) or set(observed) != CORRELATION_PROFILE_KEYS:
        fail(path)
    if observed.get("metric") != "spearman_rank":
        fail(path)
    pairs = observed.get("pairs")
    expected_pairs = expected["pairs"]
    if not isinstance(pairs, list) or len(pairs) != len(expected_pairs):
        fail(path)
    for actual_pair, expected_pair in zip(pairs, expected_pairs, strict=True):
        if not isinstance(actual_pair, dict) or set(actual_pair) != CORRELATION_PAIR_KEYS:
            fail(path)
        if actual_pair.get("key") != f"{actual_pair.get('left')}|{actual_pair.get('right')}":
            fail(path)
        if not equivalent(actual_pair, expected_pair):
            fail(path)


def validate_profile(
    observed: Any,
    reference: pd.DataFrame,
    config: dict[str, Any],
    model: RandomForestClassifier,
    calibrator: LogisticRegression,
    path: Path,
) -> dict[str, Any]:
    if not isinstance(observed, dict) or set(observed) != PROFILE_KEYS:
        fail(path)
    if observed.get("profile_version") != 6:
        fail(path)
    if observed.get("feature_order") != FEATURES:
        fail(path)
    quantiles = [float(value) for value in config["profile_quantiles"]]
    if observed.get("quantiles") != quantiles:
        fail(path)
    feature_profiles = observed.get("features")
    if not isinstance(feature_profiles, dict) or list(feature_profiles) != FEATURES:
        fail(path)
    for feature in FEATURES:
        validate_profile_value(
            feature_profiles[feature],
            expected_profile_value(
                reference[feature].to_numpy(dtype=float),
                quantiles,
                int(config["profile_ddof"]),
            ),
            path,
        )
    raw_training = model.predict_proba(reference[FEATURES])[
        :, list(model.classes_).index(1)
    ]
    calibrated_training = calibrate(calibrator, raw_training)
    validate_profile_value(
        observed.get("prediction_profile"),
        expected_profile_value(
            calibrated_training,
            quantiles,
            int(config["profile_ddof"]),
        ),
        path,
    )
    validate_profile_value(
        observed.get("disagreement_profile"),
        expected_profile_value(
            tree_disagreement(model, reference[FEATURES]),
            quantiles,
            int(config["profile_ddof"]),
        ),
        path,
    )
    validate_correlation_profile(
        observed.get("correlation_profile"),
        correlation_profile(reference[FEATURES]),
        path,
    )
    validate_leaf_profile(
        observed.get("leaf_profile"),
        leaf_occupancy_profile(model, reference[FEATURES]),
        path,
    )
    validate_path_sketch_profile(
        observed.get("path_sketch_profile"),
        path_sketch_profile(
            model,
            reference[FEATURES],
            int(config["path_sketch_buckets"]),
            str(config["path_sketch_salt"]),
        ),
        path,
    )
    return observed

def population_stability_index(
    values: np.ndarray,
    profile_value: dict[str, Any],
    epsilon: float,
) -> float:
    cut_points = np.asarray(profile_value["cut_points"], dtype=float)
    assignments = np.searchsorted(cut_points, values, side="left")
    actual_proportions = np.bincount(
        assignments,
        minlength=len(cut_points) + 1,
    ) / len(values)
    psi = 0.0
    for expected_raw, actual_raw in zip(
        profile_value["bin_proportions"],
        actual_proportions,
        strict=True,
    ):
        expected = max(float(expected_raw), epsilon)
        actual = max(float(actual_raw), epsilon)
        psi += (actual - expected) * math.log(actual / expected)
    return float(psi)


def correlation_deltas(
    features: pd.DataFrame,
    stored_profile: dict[str, Any],
) -> dict[str, float]:
    observed_profile = correlation_profile(features)
    deltas: dict[str, float] = {}
    for stored, observed in zip(
        stored_profile["pairs"],
        observed_profile["pairs"],
        strict=True,
    ):
        if stored["key"] != observed["key"]:
            raise ValueError("correlation profile order mismatch")
        deltas[stored["key"]] = abs(
            float(observed["coefficient"]) - float(stored["coefficient"])
        )
    return deltas


def leaf_js_divergences(
    model: RandomForestClassifier,
    batch: pd.DataFrame,
    leaf_profile: dict[str, Any],
    epsilon: float,
) -> list[float]:
    leaves = model.apply(batch)
    values: list[float] = []
    for tree_number, stored in enumerate(leaf_profile["trees"]):
        observed_ids, observed_counts = np.unique(
            leaves[:, tree_number].astype(int),
            return_counts=True,
        )
        expected_map = {
            int(leaf_id): float(proportion)
            for leaf_id, proportion in zip(
                stored["leaf_ids"],
                stored["bin_proportions"],
                strict=True,
            )
        }
        observed_map = {
            int(leaf_id): float(count) / len(batch)
            for leaf_id, count in zip(observed_ids, observed_counts, strict=True)
        }
        support = sorted(set(expected_map) | set(observed_map))
        expected = np.asarray(
            [expected_map.get(leaf_id, 0.0) for leaf_id in support],
            dtype=float,
        )
        actual = np.asarray(
            [observed_map.get(leaf_id, 0.0) for leaf_id in support],
            dtype=float,
        )
        expected = expected + epsilon
        actual = actual + epsilon
        expected = expected / expected.sum()
        actual = actual / actual.sum()
        midpoint = (expected + actual) / 2.0
        divergence = 0.5 * float(np.sum(expected * np.log(expected / midpoint)))
        divergence += 0.5 * float(np.sum(actual * np.log(actual / midpoint)))
        values.append(divergence)
    return values


def path_sketch_js_divergence(
    assignments: np.ndarray,
    profile: dict[str, Any],
    epsilon: float,
) -> float:
    bucket_count = int(profile["bucket_count"])
    expected = np.asarray(profile["bin_proportions"], dtype=float)
    actual = np.bincount(assignments, minlength=bucket_count).astype(float)
    actual = actual / len(assignments)
    expected = expected + epsilon
    actual = actual + epsilon
    expected = expected / expected.sum()
    actual = actual / actual.sum()
    midpoint = (expected + actual) / 2.0
    value = 0.5 * float(np.sum(expected * np.log(expected / midpoint)))
    value += 0.5 * float(np.sum(actual * np.log(actual / midpoint)))
    return value


@task(name="load-release")
def load_release() -> dict[str, Any]:
    artifacts_dir = Path(os.environ["ARTIFACTS_DIR"])
    data_path = Path(os.environ["DATA"])
    manifest_path = artifacts_dir / "artifact_manifest.json"
    metrics_path = artifacts_dir / "metrics.json"
    profile_path = artifacts_dir / "drift_profile.json"
    model_path = artifacts_dir / "model.joblib"
    calibrator_path = artifacts_dir / "calibrator.joblib"

    manifest = validate_manifest(read_json(manifest_path, canonical=True), manifest_path)
    if digest(data_path) != manifest["training_parquet_sha256"]:
        fail(data_path)
    if digest(CONFIG_PATH) != manifest["config_sha256"]:
        fail(CONFIG_PATH)
    for name in ARTIFACT_NAMES:
        artifact_path = artifacts_dir / name
        if digest(artifact_path) != manifest["artifact_sha256"][name]:
            fail(artifact_path)

    config = validate_config(read_json(CONFIG_PATH), CONFIG_PATH, manifest)
    try:
        reference = pd.read_parquet(data_path)
    except Exception as exc:
        raise RuntimeError(f"integrity mismatch: {data_path}") from exc
    if (
        list(reference.columns) != INPUT_COLUMNS
        or len(reference) != manifest["training_rows"]
        or reference["id"].duplicated().any()
        or sorted(reference["label"].unique().tolist()) != [0, 1]
        or reference[FEATURES + ["label"]].isna().any().any()
        or not np.isfinite(reference[FEATURES].to_numpy(dtype=float)).all()
        or min(reference["label"].value_counts()) < int(config["cv_folds"])
    ):
        fail(data_path)

    expected = expected_training(reference, config)
    metrics = validate_metrics(
        read_json(metrics_path, canonical=True),
        expected["metrics"],
        metrics_path,
        manifest,
    )
    model = validate_model(
        load_joblib(model_path),
        expected["model"],
        reference,
        model_path,
    )
    calibrator = validate_calibrator(
        load_joblib(calibrator_path),
        expected["calibrator"],
        config,
        calibrator_path,
    )
    profile = validate_profile(
        read_json(profile_path, canonical=True),
        reference,
        config,
        model,
        calibrator,
        profile_path,
    )
    return {
        "model": model,
        "calibrator": calibrator,
        "metrics": metrics,
        "manifest": manifest,
        "config": config,
        "profile": profile,
        "reference": reference,
    }


@task(name="fetch-inference-batch")
def fetch_inference_batch() -> dict[str, Any]:
    url = (
        f"{os.environ['API_URL'].rstrip('/')}/inference-batches/"
        f"{os.environ['BATCH_ID']}/"
    )
    cursor: int | None = None
    seen_cursors: set[int | None] = {None}
    seen_ids: set[int] = set()
    records: list[dict[str, Any]] = []
    page_digests: list[str] = []
    while True:
        params = {} if cursor is None else {"cursor": str(cursor)}
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or set(payload) != PAGE_KEYS:
            raise ValueError("invalid inference page schema")
        if payload["batch_id"] != os.environ["BATCH_ID"] or payload["cursor"] != cursor:
            raise ValueError("invalid inference page binding")
        page_records = payload["records"]
        next_cursor = payload["next_cursor"]
        page_digest = payload["page_sha256"]
        if (
            not isinstance(page_records, list)
            or not page_records
            or not isinstance(page_digest, str)
            or DIGEST_RE.fullmatch(page_digest) is None
            or (next_cursor is not None and (
                not isinstance(next_cursor, int) or isinstance(next_cursor, bool)
            ))
        ):
            raise ValueError("invalid inference page values")
        binding = {
            "batch_id": payload["batch_id"],
            "cursor": payload["cursor"],
            "records": page_records,
            "next_cursor": next_cursor,
        }
        if page_digest != digest_bytes(canonical_bytes(binding)):
            raise ValueError("invalid inference page digest")
        for record in page_records:
            if not isinstance(record, dict) or set(record) != {"id", "features"}:
                raise ValueError("invalid inference record schema")
            record_id = record["id"]
            features = record["features"]
            if (
                not isinstance(record_id, int)
                or isinstance(record_id, bool)
                or record_id in seen_ids
                or not isinstance(features, dict)
                or set(features) != set(FEATURES)
                or any(not is_number(features[name]) for name in FEATURES)
            ):
                raise ValueError("invalid inference record values")
            seen_ids.add(record_id)
            records.append(record)
        page_digests.append(page_digest)
        if next_cursor is None:
            break
        if next_cursor in seen_cursors or (cursor is not None and next_cursor <= cursor):
            raise ValueError("invalid inference cursor chain")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
        if len(page_digests) > 10000:
            raise ValueError("inference cursor chain is too long")
    transcript = "".join(f"{value}\n" for value in page_digests).encode("utf-8")
    return {
        "batch_id": os.environ["BATCH_ID"],
        "records": records,
        "source_page_count": len(page_digests),
        "batch_source_digest": digest_bytes(transcript),
    }


@task(name="score-and-measure-drift")
def score_and_measure_drift(
    release: dict[str, Any],
    batch_payload: dict[str, Any],
) -> dict[str, Any]:
    records = sorted(batch_payload["records"], key=lambda record: int(record["id"]))
    batch = pd.DataFrame(
        [
            {feature: record["features"][feature] for feature in FEATURES}
            for record in records
        ],
        columns=FEATURES,
    )
    model = release["model"]
    calibrator = release["calibrator"]
    metrics = release["metrics"]
    raw_probabilities = model.predict_proba(batch)[:, list(model.classes_).index(1)]
    probabilities = calibrate(calibrator, raw_probabilities)
    predictions = (probabilities >= metrics["decision_threshold"]).astype(int)
    prediction_transcript = "".join(
        f"{int(record['id'])}:{float(probability):.12f}:{int(prediction)}\n"
        for record, probability, prediction in zip(
            records,
            probabilities,
            predictions,
            strict=True,
        )
    ).encode("utf-8")

    config = release["config"]
    epsilon = float(config["psi_epsilon"])
    feature_stats: dict[str, dict[str, Any]] = {}
    drifted_features: list[str] = []
    for feature in FEATURES:
        batch_values = batch[feature].to_numpy(dtype=float)
        reference_values = release["reference"][feature].to_numpy(dtype=float)
        ks_statistic = float(ks_2samp(reference_values, batch_values).statistic)
        psi = population_stability_index(
            batch_values,
            release["profile"]["features"][feature],
            epsilon,
        )
        drifted = (
            ks_statistic > float(config["drift_ks_threshold"])
            or psi > float(config["drift_psi_threshold"])
        )
        feature_stats[feature] = {
            "mean": float(np.mean(batch_values)),
            "std": float(np.std(batch_values, ddof=0)),
            "ks_statistic": ks_statistic,
            "psi": psi,
            "drifted": bool(drifted),
        }
        if drifted:
            drifted_features.append(feature)

    prediction_psi = population_stability_index(
        probabilities,
        release["profile"]["prediction_profile"],
        epsilon,
    )
    prediction_drifted = bool(
        prediction_psi > float(config["prediction_drift_psi_threshold"])
    )
    disagreements = tree_disagreement(model, batch)
    disagreement_psi = population_stability_index(
        disagreements,
        release["profile"]["disagreement_profile"],
        epsilon,
    )
    disagreement_drifted = bool(
        disagreement_psi > float(config["disagreement_drift_psi_threshold"])
    )
    pair_deltas = correlation_deltas(
        batch,
        release["profile"]["correlation_profile"],
    )
    correlation_score = max(pair_deltas.values())
    correlation_drifted = bool(
        correlation_score > float(config["correlation_drift_threshold"])
    )
    leaf_values = leaf_js_divergences(
        model,
        batch,
        release["profile"]["leaf_profile"],
        float(config["leaf_js_epsilon"]),
    )
    leaf_score = float(
        np.quantile(
            np.asarray(leaf_values, dtype=float),
            float(config["leaf_drift_quantile"]),
            method="linear",
        )
    )
    leaf_drifted = bool(leaf_score > float(config["leaf_drift_threshold"]))
    path_profile = release["profile"]["path_sketch_profile"]
    path_assignments = path_sketch_assignments(
        model,
        batch,
        int(path_profile["bucket_count"]),
        str(path_profile["salt"]),
    )
    path_transcript = "".join(
        f"{int(record['id'])}:{int(bucket)}\n"
        for record, bucket in zip(records, path_assignments, strict=True)
    ).encode("utf-8")
    path_score = path_sketch_js_divergence(
        path_assignments,
        path_profile,
        float(config["path_sketch_epsilon"]),
    )
    path_drifted = bool(
        path_score > float(config["path_sketch_drift_threshold"])
    )
    drift_detected = bool(
        len(drifted_features) >= int(config["drift_feature_quorum"])
        or prediction_drifted
        or disagreement_drifted
        or correlation_drifted
        or leaf_drifted
        or path_drifted
    )
    return {
        "batch_id": os.environ["BATCH_ID"],
        "model_version": release["manifest"]["model_version"],
        "champion": release["manifest"]["champion"],
        "training_oof_f1": metrics["oof_f1"],
        "training_calibrated_brier": metrics["calibrated_brier"],
        "decision_threshold": metrics["decision_threshold"],
        "source_page_count": batch_payload["source_page_count"],
        "batch_source_digest": batch_payload["batch_source_digest"],
        "prediction_count": int(len(predictions)),
        "positive_predictions": int(predictions.sum()),
        "mean_raw_positive_probability": float(np.mean(raw_probabilities)),
        "mean_positive_probability": float(np.mean(probabilities)),
        "prediction_digest": digest_bytes(prediction_transcript),
        "prediction_psi": prediction_psi,
        "prediction_drifted": prediction_drifted,
        "mean_tree_disagreement": float(np.mean(disagreements)),
        "disagreement_psi": disagreement_psi,
        "disagreement_drifted": disagreement_drifted,
        "correlation_deltas": pair_deltas,
        "correlation_drift_score": correlation_score,
        "correlation_drifted": correlation_drifted,
        "leaf_js_divergences": leaf_values,
        "leaf_drift_score": leaf_score,
        "leaf_drifted": leaf_drifted,
        "path_sketch_digest": digest_bytes(path_transcript),
        "path_sketch_js": path_score,
        "path_sketch_drifted": path_drifted,
        "drift_detected": drift_detected,
        "drifted_features": drifted_features,
        "feature_stats": feature_stats,
    }


@task(name="submit-drift-evaluation")
def submit_drift_evaluation(payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{os.environ['API_URL'].rstrip('/')}/drift-evaluations/"
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


@flow(name="drift-monitoring-run")
def drift_monitoring_run() -> dict[str, Any]:
    release = load_release()
    batch_payload = fetch_inference_batch()
    evaluation = score_and_measure_drift(release, batch_payload)
    return submit_drift_evaluation(evaluation)


result = drift_monitoring_run()
print(f"submitted drift evaluation id {result['id']}")
PY
