"""Behavioral verifier for calibrated release, paginated sourcing, and layered drift."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import pytest
import requests
from scipy.stats import ks_2samp
from sklearn.datasets import make_classification
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
CORRELATION_KEYS = [f"{left}|{right}" for left, right in CORRELATION_PAIRS]
CLI = "/app/p/wf"
CONFIG_PATH = Path("/app/config/repro_config.json")
DEFAULT_DATA = Path("/app/data/training.parquet")
DEFAULT_ARTIFACTS = Path("/app/artifacts")
API_URL = "http://127.0.0.1:8000/api/v1"
DJANGO_DIR = Path("/app/django_api")
DJANGO_LOG = Path("/tmp/model-release-django.log")
STOP_DJANGO = "/app/scripts/stop_django.py"
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PREFECT_FLOW = "drift-monitoring-run"
PREFECT_TASKS = (
    "load-release",
    "fetch-inference-batch",
    "score-and-measure-drift",
    "submit-drift-evaluation",
)
ARTIFACT_NAMES = (
    "model.joblib",
    "calibrator.joblib",
    "metrics.json",
    "drift_profile.json",
)
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
PROFILE_FEATURE_KEYS = {"mean", "std", "cut_points", "bin_proportions"}
CORRELATION_PROFILE_KEYS = {"metric", "pairs"}
CORRELATION_PAIR_KEYS = {"key", "left", "right", "coefficient"}
LEAF_PROFILE_KEYS = {"metric", "trees"}
LEAF_TREE_KEYS = {"leaf_ids", "bin_proportions"}
PATH_SKETCH_PROFILE_KEYS = {"metric", "hash", "salt", "bucket_count", "bin_proportions"}
PAGE_KEYS = {"batch_id", "cursor", "records", "next_cursor", "page_sha256"}
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


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


@contextmanager
def _temporary_config(config: dict[str, Any]) -> Iterator[None]:
    original = CONFIG_PATH.read_bytes()
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    try:
        yield
    finally:
        CONFIG_PATH.write_bytes(original)


def _assert_number(value: object) -> None:
    assert isinstance(value, (int, float))
    assert not isinstance(value, bool)
    assert math.isfinite(float(value))


def _run_train(data: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            CLI,
            "train",
            "--data",
            str(data),
            "--artifacts-dir",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )


def _candidate_params(
    candidate: dict[str, Any],
    config: dict[str, Any],
    random_state: int | None = None,
) -> dict:
    return {
        "n_estimators": candidate["n_estimators"],
        "max_depth": candidate["max_depth"],
        "min_samples_leaf": candidate["min_samples_leaf"],
        "class_weight": candidate["class_weight"],
        "random_state": (
            config["random_state"] if random_state is None else random_state
        ),
        "n_jobs": 1,
    }


def _calibrator_params(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "C": float(config["calibration_c"]),
        "solver": "lbfgs",
        "max_iter": 1000,
    }


def _calibrate(
    calibrator: LogisticRegression,
    raw_probabilities: np.ndarray,
) -> np.ndarray:
    positive_index = list(calibrator.classes_).index(1)
    return calibrator.predict_proba(raw_probabilities.reshape(-1, 1))[:, positive_index]


def _expected_candidate(
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
                **_candidate_params(
                    candidate,
                    config,
                    split_seed + fold_number + 1,
                )
            )
            model.fit(features.iloc[train_indices], labels[train_indices])
            positive_index = list(model.classes_).index(config["positive_class"])
            raw_repeats[repeat_number, validation_indices] = model.predict_proba(
                features.iloc[validation_indices]
            )[:, positive_index]
            fold_ids[repeat_number, validation_indices] = fold_number

        for fold_number in range(fold_count):
            validation_mask = fold_ids[repeat_number] == fold_number
            calibration_mask = ~validation_mask
            fold_calibrator = LogisticRegression(**_calibrator_params(config))
            fold_calibrator.fit(
                raw_repeats[repeat_number, calibration_mask].reshape(-1, 1),
                labels[calibration_mask],
            )
            calibrated_repeats[repeat_number, validation_mask] = _calibrate(
                fold_calibrator,
                raw_repeats[repeat_number, validation_mask],
            )

    raw_oof = np.mean(raw_repeats, axis=0)
    calibrated_oof = np.mean(calibrated_repeats, axis=0)
    release_calibrator = LogisticRegression(**_calibrator_params(config))
    release_calibrator.fit(raw_oof.reshape(-1, 1), labels)
    threshold_rows: list[tuple[float, float, np.ndarray]] = []
    for threshold in sorted({0.0, 1.0, *map(float, calibrated_oof)}):
        predictions = (calibrated_oof >= threshold).astype(int)
        score = float(f1_score(labels, predictions, zero_division=0))
        threshold_rows.append((score, float(threshold), predictions))
    oof_f1, decision_threshold, predictions = max(
        threshold_rows,
        key=lambda item: (item[0], item[1]),
    )
    fold_f1 = [
        float(
            f1_score(
                labels[fold_ids[repeat_number] == fold_number],
                predictions[fold_ids[repeat_number] == fold_number],
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
                (calibrated_repeats[repeat_number] >= decision_threshold).astype(int),
                zero_division=0,
            )
        )
        for repeat_number in range(repeat_count)
    ]
    return {
        "name": candidate["name"],
        "complexity": candidate["n_estimators"] * candidate["max_depth"],
        "decision_threshold": decision_threshold,
        "raw_brier": float(np.mean((labels - raw_oof) ** 2)),
        "calibrated_brier": float(np.mean((labels - calibrated_oof) ** 2)),
        "oof_accuracy": float(accuracy_score(labels, predictions)),
        "oof_f1": oof_f1,
        "worst_repeat_f1": min(repeat_f1),
        "repeat_f1": repeat_f1,
        "worst_fold_f1": min(fold_f1),
        "fold_f1": fold_f1,
        "threshold_rows": threshold_rows,
        "raw_oof": raw_oof,
        "calibrated_oof": calibrated_oof,
        "release_calibrator": release_calibrator,
    }


def _expected_training(frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    candidate_details = [
        _expected_candidate(frame, config, candidate)
        for candidate in config["candidates"]
    ]
    champion = min(
        candidate_details,
        key=lambda item: (
            -item["oof_f1"],
            item["calibrated_brier"],
            -item["worst_repeat_f1"],
            -item["worst_fold_f1"],
            item["complexity"],
            item["name"],
        ),
    )
    champion_config = next(
        candidate
        for candidate in config["candidates"]
        if candidate["name"] == champion["name"]
    )
    final_model = RandomForestClassifier(**_candidate_params(champion_config, config))
    final_model.fit(frame[FEATURES], frame["label"].to_numpy(dtype=int))
    release_calibrator = champion["release_calibrator"]
    metrics = {
        "model_version": config["model_version"],
        "champion": champion["name"],
        "positive_class": config["positive_class"],
        "calibration_method": config["calibration_method"],
        "calibration_c": float(config["calibration_c"]),
        "calibration_intercept": float(release_calibrator.intercept_[0]),
        "calibration_coefficient": float(release_calibrator.coef_[0, 0]),
        "decision_threshold": champion["decision_threshold"],
        "raw_brier": champion["raw_brier"],
        "calibrated_brier": champion["calibrated_brier"],
        "oof_accuracy": champion["oof_accuracy"],
        "oof_f1": champion["oof_f1"],
        "worst_repeat_f1": champion["worst_repeat_f1"],
        "repeat_f1": champion["repeat_f1"],
        "worst_fold_f1": champion["worst_fold_f1"],
        "fold_f1": champion["fold_f1"],
        "training_rows": len(frame),
        "cv_folds": config["cv_folds"],
        "cv_repeats": config["cv_repeats"],
        "random_state": config["random_state"],
        "repeat_seed_stride": config["repeat_seed_stride"],
        "candidate_scores": [
            {
                key: value
                for key, value in score.items()
                if key
                not in {
                    "threshold_rows",
                    "raw_oof",
                    "calibrated_oof",
                    "release_calibrator",
                }
            }
            for score in candidate_details
        ],
    }
    return {
        "model": final_model,
        "calibrator": release_calibrator,
        "metrics": metrics,
        "candidate_details": candidate_details,
    }

def _profile_feature(
    values: np.ndarray,
    quantiles: list[float],
    ddof: int,
) -> dict[str, Any]:
    raw_points = np.quantile(values, quantiles, method="linear")
    cut_points: list[float] = []
    for raw in raw_points:
        value = float(raw)
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


def _leaf_profile(
    model: RandomForestClassifier,
    features: pd.DataFrame,
) -> dict[str, Any]:
    leaves = model.apply(features)
    trees = []
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


def _tree_disagreement(
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


def _path_sketch_assignments(
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


def _path_sketch_profile(
    model: RandomForestClassifier,
    features: pd.DataFrame,
    bucket_count: int,
    salt: str,
) -> dict[str, Any]:
    assignments = _path_sketch_assignments(model, features, bucket_count, salt)
    proportions = np.bincount(assignments, minlength=bucket_count) / len(features)
    return {
        "metric": "joint_leaf_path_jensen_shannon_natural_log",
        "hash": "sha256_first_u64_be_mod",
        "salt": salt,
        "bucket_count": bucket_count,
        "bin_proportions": [float(value) for value in proportions],
    }


def _spearman_coefficient(left: np.ndarray, right: np.ndarray) -> float:
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


def _correlation_profile(features: pd.DataFrame) -> dict[str, Any]:
    return {
        "metric": "spearman_rank",
        "pairs": [
            {
                "key": f"{left}|{right}",
                "left": left,
                "right": right,
                "coefficient": _spearman_coefficient(
                    features[left].to_numpy(dtype=float),
                    features[right].to_numpy(dtype=float),
                ),
            }
            for left, right in CORRELATION_PAIRS
        ],
    }


def _expected_profile(
    frame: pd.DataFrame,
    config: dict[str, Any],
    model: RandomForestClassifier,
    calibrator: LogisticRegression,
) -> dict[str, Any]:
    quantiles = [float(value) for value in config["profile_quantiles"]]
    raw_training = model.predict_proba(frame[FEATURES])[
        :, list(model.classes_).index(1)
    ]
    calibrated_training = _calibrate(calibrator, raw_training)
    return {
        "profile_version": 6,
        "feature_order": FEATURES,
        "quantiles": quantiles,
        "features": {
            feature: _profile_feature(
                frame[feature].to_numpy(dtype=float),
                quantiles,
                config["profile_ddof"],
            )
            for feature in FEATURES
        },
        "prediction_profile": _profile_feature(
            calibrated_training,
            quantiles,
            config["profile_ddof"],
        ),
        "disagreement_profile": _profile_feature(
            _tree_disagreement(model, frame[FEATURES]),
            quantiles,
            config["profile_ddof"],
        ),
        "correlation_profile": _correlation_profile(frame[FEATURES]),
        "leaf_profile": _leaf_profile(model, frame[FEATURES]),
        "path_sketch_profile": _path_sketch_profile(
            model,
            frame[FEATURES],
            int(config["path_sketch_buckets"]),
            str(config["path_sketch_salt"]),
        ),
    }

def _assert_float_mapping(actual: dict, expected: dict) -> None:
    assert set(actual) == set(expected)
    for key, expected_value in expected.items():
        actual_value = actual[key]
        if isinstance(expected_value, float):
            _assert_number(actual_value)
            assert actual_value == pytest.approx(expected_value, rel=1e-12, abs=1e-12)
        elif isinstance(expected_value, list):
            assert isinstance(actual_value, list)
            assert len(actual_value) == len(expected_value)
            for left, right in zip(actual_value, expected_value, strict=True):
                _assert_number(left)
                assert left == pytest.approx(right, rel=1e-12, abs=1e-12)
        else:
            assert actual_value == expected_value


def _assert_bundle(data: Path, output: Path) -> dict[str, Any]:
    frame = pd.read_parquet(data)
    config = _config()
    expected = _expected_training(frame, config)
    expected_profile = _expected_profile(
        frame,
        config,
        expected["model"],
        expected["calibrator"],
    )
    model_path = output / "model.joblib"
    calibrator_path = output / "calibrator.joblib"
    metrics_path = output / "metrics.json"
    profile_path = output / "drift_profile.json"
    manifest_path = output / "artifact_manifest.json"
    assert {path.name for path in output.iterdir()} == {
        *ARTIFACT_NAMES,
        "artifact_manifest.json",
    }

    model = joblib.load(model_path)
    calibrator = joblib.load(calibrator_path)
    assert isinstance(model, RandomForestClassifier)
    assert isinstance(calibrator, LogisticRegression)
    champion_config = next(
        candidate
        for candidate in config["candidates"]
        if candidate["name"] == expected["metrics"]["champion"]
    )
    for key, expected_value in _candidate_params(champion_config, config).items():
        assert model.get_params()[key] == expected_value
    assert model.n_features_in_ == len(FEATURES)
    assert np.array_equal(
        model.predict_proba(frame[FEATURES]),
        expected["model"].predict_proba(frame[FEATURES]),
    )
    for key, expected_value in _calibrator_params(config).items():
        assert calibrator.get_params()[key] == expected_value
    assert calibrator.n_features_in_ == 1
    assert list(calibrator.classes_) == [0, 1]
    assert np.array_equal(calibrator.coef_, expected["calibrator"].coef_)
    assert np.array_equal(calibrator.intercept_, expected["calibrator"].intercept_)

    metrics_bytes = metrics_path.read_bytes()
    metrics = json.loads(metrics_bytes)
    assert metrics_bytes == _canonical_bytes(metrics) + b"\n"
    assert set(metrics) == METRICS_KEYS
    for key in (
        "positive_class",
        "training_rows",
        "cv_folds",
        "cv_repeats",
        "random_state",
        "repeat_seed_stride",
    ):
        assert isinstance(metrics[key], int) and not isinstance(metrics[key], bool)
    assert metrics["calibration_method"] == "sigmoid"
    for key in (
        "calibration_c",
        "calibration_intercept",
        "calibration_coefficient",
        "decision_threshold",
        "raw_brier",
        "calibrated_brier",
        "oof_accuracy",
        "oof_f1",
        "worst_repeat_f1",
        "worst_fold_f1",
    ):
        _assert_number(metrics[key])
    assert float(metrics["calibration_c"]) > 0
    for key in (
        "decision_threshold",
        "raw_brier",
        "calibrated_brier",
        "oof_accuracy",
        "oof_f1",
        "worst_repeat_f1",
        "worst_fold_f1",
    ):
        assert 0 <= float(metrics[key]) <= 1
    assert isinstance(metrics["fold_f1"], list)
    assert isinstance(metrics["repeat_f1"], list)
    assert len(metrics["fold_f1"]) == config["cv_folds"] * config["cv_repeats"]
    assert len(metrics["repeat_f1"]) == config["cv_repeats"]
    assert isinstance(metrics["candidate_scores"], list)
    assert len(metrics["candidate_scores"]) == len(config["candidates"])
    for actual_score, expected_score in zip(
        metrics["candidate_scores"],
        expected["metrics"]["candidate_scores"],
        strict=True,
    ):
        assert set(actual_score) == CANDIDATE_SCORE_KEYS
        _assert_float_mapping(actual_score, expected_score)
    top_level_expected = {
        key: value
        for key, value in expected["metrics"].items()
        if key != "candidate_scores"
    }
    _assert_float_mapping(
        {key: metrics[key] for key in top_level_expected},
        top_level_expected,
    )

    profile_bytes = profile_path.read_bytes()
    profile = json.loads(profile_bytes)
    assert profile_bytes == _canonical_bytes(profile) + b"\n"
    assert set(profile) == PROFILE_KEYS
    assert profile["profile_version"] == 6
    assert profile["feature_order"] == FEATURES
    assert profile["quantiles"] == expected_profile["quantiles"]
    assert list(profile["features"]) == FEATURES
    for feature in FEATURES:
        assert set(profile["features"][feature]) == PROFILE_FEATURE_KEYS
        _assert_float_mapping(
            profile["features"][feature],
            expected_profile["features"][feature],
        )
    assert set(profile["prediction_profile"]) == PROFILE_FEATURE_KEYS
    _assert_float_mapping(
        profile["prediction_profile"],
        expected_profile["prediction_profile"],
    )
    assert set(profile["disagreement_profile"]) == PROFILE_FEATURE_KEYS
    _assert_float_mapping(
        profile["disagreement_profile"],
        expected_profile["disagreement_profile"],
    )
    assert set(profile["correlation_profile"]) == CORRELATION_PROFILE_KEYS
    assert profile["correlation_profile"]["metric"] == "spearman_rank"
    actual_pairs = profile["correlation_profile"]["pairs"]
    expected_pairs = expected_profile["correlation_profile"]["pairs"]
    assert len(actual_pairs) == len(CORRELATION_PAIRS)
    assert len(actual_pairs) == len(expected_pairs)
    for actual_pair, expected_pair in zip(actual_pairs, expected_pairs, strict=True):
        assert set(actual_pair) == CORRELATION_PAIR_KEYS
        assert actual_pair["key"] == f"{actual_pair['left']}|{actual_pair['right']}"
        _assert_float_mapping(actual_pair, expected_pair)
    assert set(profile["leaf_profile"]) == LEAF_PROFILE_KEYS
    assert profile["leaf_profile"]["metric"] == "jensen_shannon_natural_log"
    actual_trees = profile["leaf_profile"]["trees"]
    expected_trees = expected_profile["leaf_profile"]["trees"]
    assert len(actual_trees) == model.n_estimators
    assert len(actual_trees) == len(expected_trees)
    for actual_tree, expected_tree in zip(actual_trees, expected_trees, strict=True):
        assert set(actual_tree) == LEAF_TREE_KEYS
        assert actual_tree["leaf_ids"] == expected_tree["leaf_ids"]
        _assert_float_mapping(actual_tree, expected_tree)
    assert set(profile["path_sketch_profile"]) == PATH_SKETCH_PROFILE_KEYS
    assert profile["path_sketch_profile"]["metric"] == "joint_leaf_path_jensen_shannon_natural_log"
    assert profile["path_sketch_profile"]["hash"] == "sha256_first_u64_be_mod"
    assert profile["path_sketch_profile"]["bucket_count"] == config["path_sketch_buckets"]
    assert len(profile["path_sketch_profile"]["bin_proportions"]) == config["path_sketch_buckets"]
    _assert_float_mapping(
        profile["path_sketch_profile"],
        expected_profile["path_sketch_profile"],
    )

    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    assert manifest_bytes == _canonical_bytes(manifest) + b"\n"
    assert set(manifest) == MANIFEST_KEYS
    assert manifest["schema_version"] == 7
    assert manifest["model_version"] == metrics["model_version"]
    assert manifest["champion"] == metrics["champion"]
    assert manifest["feature_order"] == FEATURES
    assert manifest["training_rows"] == len(frame)
    assert manifest["training_parquet_sha256"] == _sha256(data)
    assert manifest["config_sha256"] == _sha256(CONFIG_PATH)
    assert set(manifest["artifact_sha256"]) == set(ARTIFACT_NAMES)
    for name in ARTIFACT_NAMES:
        assert DIGEST_RE.fullmatch(manifest["artifact_sha256"][name])
        assert manifest["artifact_sha256"][name] == _sha256(output / name)
    release_binding = {
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
    assert manifest["release_sha256"] == _digest_bytes(
        _canonical_bytes(release_binding)
    )
    assert DIGEST_RE.fullmatch(manifest["release_sha256"])
    return {
        "model": model,
        "calibrator": calibrator,
        "metrics": metrics,
        "profile": profile,
        "manifest": manifest,
        "candidate_details": expected["candidate_details"],
    }


def _stop_existing_django() -> None:
    subprocess.run(["python", STOP_DJANGO], check=False)
    time.sleep(1)


def _wait_for_api(timeout_seconds: int = 60) -> None:
    last_error = "no response"
    for _ in range(timeout_seconds):
        try:
            response = requests.get(f"{API_URL}/health/", timeout=2)
            if response.status_code == 200:
                return
            last_error = f"status={response.status_code} body={response.text[:200]}"
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(1)
    log_tail = ""
    if DJANGO_LOG.exists():
        log_tail = DJANGO_LOG.read_text(encoding="utf-8")[-2000:]
    raise RuntimeError(f"API startup failed: {last_error}\n{log_tail}")


@pytest.fixture(scope="session")
def django_server() -> Generator[str, None, None]:
    """Start a deterministic local API used by drift integration tests."""
    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "drift_api.settings"
    _stop_existing_django()
    database = DJANGO_DIR / "db.sqlite3"
    database.unlink(missing_ok=True)
    subprocess.run(
        ["python", "manage.py", "migrate", "--noinput"],
        cwd=DJANGO_DIR,
        env=env,
        check=True,
    )
    subprocess.run(
        ["python", "manage.py", "seed_records"],
        cwd=DJANGO_DIR,
        env=env,
        check=True,
    )
    log_handle = DJANGO_LOG.open("w", encoding="utf-8")
    process = subprocess.Popen(
        ["python", "manage.py", "runserver", "127.0.0.1:8000", "--noreload"],
        cwd=DJANGO_DIR,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )
    try:
        _wait_for_api()
        yield API_URL
    finally:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
        log_handle.close()


@pytest.fixture(scope="session")
def trained_default_bundle() -> Path:
    """Train and validate the default release once for drift tests."""
    shutil.rmtree(DEFAULT_ARTIFACTS, ignore_errors=True)
    _run_train(DEFAULT_DATA, DEFAULT_ARTIFACTS)
    _assert_bundle(DEFAULT_DATA, DEFAULT_ARTIFACTS)
    return DEFAULT_ARTIFACTS


def _is_prefect_timeout(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode != 0 and (
        "TimeoutError" in result.stderr
        or "Timed out while attempting to connect to ephemeral Prefect API server"
        in result.stderr
    )


def _retry_prefect(
    run_once: Callable[[], subprocess.CompletedProcess[str]],
) -> subprocess.CompletedProcess[str]:
    last_result: subprocess.CompletedProcess[str] | None = None
    for attempt in range(3):
        result = run_once()
        if result.returncode == 0:
            return result
        if _is_prefect_timeout(result) and attempt < 2:
            last_result = result
            time.sleep(5 * (attempt + 1))
            continue
        return result
    assert last_result is not None
    return last_result


def _run_drift(
    batch_id: str,
    *,
    api_url: str = API_URL,
    data: Path = DEFAULT_DATA,
    artifacts: Path = DEFAULT_ARTIFACTS,
    minimal: bool = False,
) -> subprocess.CompletedProcess[str]:
    def run_once() -> subprocess.CompletedProcess[str]:
        command = [CLI, "run-drift", "--batch-id", batch_id]
        if not minimal:
            command.extend(
                [
                    "--api-url",
                    api_url,
                    "--data",
                    str(data),
                    "--artifacts-dir",
                    str(artifacts),
                ]
            )
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=600,
        )

    return _retry_prefect(run_once)


def _fetch_batch_payload(batch_id: str, api_url: str = API_URL) -> dict[str, Any]:
    url = f"{api_url}/inference-batches/{batch_id}/"
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
        assert isinstance(payload, dict)
        assert set(payload) == PAGE_KEYS
        assert payload["batch_id"] == batch_id
        assert payload["cursor"] == cursor
        binding = {
            "batch_id": payload["batch_id"],
            "cursor": payload["cursor"],
            "records": payload["records"],
            "next_cursor": payload["next_cursor"],
        }
        assert payload["page_sha256"] == _digest_bytes(_canonical_bytes(binding))
        assert DIGEST_RE.fullmatch(payload["page_sha256"])
        assert payload["records"]
        for record in payload["records"]:
            assert set(record) == {"id", "features"}
            assert isinstance(record["id"], int) and not isinstance(record["id"], bool)
            assert record["id"] not in seen_ids
            assert set(record["features"]) == set(FEATURES)
            for feature in FEATURES:
                _assert_number(record["features"][feature])
            seen_ids.add(record["id"])
            records.append(record)
        page_digests.append(payload["page_sha256"])
        next_cursor = payload["next_cursor"]
        if next_cursor is None:
            break
        assert isinstance(next_cursor, int) and not isinstance(next_cursor, bool)
        assert next_cursor not in seen_cursors
        if cursor is not None:
            assert next_cursor > cursor
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    transcript = "".join(f"{value}\n" for value in page_digests).encode("utf-8")
    return {
        "batch_id": batch_id,
        "records": records,
        "source_page_count": len(page_digests),
        "batch_source_digest": _digest_bytes(transcript),
    }


def _fetch_batch(batch_id: str, api_url: str = API_URL) -> list[dict]:
    return _fetch_batch_payload(batch_id, api_url)["records"]


def _psi_from_profile(
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


def _correlation_deltas(
    features: pd.DataFrame,
    profile: dict[str, Any],
) -> dict[str, float]:
    observed = _correlation_profile(features)
    deltas: dict[str, float] = {}
    for stored_pair, observed_pair in zip(
        profile["pairs"],
        observed["pairs"],
        strict=True,
    ):
        assert stored_pair["key"] == observed_pair["key"]
        deltas[stored_pair["key"]] = abs(
            float(observed_pair["coefficient"])
            - float(stored_pair["coefficient"])
        )
    return deltas


def _leaf_js_divergences(
    model: RandomForestClassifier,
    batch: pd.DataFrame,
    leaf_profile: dict[str, Any],
    epsilon: float,
) -> list[float]:
    leaves = model.apply(batch)
    divergences: list[float] = []
    for tree_number, stored in enumerate(leaf_profile["trees"]):
        observed_ids, counts = np.unique(
            leaves[:, tree_number].astype(int),
            return_counts=True,
        )
        expected_map = dict(
            zip(stored["leaf_ids"], stored["bin_proportions"], strict=True)
        )
        actual_map = {
            int(leaf_id): float(count) / len(batch)
            for leaf_id, count in zip(observed_ids, counts, strict=True)
        }
        support = sorted(set(expected_map) | set(actual_map))
        expected = np.asarray(
            [float(expected_map.get(leaf_id, 0.0)) for leaf_id in support]
        )
        actual = np.asarray(
            [float(actual_map.get(leaf_id, 0.0)) for leaf_id in support]
        )
        expected = expected + epsilon
        actual = actual + epsilon
        expected = expected / expected.sum()
        actual = actual / actual.sum()
        midpoint = (expected + actual) / 2.0
        divergence = 0.5 * float(np.sum(expected * np.log(expected / midpoint)))
        divergence += 0.5 * float(np.sum(actual * np.log(actual / midpoint)))
        divergences.append(divergence)
    return divergences


def _path_sketch_js_divergence(
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


def _expected_feature_stats(
    batch: pd.DataFrame,
    reference: pd.DataFrame,
    profile: dict[str, Any],
    config: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    feature_stats: dict[str, dict[str, Any]] = {}
    drifted_features: list[str] = []
    for feature in FEATURES:
        batch_values = batch[feature].to_numpy(dtype=float)
        reference_values = reference[feature].to_numpy(dtype=float)
        statistic = float(ks_2samp(reference_values, batch_values).statistic)
        psi = _psi_from_profile(
            batch_values,
            profile["features"][feature],
            float(config["psi_epsilon"]),
        )
        drifted = (
            statistic > config["drift_ks_threshold"]
            or psi > config["drift_psi_threshold"]
        )
        feature_stats[feature] = {
            "mean": float(np.mean(batch_values)),
            "std": float(np.std(batch_values, ddof=0)),
            "ks_statistic": statistic,
            "psi": psi,
            "drifted": drifted,
        }
        if drifted:
            drifted_features.append(feature)
    return feature_stats, drifted_features


def _expected_evaluation(
    batch_id: str,
    batch_payload: dict[str, Any],
    artifacts: Path,
    data: Path,
) -> dict[str, Any]:
    records = sorted(
        batch_payload["records"],
        key=lambda record: int(record["id"]),
    )
    manifest = json.loads(
        (artifacts / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    metrics = json.loads((artifacts / "metrics.json").read_text(encoding="utf-8"))
    profile = json.loads((artifacts / "drift_profile.json").read_text(encoding="utf-8"))
    config = _config()
    model = joblib.load(artifacts / "model.joblib")
    calibrator = joblib.load(artifacts / "calibrator.joblib")
    batch = pd.DataFrame(
        [
            {feature: record["features"][feature] for feature in FEATURES}
            for record in records
        ],
        columns=FEATURES,
    )
    raw_probabilities = model.predict_proba(batch)[:, list(model.classes_).index(1)]
    probabilities = _calibrate(calibrator, raw_probabilities)
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
    reference = pd.read_parquet(data)
    feature_stats, drifted_features = _expected_feature_stats(
        batch,
        reference,
        profile,
        config,
    )
    prediction_psi = _psi_from_profile(
        probabilities,
        profile["prediction_profile"],
        float(config["psi_epsilon"]),
    )
    prediction_drifted = prediction_psi > config["prediction_drift_psi_threshold"]
    disagreements = _tree_disagreement(model, batch)
    disagreement_psi = _psi_from_profile(
        disagreements,
        profile["disagreement_profile"],
        float(config["psi_epsilon"]),
    )
    disagreement_drifted = (
        disagreement_psi > config["disagreement_drift_psi_threshold"]
    )
    correlation_deltas = _correlation_deltas(
        batch,
        profile["correlation_profile"],
    )
    correlation_drift_score = max(correlation_deltas.values())
    correlation_drifted = (
        correlation_drift_score > config["correlation_drift_threshold"]
    )
    leaf_values = _leaf_js_divergences(
        model,
        batch,
        profile["leaf_profile"],
        float(config["leaf_js_epsilon"]),
    )
    leaf_score = float(
        np.quantile(
            np.asarray(leaf_values, dtype=float),
            float(config["leaf_drift_quantile"]),
            method="linear",
        )
    )
    leaf_drifted = leaf_score > config["leaf_drift_threshold"]
    path_profile = profile["path_sketch_profile"]
    path_assignments = _path_sketch_assignments(
        model,
        batch,
        int(path_profile["bucket_count"]),
        str(path_profile["salt"]),
    )
    path_transcript = "".join(
        f"{int(record['id'])}:{int(bucket)}\n"
        for record, bucket in zip(records, path_assignments, strict=True)
    ).encode("utf-8")
    path_score = _path_sketch_js_divergence(
        path_assignments,
        path_profile,
        float(config["path_sketch_epsilon"]),
    )
    path_drifted = path_score > config["path_sketch_drift_threshold"]
    return {
        "batch_id": batch_id,
        "model_version": manifest["model_version"],
        "champion": manifest["champion"],
        "training_oof_f1": metrics["oof_f1"],
        "training_calibrated_brier": metrics["calibrated_brier"],
        "decision_threshold": metrics["decision_threshold"],
        "source_page_count": batch_payload["source_page_count"],
        "batch_source_digest": batch_payload["batch_source_digest"],
        "prediction_count": len(predictions),
        "positive_predictions": int(predictions.sum()),
        "mean_raw_positive_probability": float(np.mean(raw_probabilities)),
        "mean_positive_probability": float(np.mean(probabilities)),
        "prediction_digest": _digest_bytes(prediction_transcript),
        "prediction_psi": prediction_psi,
        "prediction_drifted": prediction_drifted,
        "mean_tree_disagreement": float(np.mean(disagreements)),
        "disagreement_psi": disagreement_psi,
        "disagreement_drifted": disagreement_drifted,
        "correlation_deltas": correlation_deltas,
        "correlation_drift_score": correlation_drift_score,
        "correlation_drifted": correlation_drifted,
        "leaf_js_divergences": leaf_values,
        "leaf_drift_score": leaf_score,
        "leaf_drifted": leaf_drifted,
        "path_sketch_digest": _digest_bytes(path_transcript),
        "path_sketch_js": path_score,
        "path_sketch_drifted": path_drifted,
        "drift_detected": (
            len(drifted_features) >= config["drift_feature_quorum"]
            or prediction_drifted
            or disagreement_drifted
            or correlation_drifted
            or leaf_drifted
            or path_drifted
        ),
        "drifted_features": drifted_features,
        "feature_stats": feature_stats,
    }

def _latest_evaluation(batch_id: str, api_url: str = API_URL) -> dict:
    response = requests.get(f"{api_url}/drift-evaluations/", timeout=30)
    response.raise_for_status()
    matching = [record for record in response.json() if record["batch_id"] == batch_id]
    assert matching
    return max(matching, key=lambda record: record["id"])


def _assert_evaluation(
    batch_id: str,
    stdout: str,
    artifacts: Path = DEFAULT_ARTIFACTS,
    data: Path = DEFAULT_DATA,
) -> dict[str, Any]:
    expected = _expected_evaluation(
        batch_id,
        _fetch_batch_payload(batch_id),
        artifacts,
        data,
    )
    actual = _latest_evaluation(batch_id)
    assert set(actual) == {
        "id",
        "batch_id",
        "model_version",
        "champion",
        "training_oof_f1",
        "training_calibrated_brier",
        "decision_threshold",
        "source_page_count",
        "batch_source_digest",
        "prediction_count",
        "positive_predictions",
        "mean_raw_positive_probability",
        "mean_positive_probability",
        "prediction_digest",
        "prediction_psi",
        "prediction_drifted",
        "mean_tree_disagreement",
        "disagreement_psi",
        "disagreement_drifted",
        "correlation_deltas",
        "correlation_drift_score",
        "correlation_drifted",
        "leaf_js_divergences",
        "leaf_drift_score",
        "leaf_drifted",
        "path_sketch_digest",
        "path_sketch_js",
        "path_sketch_drifted",
        "drift_detected",
        "drifted_features",
        "feature_stats",
        "created_at",
    }
    match = re.fullmatch(r"submitted drift evaluation id (\d+)\n?", stdout)
    assert match is not None
    assert int(match.group(1)) == actual["id"]
    for key in (
        "batch_id",
        "model_version",
        "champion",
        "source_page_count",
        "batch_source_digest",
        "prediction_count",
        "positive_predictions",
        "prediction_digest",
        "prediction_drifted",
        "disagreement_drifted",
        "correlation_drifted",
        "leaf_drifted",
        "path_sketch_digest",
        "path_sketch_drifted",
        "drift_detected",
        "drifted_features",
    ):
        assert actual[key] == expected[key]
    for key in (
        "training_oof_f1",
        "training_calibrated_brier",
        "decision_threshold",
        "mean_raw_positive_probability",
        "mean_positive_probability",
        "prediction_psi",
        "mean_tree_disagreement",
        "disagreement_psi",
        "correlation_drift_score",
        "leaf_drift_score",
        "path_sketch_js",
    ):
        _assert_number(actual[key])
        assert actual[key] == pytest.approx(expected[key], rel=1e-12, abs=1e-12)
    assert DIGEST_RE.fullmatch(actual["prediction_digest"])
    assert DIGEST_RE.fullmatch(actual["path_sketch_digest"])
    assert list(actual["correlation_deltas"]) == CORRELATION_KEYS
    for key in CORRELATION_KEYS:
        _assert_number(actual["correlation_deltas"][key])
        assert 0 <= actual["correlation_deltas"][key] <= 2
        assert actual["correlation_deltas"][key] == pytest.approx(
            expected["correlation_deltas"][key],
            rel=1e-12,
            abs=1e-12,
        )
    assert actual["correlation_drift_score"] == pytest.approx(
        max(actual["correlation_deltas"].values()),
        rel=1e-12,
        abs=1e-12,
    )
    assert list(actual["feature_stats"]) == FEATURES
    for feature in FEATURES:
        assert set(actual["feature_stats"][feature]) == {
            "mean",
            "std",
            "ks_statistic",
            "psi",
            "drifted",
        }
        for stat_name in ("mean", "std", "ks_statistic", "psi"):
            _assert_number(actual["feature_stats"][feature][stat_name])
            assert actual["feature_stats"][feature][stat_name] == pytest.approx(
                expected["feature_stats"][feature][stat_name],
                rel=1e-12,
                abs=1e-12,
            )
        assert (
            actual["feature_stats"][feature]["drifted"]
            is expected["feature_stats"][feature]["drifted"]
        )
    assert len(actual["leaf_js_divergences"]) == len(expected["leaf_js_divergences"])
    for left, right in zip(
        actual["leaf_js_divergences"],
        expected["leaf_js_divergences"],
        strict=True,
    ):
        _assert_number(left)
        assert left == pytest.approx(right, rel=1e-12, abs=1e-12)
    assert DIGEST_RE.fullmatch(actual["batch_source_digest"])
    return actual


def _insert_batch(batch_id: str, frame: pd.DataFrame, tmp_path: Path) -> None:
    payload_path = tmp_path / f"{batch_id}.json"
    records = [
        {
            "id": int(row["id"]),
            "features": {feature: float(row[feature]) for feature in FEATURES},
        }
        for _, row in frame.iterrows()
    ]
    payload_path.write_text(
        json.dumps({"batch_id": batch_id, "records": records}),
        encoding="utf-8",
    )
    code = f"""
import json
from pathlib import Path
from monitoring.models import InferenceRecord
payload = json.loads(Path({str(payload_path)!r}).read_text(encoding='utf-8'))
InferenceRecord.objects.filter(batch_id=payload['batch_id']).delete()
InferenceRecord.objects.bulk_create([
    InferenceRecord(
        id=record['id'],
        batch_id=payload['batch_id'],
        features=record['features'],
    )
    for record in payload['records']
])
"""
    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "drift_api.settings"
    subprocess.run(
        ["python", "manage.py", "shell", "-c", code],
        cwd=DJANGO_DIR,
        env=env,
        check=True,
    )


def _fresh_training_frame(
    rows: int,
    weights: list[float],
    seed: int,
    id_start: int,
) -> pd.DataFrame:
    features, labels = make_classification(
        n_samples=rows,
        n_features=4,
        n_informative=4,
        n_redundant=0,
        weights=weights,
        class_sep=0.85,
        random_state=seed,
    )
    frame = pd.DataFrame(features, columns=FEATURES)
    frame.insert(0, "id", range(id_start, id_start + rows))
    frame["label"] = labels.astype(int)
    return frame


def _dynamic_policy(
    base: dict[str, Any],
    *,
    version: str,
    folds: int,
    candidates: list[dict[str, Any]],
    quantiles: list[float],
    calibration_c: float,
    repeats: int | None = None,
    repeat_seed_stride: int | None = None,
    path_sketch_buckets: int | None = None,
    path_sketch_salt: str | None = None,
    prediction_drift_threshold: float | None = None,
) -> dict[str, Any]:
    policy = copy.deepcopy(base)
    policy["model_version"] = version
    policy["cv_folds"] = folds
    policy["candidates"] = candidates
    policy["profile_quantiles"] = quantiles
    policy["calibration_c"] = calibration_c
    if repeats is not None:
        policy["cv_repeats"] = repeats
    if repeat_seed_stride is not None:
        policy["repeat_seed_stride"] = repeat_seed_stride
    if path_sketch_buckets is not None:
        policy["path_sketch_buckets"] = path_sketch_buckets
    if path_sketch_salt is not None:
        policy["path_sketch_salt"] = path_sketch_salt
    if prediction_drift_threshold is not None:
        policy["prediction_drift_psi_threshold"] = prediction_drift_threshold
    return policy


def _find_stable_sample(
    reference: pd.DataFrame,
    profile: dict[str, Any],
    config: dict[str, Any],
    rows: int,
    id_start: int,
    artifacts: Path = DEFAULT_ARTIFACTS,
) -> pd.DataFrame:
    model = joblib.load(artifacts / "model.joblib")
    calibrator = joblib.load(artifacts / "calibrator.joblib")
    for seed in range(100, 700):
        candidate = (
            reference[FEATURES]
            .sample(n=rows, replace=True, random_state=seed)
            .reset_index(drop=True)
        )
        stats, drifted = _expected_feature_stats(
            candidate,
            reference,
            profile,
            config,
        )
        raw = model.predict_proba(candidate)[:, list(model.classes_).index(1)]
        calibrated = _calibrate(calibrator, raw)
        prediction_psi = _psi_from_profile(
            calibrated,
            profile["prediction_profile"],
            float(config["psi_epsilon"]),
        )
        disagreements = _tree_disagreement(model, candidate)
        disagreement_psi = _psi_from_profile(
            disagreements,
            profile["disagreement_profile"],
            float(config["psi_epsilon"]),
        )
        leaf_values = _leaf_js_divergences(
            model,
            candidate,
            profile["leaf_profile"],
            float(config["leaf_js_epsilon"]),
        )
        leaf_score = float(
            np.quantile(
                np.asarray(leaf_values, dtype=float),
                float(config["leaf_drift_quantile"]),
                method="linear",
            )
        )
        correlation_score = max(
            _correlation_deltas(
                candidate,
                profile["correlation_profile"],
            ).values()
        )
        path_profile = profile["path_sketch_profile"]
        path_assignments = _path_sketch_assignments(
            model,
            candidate,
            int(path_profile["bucket_count"]),
            str(path_profile["salt"]),
        )
        path_score = _path_sketch_js_divergence(
            path_assignments,
            path_profile,
            float(config["path_sketch_epsilon"]),
        )
        if (
            not drifted
            and prediction_psi <= config["prediction_drift_psi_threshold"]
            and disagreement_psi <= config["disagreement_drift_psi_threshold"]
            and correlation_score <= config["correlation_drift_threshold"]
            and leaf_score <= config["leaf_drift_threshold"]
            and path_score <= config["path_sketch_drift_threshold"]
            and all(stats[name]["psi"] >= 0 for name in FEATURES)
        ):
            candidate.insert(0, "id", range(id_start, id_start + rows))
            return candidate
    raise AssertionError("could not generate a non-drifted dynamic batch")


def test_cli_surface_is_executable_and_complete() -> None:
    """The documented executable CLI exposes both release workflow commands."""
    assert os.access(CLI, os.X_OK)
    result = subprocess.run(
        [CLI, "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stderr == ""
    assert re.search(r"(?<![A-Za-z0-9_-])train(?![A-Za-z0-9_-])", result.stdout)
    assert re.search(
        r"(?<![A-Za-z0-9_-])run-drift(?![A-Za-z0-9_-])",
        result.stdout,
    )


def test_train_builds_cross_validated_champion_bundle(tmp_path: Path) -> None:
    """Default training matches independent OOF selection, full-data refit, schemas, and release hashes."""
    output = tmp_path / "bundle"
    result = _run_train(DEFAULT_DATA, output)
    bundle = _assert_bundle(DEFAULT_DATA, output)
    metrics = bundle["metrics"]
    expected_stdout = (
        f"trained {metrics['model_version']} champion {metrics['champion']} "
        f"oof_f1 {metrics['oof_f1']:.3f} "
        f"worst_repeat_f1 {metrics['worst_repeat_f1']:.3f} "
        f"worst_fold_f1 {metrics['worst_fold_f1']:.3f} "
        f"calibrated_brier {metrics['calibrated_brier']:.6f} "
        f"threshold {metrics['decision_threshold']:.6f}\n"
    )
    assert result.stdout == expected_stdout


def test_dynamic_training_variants_defeat_static_bundle(tmp_path: Path) -> None:
    """Two unseen data/policy pairs require fresh candidates, classifications, profiles, and digests."""
    base = _config()
    cases = [
        (
            _fresh_training_frame(151, [0.73, 0.27], 704, 41000),
            _dynamic_policy(
                base,
                version="fresh-release-alpha",
                folds=3,
                candidates=[
                    {
                        "name": "alpha-balanced",
                        "n_estimators": 29,
                        "max_depth": 4,
                        "min_samples_leaf": 2,
                        "class_weight": "balanced",
                    },
                    {
                        "name": "alpha-plain",
                        "n_estimators": 41,
                        "max_depth": 7,
                        "min_samples_leaf": 1,
                        "class_weight": None,
                    },
                ],
                quantiles=[0.15, 0.5, 0.85],
                calibration_c=0.35,
                repeats=2,
                repeat_seed_stride=809,
                path_sketch_buckets=17,
                path_sketch_salt="fresh-alpha-path-sketch",
            ),
        ),
        (
            _fresh_training_frame(233, [0.44, 0.56], 705, 52000),
            _dynamic_policy(
                base,
                version="fresh-release-beta",
                folds=5,
                candidates=[
                    {
                        "name": "beta-leaf",
                        "n_estimators": 31,
                        "max_depth": 5,
                        "min_samples_leaf": 3,
                        "class_weight": "balanced_subsample",
                    },
                    {
                        "name": "beta-deep",
                        "n_estimators": 43,
                        "max_depth": 9,
                        "min_samples_leaf": 1,
                        "class_weight": None,
                    },
                    {
                        "name": "beta-compact",
                        "n_estimators": 23,
                        "max_depth": 4,
                        "min_samples_leaf": 1,
                        "class_weight": "balanced",
                    },
                ],
                quantiles=[0.1, 0.3, 0.7, 0.9],
                calibration_c=1.7,
                repeats=3,
                repeat_seed_stride=1301,
                path_sketch_buckets=31,
                path_sketch_salt="fresh-beta-path-sketch",
            ),
        ),
    ]
    observed = []
    for index, (frame, policy) in enumerate(cases):
        data = tmp_path / f"fresh-training-{index}.parquet"
        output = tmp_path / f"fresh-bundle-{index}"
        frame.to_parquet(data, index=False)
        with _temporary_config(policy):
            result = _run_train(data, output)
            bundle = _assert_bundle(data, output)
            candidate_names = [
                item["name"] for item in bundle["metrics"]["candidate_scores"]
            ]
            assert bundle["metrics"]["champion"] in result.stdout
            assert candidate_names == [item["name"] for item in policy["candidates"]]
            assert bundle["metrics"]["champion"] in candidate_names
            assert bundle["manifest"]["model_version"] == policy["model_version"]
            assert (
                bundle["profile"]["path_sketch_profile"]["bucket_count"]
                == policy["path_sketch_buckets"]
            )
            assert (
                bundle["profile"]["path_sketch_profile"]["salt"]
                == policy["path_sketch_salt"]
            )
            observed.append(
                (
                    bundle["metrics"]["champion"],
                    bundle["metrics"]["decision_threshold"],
                    bundle["metrics"]["oof_f1"],
                    bundle["metrics"]["calibrated_brier"],
                    bundle["metrics"]["calibration_c"],
                    bundle["metrics"]["calibration_coefficient"],
                    bundle["metrics"]["cv_repeats"],
                    bundle["metrics"]["repeat_seed_stride"],
                    bundle["metrics"]["repeat_f1"],
                    bundle["profile"]["prediction_profile"],
                    bundle["profile"]["disagreement_profile"],
                    bundle["profile"]["path_sketch_profile"],
                    bundle["manifest"]["training_rows"],
                    bundle["manifest"]["training_parquet_sha256"],
                    bundle["manifest"]["config_sha256"],
                    bundle["manifest"]["release_sha256"],
                )
            )
    default_rows = len(pd.read_parquet(DEFAULT_DATA))
    assert observed[0] != observed[1]
    assert observed[0][12] == 151 and observed[1][12] == 233
    assert all(item[12] != default_rows for item in observed)
    assert observed[0][4] != observed[1][4]
    assert observed[0][5] != observed[1][5]
    assert observed[0][6:] != observed[1][6:]
    assert observed[0][6] == 2 and observed[1][6] == 3
    assert observed[0][7] == 809 and observed[1][7] == 1301
    assert len(observed[0][8]) == 2 and len(observed[1][8]) == 3
    assert observed[0][14] != observed[1][14]
    assert observed[0][15] != observed[1][15]
    assert all(item[13] != _sha256(DEFAULT_DATA) for item in observed)


def test_champion_tie_break_uses_complexity_then_name(tmp_path: Path) -> None:
    """Perfectly separable candidates tie on F1 so lower complexity then lexical name decides."""
    rows = 120
    labels = np.array([0, 1] * (rows // 2), dtype=int)
    frame = pd.DataFrame(
        {
            "id": range(61000, 61000 + rows),
            "feature_0": labels.astype(float) * 10.0,
            "feature_1": labels.astype(float) * -4.0,
            "feature_2": np.zeros(rows),
            "feature_3": np.ones(rows),
            "label": labels,
        },
        columns=INPUT_COLUMNS,
    )
    policy = _dynamic_policy(
        _config(),
        version="tie-break-release",
        folds=4,
        candidates=[
            {
                "name": "large",
                "n_estimators": 17,
                "max_depth": 5,
                "min_samples_leaf": 1,
                "class_weight": None,
            },
            {
                "name": "small-z",
                "n_estimators": 5,
                "max_depth": 2,
                "min_samples_leaf": 1,
                "class_weight": None,
            },
            {
                "name": "small-a",
                "n_estimators": 5,
                "max_depth": 2,
                "min_samples_leaf": 1,
                "class_weight": None,
            },
        ],
        quantiles=[0.25, 0.5, 0.75],
        calibration_c=0.8,
    )
    data = tmp_path / "tie.parquet"
    output = tmp_path / "tie-bundle"
    frame.to_parquet(data, index=False)
    with _temporary_config(policy):
        _run_train(data, output)
        bundle = _assert_bundle(data, output)
    scores = bundle["metrics"]["candidate_scores"]
    assert all(score["oof_f1"] == pytest.approx(1.0) for score in scores)
    assert all(score["worst_repeat_f1"] == pytest.approx(1.0) for score in scores)
    assert all(score["worst_fold_f1"] == pytest.approx(1.0) for score in scores)
    assert all(
        score["calibrated_brier"]
        == pytest.approx(scores[0]["calibrated_brier"], rel=0, abs=0)
        for score in scores
    )
    assert bundle["metrics"]["champion"] == "small-a"


def test_repeated_training_is_byte_reproducible(tmp_path: Path) -> None:
    """Identical inputs reproduce every JSON byte and all release/artifact bindings."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    _run_train(DEFAULT_DATA, first)
    _run_train(DEFAULT_DATA, second)
    for name in (*ARTIFACT_NAMES, "artifact_manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    first_manifest = json.loads((first / "artifact_manifest.json").read_text())
    second_manifest = json.loads((second / "artifact_manifest.json").read_text())
    assert first_manifest == second_manifest


def test_run_drift_scores_static_batches_with_prefect(
    django_server: str,
    trained_default_bundle: Path,
) -> None:
    """The named Prefect flow submits every independently derived marginal, uncertainty, and path channel."""
    shifted = _run_drift("batch-shifted", api_url=django_server)
    shifted.check_returncode()
    assert PREFECT_FLOW in shifted.stderr
    for task_name in PREFECT_TASKS:
        assert f"task '{task_name}'" in shifted.stderr
    shifted_record = _assert_evaluation("batch-shifted", shifted.stdout)
    assert shifted_record["drift_detected"] is True

    stable = _run_drift("batch-stable", minimal=True)
    stable.check_returncode()
    stable_record = _assert_evaluation("batch-stable", stable.stdout)
    assert stable_record["drift_detected"] is False


def test_dynamic_variant_defeats_hardcoded_solution(
    django_server: str,
    trained_default_bundle: Path,
    tmp_path: Path,
) -> None:
    """Fresh ids, sizes, probabilities, predictions, distributions, and report digests drive submissions."""
    reference = pd.read_parquet(DEFAULT_DATA)
    profile = json.loads(
        (DEFAULT_ARTIFACTS / "drift_profile.json").read_text(encoding="utf-8")
    )
    config = _config()
    stable = _find_stable_sample(reference, profile, config, 83, 71001)
    shifted = _find_stable_sample(reference, profile, config, 47, 82001)
    shifted["feature_0"] += 7.5
    shifted["feature_2"] -= 6.0
    cases = [
        ("fresh-stable-83", stable),
        ("fresh-shifted-47", shifted),
    ]
    seeded_digest = _expected_evaluation(
        "batch-stable",
        _fetch_batch_payload("batch-stable"),
        DEFAULT_ARTIFACTS,
        DEFAULT_DATA,
    )["prediction_digest"]
    observed = []
    for batch_id, frame in cases:
        _insert_batch(batch_id, frame, tmp_path)
        fetched_ids = sorted(
            record["id"] for record in _fetch_batch(batch_id, django_server)
        )
        assert fetched_ids == sorted(frame["id"].astype(int).tolist())
        result = _run_drift(batch_id, api_url=django_server)
        result.check_returncode()
        record = _assert_evaluation(batch_id, result.stdout)
        assert record["batch_id"] == batch_id
        assert record["prediction_count"] == len(frame)
        assert record["source_page_count"] == math.ceil(
            len(frame) / int(config["inference_page_size"])
        )
        assert record["source_page_count"] > 1
        assert record["prediction_digest"] != seeded_digest
        assert record["leaf_js_divergences"]
        assert record["leaf_drift_score"] >= 0
        assert record["mean_raw_positive_probability"] != pytest.approx(
            record["mean_positive_probability"]
        )
        assert record["prediction_psi"] >= 0
        observed.append(record)
    assert observed[0]["drift_detected"] is False
    assert observed[1]["drift_detected"] is True
    assert observed[0]["prediction_digest"] != observed[1]["prediction_digest"]
    assert (
        observed[0]["mean_positive_probability"]
        != observed[1]["mean_positive_probability"]
    )
    assert observed[0]["prediction_psi"] != observed[1]["prediction_psi"]
    assert (
        observed[0]["mean_tree_disagreement"]
        != observed[1]["mean_tree_disagreement"]
    )
    assert observed[0]["disagreement_psi"] != observed[1]["disagreement_psi"]
    assert observed[0]["path_sketch_digest"] != observed[1]["path_sketch_digest"]
    assert observed[0]["path_sketch_js"] != observed[1]["path_sketch_js"]
    assert observed[0]["feature_stats"] != observed[1]["feature_stats"]
    assert observed[0]["batch_source_digest"] != observed[1]["batch_source_digest"]
    assert observed[0]["correlation_deltas"] != observed[1]["correlation_deltas"]
    assert (
        observed[0]["correlation_drift_score"]
        != observed[1]["correlation_drift_score"]
    )
    assert observed[0]["leaf_js_divergences"] != observed[1]["leaf_js_divergences"]


def test_prediction_drift_couples_calibration_profile_to_final_decision(
    django_server: str,
    tmp_path: Path,
) -> None:
    """Calibrated prediction PSI alone can trigger overall drift while feature rules stay false."""
    reference = pd.read_parquet(DEFAULT_DATA)
    policy = copy.deepcopy(_config())
    policy["model_version"] = "prediction-drift-release"
    policy["drift_ks_threshold"] = 999.0
    policy["drift_psi_threshold"] = 999.0
    policy["drift_feature_quorum"] = 4
    policy["prediction_drift_psi_threshold"] = 0.4
    policy["disagreement_drift_psi_threshold"] = 999.0
    policy["correlation_drift_threshold"] = 2.0
    policy["leaf_drift_threshold"] = math.log(2.0)
    policy["path_sketch_drift_threshold"] = math.log(2.0)
    artifacts = tmp_path / "prediction-drift-bundle"
    with _temporary_config(policy):
        _run_train(DEFAULT_DATA, artifacts)
        bundle = _assert_bundle(DEFAULT_DATA, artifacts)
        profile = bundle["profile"]
        stable = _find_stable_sample(
            reference,
            profile,
            policy,
            101,
            121001,
            artifacts,
        )
        model = bundle["model"]
        calibrator = bundle["calibrator"]
        raw_reference = model.predict_proba(reference[FEATURES])[
            :, list(model.classes_).index(1)
        ]
        calibrated_reference = _calibrate(calibrator, raw_reference)
        extreme_index = int(np.argmax(calibrated_reference))
        extreme = pd.DataFrame(
            np.repeat(
                reference.loc[[extreme_index], FEATURES].to_numpy(dtype=float),
                79,
                axis=0,
            ),
            columns=FEATURES,
        )
        extreme.insert(0, "id", range(123001, 123001 + len(extreme)))
        extreme_raw = model.predict_proba(extreme[FEATURES])[
            :, list(model.classes_).index(1)
        ]
        extreme_calibrated = _calibrate(calibrator, extreme_raw)
        extreme_psi = _psi_from_profile(
            extreme_calibrated,
            profile["prediction_profile"],
            float(policy["psi_epsilon"]),
        )
        assert extreme_psi > policy["prediction_drift_psi_threshold"]

        observed = []
        for batch_id, frame in (
            ("prediction-stable", stable),
            ("prediction-extreme", extreme),
        ):
            _insert_batch(batch_id, frame, tmp_path)
            result = _run_drift(
                batch_id,
                api_url=django_server,
                artifacts=artifacts,
            )
            result.check_returncode()
            observed.append(
                _assert_evaluation(
                    batch_id,
                    result.stdout,
                    artifacts=artifacts,
                )
            )
        assert observed[0]["drifted_features"] == []
        assert observed[0]["prediction_drifted"] is False
        assert observed[0]["disagreement_drifted"] is False
        assert observed[0]["correlation_drifted"] is False
        assert observed[0]["leaf_drifted"] is False
        assert observed[0]["path_sketch_drifted"] is False
        assert observed[0]["drift_detected"] is False
        assert observed[1]["drifted_features"] == []
        assert observed[1]["prediction_drifted"] is True
        assert observed[1]["disagreement_drifted"] is False
        assert observed[1]["correlation_drifted"] is False
        assert observed[1]["leaf_drifted"] is False
        assert observed[1]["path_sketch_drifted"] is False
        assert observed[1]["drift_detected"] is True
        assert observed[0]["prediction_digest"] != observed[1]["prediction_digest"]



def test_tree_disagreement_drift_couples_forest_uncertainty_to_final_decision(
    django_server: str,
    tmp_path: Path,
) -> None:
    """Tree-probability disagreement PSI independently controls the final drift decision."""
    reference = pd.read_parquet(DEFAULT_DATA)
    policy = copy.deepcopy(_config())
    policy["model_version"] = "tree-disagreement-release"
    policy["drift_ks_threshold"] = 999.0
    policy["drift_psi_threshold"] = 999.0
    policy["drift_feature_quorum"] = 4
    policy["prediction_drift_psi_threshold"] = 999.0
    policy["correlation_drift_threshold"] = 2.0
    policy["leaf_drift_threshold"] = math.log(2.0)
    policy["path_sketch_drift_threshold"] = math.log(2.0)

    expected = _expected_training(reference, policy)
    expected_profile = _expected_profile(
        reference,
        policy,
        expected["model"],
        expected["calibrator"],
    )
    stable = (
        reference[FEATURES]
        .sample(n=101, replace=True, random_state=817)
        .reset_index(drop=True)
    )
    stable_score = _psi_from_profile(
        _tree_disagreement(expected["model"], stable),
        expected_profile["disagreement_profile"],
        float(policy["psi_epsilon"]),
    )
    reference_disagreement = _tree_disagreement(
        expected["model"], reference[FEATURES]
    )
    extreme_scores: list[tuple[float, int]] = []
    for row_index in np.argsort(reference_disagreement)[-12:]:
        repeated = pd.DataFrame(
            np.repeat(
                reference.iloc[[int(row_index)]][FEATURES].to_numpy(dtype=float),
                89,
                axis=0,
            ),
            columns=FEATURES,
        )
        score = _psi_from_profile(
            _tree_disagreement(expected["model"], repeated),
            expected_profile["disagreement_profile"],
            float(policy["psi_epsilon"]),
        )
        extreme_scores.append((score, int(row_index)))
    extreme_score, extreme_index = max(extreme_scores)
    assert extreme_score > stable_score
    policy["disagreement_drift_psi_threshold"] = (
        stable_score + extreme_score
    ) / 2.0
    extreme = pd.DataFrame(
        np.repeat(
            reference.iloc[[extreme_index]][FEATURES].to_numpy(dtype=float),
            89,
            axis=0,
        ),
        columns=FEATURES,
    )
    stable.insert(0, "id", range(131001, 131001 + len(stable)))
    extreme.insert(0, "id", range(132001, 132001 + len(extreme)))

    artifacts = tmp_path / "tree-disagreement-bundle"
    with _temporary_config(policy):
        _run_train(DEFAULT_DATA, artifacts)
        _assert_bundle(DEFAULT_DATA, artifacts)
        observed = []
        for batch_id, frame in (
            ("disagreement-stable", stable),
            ("disagreement-extreme", extreme),
        ):
            _insert_batch(batch_id, frame, tmp_path)
            result = _run_drift(
                batch_id,
                api_url=django_server,
                artifacts=artifacts,
            )
            result.check_returncode()
            observed.append(
                _assert_evaluation(
                    batch_id,
                    result.stdout,
                    artifacts=artifacts,
                )
            )

    assert observed[0]["drifted_features"] == []
    assert observed[0]["prediction_drifted"] is False
    assert observed[0]["disagreement_drifted"] is False
    assert observed[0]["correlation_drifted"] is False
    assert observed[0]["leaf_drifted"] is False
    assert observed[0]["path_sketch_drifted"] is False
    assert observed[0]["drift_detected"] is False
    assert observed[1]["drifted_features"] == []
    assert observed[1]["prediction_drifted"] is False
    assert observed[1]["disagreement_drifted"] is True
    assert observed[1]["correlation_drifted"] is False
    assert observed[1]["leaf_drifted"] is False
    assert observed[1]["path_sketch_drifted"] is False
    assert observed[1]["drift_detected"] is True
    assert observed[0]["disagreement_psi"] < observed[1]["disagreement_psi"]


def test_joint_path_sketch_drift_couples_complete_leaf_signature_to_decision(
    django_server: str,
    tmp_path: Path,
) -> None:
    """Hashed complete leaf paths independently trigger drift and bind the id transcript."""
    reference = pd.read_parquet(DEFAULT_DATA)
    policy = copy.deepcopy(_config())
    policy["model_version"] = "joint-path-sketch-release"
    policy["drift_ks_threshold"] = 999.0
    policy["drift_psi_threshold"] = 999.0
    policy["drift_feature_quorum"] = 4
    policy["prediction_drift_psi_threshold"] = 999.0
    policy["disagreement_drift_psi_threshold"] = 999.0
    policy["correlation_drift_threshold"] = 2.0
    policy["leaf_drift_threshold"] = math.log(2.0)

    expected = _expected_training(reference, policy)
    expected_profile = _expected_profile(
        reference,
        policy,
        expected["model"],
        expected["calibrator"],
    )
    path_profile = expected_profile["path_sketch_profile"]
    stable = (
        reference[FEATURES]
        .sample(n=103, replace=True, random_state=911)
        .reset_index(drop=True)
    )
    stable_assignments = _path_sketch_assignments(
        expected["model"],
        stable,
        int(path_profile["bucket_count"]),
        str(path_profile["salt"]),
    )
    stable_score = _path_sketch_js_divergence(
        stable_assignments,
        path_profile,
        float(policy["path_sketch_epsilon"]),
    )
    reference_assignments = _path_sketch_assignments(
        expected["model"],
        reference[FEATURES],
        int(path_profile["bucket_count"]),
        str(path_profile["salt"]),
    )
    bucket_proportions = np.asarray(
        path_profile["bin_proportions"], dtype=float
    )
    candidate_indices = sorted(
        range(len(reference_assignments)),
        key=lambda index: (
            bucket_proportions[int(reference_assignments[index])],
            int(reference_assignments[index]),
            index,
        ),
    )[:24]
    extreme_scores: list[tuple[float, int]] = []
    for row_index in candidate_indices:
        assignments = np.repeat(reference_assignments[row_index], 97)
        score = _path_sketch_js_divergence(
            assignments,
            path_profile,
            float(policy["path_sketch_epsilon"]),
        )
        extreme_scores.append((score, row_index))
    extreme_score, extreme_index = max(extreme_scores)
    assert extreme_score > stable_score
    policy["path_sketch_drift_threshold"] = (
        stable_score + extreme_score
    ) / 2.0
    extreme = pd.DataFrame(
        np.repeat(
            reference.iloc[[extreme_index]][FEATURES].to_numpy(dtype=float),
            97,
            axis=0,
        ),
        columns=FEATURES,
    )
    stable.insert(0, "id", range(141001, 141001 + len(stable)))
    extreme.insert(0, "id", range(142001, 142001 + len(extreme)))

    artifacts = tmp_path / "joint-path-sketch-bundle"
    with _temporary_config(policy):
        _run_train(DEFAULT_DATA, artifacts)
        _assert_bundle(DEFAULT_DATA, artifacts)
        observed = []
        for batch_id, frame in (
            ("path-sketch-stable", stable),
            ("path-sketch-extreme", extreme),
        ):
            _insert_batch(batch_id, frame, tmp_path)
            result = _run_drift(
                batch_id,
                api_url=django_server,
                artifacts=artifacts,
            )
            result.check_returncode()
            observed.append(
                _assert_evaluation(
                    batch_id,
                    result.stdout,
                    artifacts=artifacts,
                )
            )

    assert observed[0]["drifted_features"] == []
    assert observed[0]["prediction_drifted"] is False
    assert observed[0]["disagreement_drifted"] is False
    assert observed[0]["correlation_drifted"] is False
    assert observed[0]["leaf_drifted"] is False
    assert observed[0]["path_sketch_drifted"] is False
    assert observed[0]["drift_detected"] is False
    assert observed[1]["drifted_features"] == []
    assert observed[1]["prediction_drifted"] is False
    assert observed[1]["disagreement_drifted"] is False
    assert observed[1]["correlation_drifted"] is False
    assert observed[1]["leaf_drifted"] is False
    assert observed[1]["path_sketch_drifted"] is True
    assert observed[1]["drift_detected"] is True
    assert observed[0]["path_sketch_js"] < observed[1]["path_sketch_js"]
    assert observed[0]["path_sketch_digest"] != observed[1]["path_sketch_digest"]

def test_feature_quorum_couples_profile_statistics_to_final_decision(
    django_server: str,
    tmp_path: Path,
) -> None:
    """One drifted feature is insufficient while two trigger quorum when prediction drift is disabled."""
    reference = pd.read_parquet(DEFAULT_DATA)
    policy = copy.deepcopy(_config())
    policy["model_version"] = "feature-quorum-release"
    policy["prediction_drift_psi_threshold"] = 999.0
    policy["disagreement_drift_psi_threshold"] = 999.0
    policy["correlation_drift_threshold"] = 2.0
    policy["leaf_drift_threshold"] = math.log(2.0)
    policy["path_sketch_drift_threshold"] = math.log(2.0)
    artifacts = tmp_path / "feature-quorum-bundle"
    with _temporary_config(policy):
        _run_train(DEFAULT_DATA, artifacts)
        bundle = _assert_bundle(DEFAULT_DATA, artifacts)
        profile = bundle["profile"]
        one_feature = _find_stable_sample(
            reference, profile, policy, 137, 93001, artifacts
        )
        one_feature["feature_1"] += 9.0
        two_features = _find_stable_sample(
            reference, profile, policy, 139, 95001, artifacts
        )
        two_features["feature_1"] += 9.0
        two_features["feature_3"] -= 8.0
        cases = [
            ("quorum-one", one_feature, ["feature_1"], False),
            ("quorum-two", two_features, ["feature_1", "feature_3"], True),
        ]
        for batch_id, frame, expected_features, expected_drift in cases:
            _insert_batch(batch_id, frame, tmp_path)
            result = _run_drift(
                batch_id,
                api_url=django_server,
                artifacts=artifacts,
            )
            result.check_returncode()
            record = _assert_evaluation(
                batch_id,
                result.stdout,
                artifacts=artifacts,
            )
            assert record["prediction_drifted"] is False
            assert record["disagreement_drifted"] is False
            assert record["correlation_drifted"] is False
            assert record["leaf_drifted"] is False
            assert record["path_sketch_drifted"] is False
            assert record["drifted_features"] == expected_features
            assert record["drift_detected"] is expected_drift


def test_correlation_drift_couples_joint_structure_to_final_decision(
    django_server: str,
    tmp_path: Path,
) -> None:
    """A fresh batch with unchanged marginals triggers only pairwise dependence drift."""
    reference = pd.read_parquet(DEFAULT_DATA)
    policy = copy.deepcopy(_config())
    policy["model_version"] = "correlation-drift-release"
    policy["drift_ks_threshold"] = 999.0
    policy["drift_psi_threshold"] = 999.0
    policy["prediction_drift_psi_threshold"] = 999.0
    policy["disagreement_drift_psi_threshold"] = 999.0
    policy["correlation_drift_threshold"] = 0.30
    policy["leaf_drift_threshold"] = math.log(2.0)
    policy["path_sketch_drift_threshold"] = math.log(2.0)
    policy["drift_feature_quorum"] = 4
    artifacts = tmp_path / "correlation-drift-bundle"

    with _temporary_config(policy):
        _run_train(DEFAULT_DATA, artifacts)
        bundle = _assert_bundle(DEFAULT_DATA, artifacts)
        batch = reference[FEATURES].copy().reset_index(drop=True)
        for seed in range(330, 530):
            candidate = batch.copy()
            candidate["feature_1"] = (
                batch["feature_1"]
                .sample(frac=1.0, random_state=seed)
                .to_numpy(dtype=float)
            )
            deltas = _correlation_deltas(
                candidate,
                bundle["profile"]["correlation_profile"],
            )
            if max(deltas.values()) > policy["correlation_drift_threshold"]:
                batch = candidate
                break
        else:
            raise AssertionError("could not generate dependence-only drift")

        for feature in FEATURES:
            assert np.array_equal(
                np.sort(batch[feature].to_numpy(dtype=float)),
                np.sort(reference[feature].to_numpy(dtype=float)),
            )
        batch.insert(0, "id", range(151001, 151001 + len(batch)))
        _insert_batch("correlation-only", batch, tmp_path)
        result = _run_drift(
            "correlation-only",
            api_url=django_server,
            artifacts=artifacts,
        )
        result.check_returncode()
        record = _assert_evaluation(
            "correlation-only",
            result.stdout,
            artifacts=artifacts,
        )

    assert record["drifted_features"] == []
    assert all(
        stats["ks_statistic"] == pytest.approx(0.0, rel=0, abs=0)
        and stats["psi"] == pytest.approx(0.0, rel=0, abs=1e-15)
        for stats in record["feature_stats"].values()
    )
    assert record["prediction_drifted"] is False
    assert record["disagreement_drifted"] is False
    assert record["leaf_drifted"] is False
    assert record["path_sketch_drifted"] is False
    assert record["correlation_drifted"] is True
    assert record["correlation_drift_score"] > policy["correlation_drift_threshold"]
    assert record["drift_detected"] is True


def test_leaf_path_drift_triggers_without_marginal_or_prediction_drift(
    django_server: str,
    tmp_path: Path,
) -> None:
    """Per-tree leaf occupancy can independently trigger drift after pagination."""
    reference = pd.read_parquet(DEFAULT_DATA)
    policy = copy.deepcopy(_config())
    policy["model_version"] = "leaf-path-release"
    policy["drift_ks_threshold"] = 999.0
    policy["drift_psi_threshold"] = 999.0
    policy["prediction_drift_psi_threshold"] = 999.0
    policy["disagreement_drift_psi_threshold"] = 999.0
    policy["correlation_drift_threshold"] = 2.0
    policy["path_sketch_drift_threshold"] = math.log(2.0)
    policy["drift_feature_quorum"] = 4
    policy["inference_page_size"] = 13

    expected = _expected_training(reference, policy)
    expected_profile = _expected_profile(
        reference,
        policy,
        expected["model"],
        expected["calibrator"],
    )
    stable = (
        reference[FEATURES]
        .sample(n=109, replace=True, random_state=441)
        .reset_index(drop=True)
    )
    shifted_values, _ = make_classification(
        n_samples=109,
        n_features=4,
        n_informative=4,
        n_redundant=0,
        class_sep=0.65,
        shift=5.5,
        random_state=442,
    )
    shifted = pd.DataFrame(shifted_values, columns=FEATURES)
    stable_leaf_values = _leaf_js_divergences(
        expected["model"],
        stable,
        expected_profile["leaf_profile"],
        float(policy["leaf_js_epsilon"]),
    )
    shifted_leaf_values = _leaf_js_divergences(
        expected["model"],
        shifted,
        expected_profile["leaf_profile"],
        float(policy["leaf_js_epsilon"]),
    )
    stable_score = float(
        np.quantile(
            stable_leaf_values,
            float(policy["leaf_drift_quantile"]),
            method="linear",
        )
    )
    shifted_score = float(
        np.quantile(
            shifted_leaf_values,
            float(policy["leaf_drift_quantile"]),
            method="linear",
        )
    )
    assert shifted_score > stable_score
    policy["leaf_drift_threshold"] = (stable_score + shifted_score) / 2.0
    stable.insert(0, "id", range(161001, 161001 + len(stable)))
    shifted.insert(0, "id", range(162001, 162001 + len(shifted)))

    artifacts = tmp_path / "leaf-path-bundle"
    with _temporary_config(policy):
        _run_train(DEFAULT_DATA, artifacts)
        _assert_bundle(DEFAULT_DATA, artifacts)
        observed = []
        for batch_id, frame in (
            ("leaf-stable", stable),
            ("leaf-shifted", shifted),
        ):
            _insert_batch(batch_id, frame, tmp_path)
            result = _run_drift(
                batch_id,
                api_url=django_server,
                artifacts=artifacts,
            )
            result.check_returncode()
            observed.append(
                _assert_evaluation(
                    batch_id,
                    result.stdout,
                    artifacts=artifacts,
                )
            )
    assert observed[0]["drifted_features"] == []
    assert observed[0]["prediction_drifted"] is False
    assert observed[0]["disagreement_drifted"] is False
    assert observed[0]["correlation_drifted"] is False
    assert observed[0]["leaf_drifted"] is False
    assert observed[0]["path_sketch_drifted"] is False
    assert observed[0]["drift_detected"] is False
    assert observed[1]["drifted_features"] == []
    assert observed[1]["prediction_drifted"] is False
    assert observed[1]["disagreement_drifted"] is False
    assert observed[1]["correlation_drifted"] is False
    assert observed[1]["leaf_drifted"] is True
    assert observed[1]["path_sketch_drifted"] is False
    assert observed[1]["drift_detected"] is True
    assert observed[0]["leaf_drift_score"] < observed[1]["leaf_drift_score"]


def test_strict_leaf_boundary_uses_greater_than(
    django_server: str,
    tmp_path: Path,
) -> None:
    """A leaf score equal to the policy threshold is not considered drift."""
    reference = pd.read_parquet(DEFAULT_DATA)
    policy = copy.deepcopy(_config())
    policy["model_version"] = "strict-leaf-boundary-release"
    policy["drift_ks_threshold"] = 999.0
    policy["drift_psi_threshold"] = 999.0
    policy["prediction_drift_psi_threshold"] = 999.0
    policy["disagreement_drift_psi_threshold"] = 999.0
    policy["correlation_drift_threshold"] = 2.0
    policy["path_sketch_drift_threshold"] = math.log(2.0)
    policy["drift_feature_quorum"] = 4
    expected = _expected_training(reference, policy)
    expected_profile = _expected_profile(
        reference,
        policy,
        expected["model"],
        expected["calibrator"],
    )
    batch = (
        reference[FEATURES]
        .sample(n=97, replace=True, random_state=716)
        .reset_index(drop=True)
    )
    divergences = _leaf_js_divergences(
        expected["model"],
        batch,
        expected_profile["leaf_profile"],
        float(policy["leaf_js_epsilon"]),
    )
    boundary = float(
        np.quantile(
            divergences,
            float(policy["leaf_drift_quantile"]),
            method="linear",
        )
    )
    policy["leaf_drift_threshold"] = boundary
    batch.insert(0, "id", range(171001, 171001 + len(batch)))
    artifacts = tmp_path / "strict-leaf-bundle"
    with _temporary_config(policy):
        _run_train(DEFAULT_DATA, artifacts)
        _assert_bundle(DEFAULT_DATA, artifacts)
        _insert_batch("strict-leaf-boundary", batch, tmp_path)
        result = _run_drift(
            "strict-leaf-boundary",
            api_url=django_server,
            artifacts=artifacts,
        )
        result.check_returncode()
        record = _assert_evaluation(
            "strict-leaf-boundary",
            result.stdout,
            artifacts=artifacts,
        )
    assert record["leaf_drift_score"] == pytest.approx(boundary, rel=1e-12, abs=1e-12)
    assert record["leaf_drifted"] is False
    assert record["drifted_features"] == []
    assert record["prediction_drifted"] is False
    assert record["correlation_drifted"] is False
    assert record["drift_detected"] is False



def test_strict_uncertainty_and_path_boundaries_use_greater_than(
    django_server: str,
    tmp_path: Path,
) -> None:
    """Disagreement PSI and joint-path JS equal to policy thresholds remain non-drifted."""
    reference = pd.read_parquet(DEFAULT_DATA)
    policy = copy.deepcopy(_config())
    policy["model_version"] = "strict-uncertainty-path-boundary-release"
    policy["drift_ks_threshold"] = 999.0
    policy["drift_psi_threshold"] = 999.0
    policy["drift_feature_quorum"] = 4
    policy["prediction_drift_psi_threshold"] = 999.0
    policy["correlation_drift_threshold"] = 2.0
    policy["leaf_drift_threshold"] = math.log(2.0)

    expected = _expected_training(reference, policy)
    expected_profile = _expected_profile(
        reference,
        policy,
        expected["model"],
        expected["calibrator"],
    )
    batch = (
        reference[FEATURES]
        .sample(n=113, replace=True, random_state=1007)
        .reset_index(drop=True)
    )
    disagreement_boundary = _psi_from_profile(
        _tree_disagreement(expected["model"], batch),
        expected_profile["disagreement_profile"],
        float(policy["psi_epsilon"]),
    )
    path_profile = expected_profile["path_sketch_profile"]
    path_boundary = _path_sketch_js_divergence(
        _path_sketch_assignments(
            expected["model"],
            batch,
            int(path_profile["bucket_count"]),
            str(path_profile["salt"]),
        ),
        path_profile,
        float(policy["path_sketch_epsilon"]),
    )
    assert disagreement_boundary > 0
    assert path_boundary > 0
    policy["disagreement_drift_psi_threshold"] = disagreement_boundary
    policy["path_sketch_drift_threshold"] = path_boundary
    batch.insert(0, "id", range(176001, 176001 + len(batch)))

    artifacts = tmp_path / "strict-uncertainty-path-bundle"
    with _temporary_config(policy):
        _run_train(DEFAULT_DATA, artifacts)
        _assert_bundle(DEFAULT_DATA, artifacts)
        _insert_batch("strict-uncertainty-path", batch, tmp_path)
        result = _run_drift(
            "strict-uncertainty-path",
            api_url=django_server,
            artifacts=artifacts,
        )
        result.check_returncode()
        record = _assert_evaluation(
            "strict-uncertainty-path",
            result.stdout,
            artifacts=artifacts,
        )

    assert record["drifted_features"] == []
    assert record["prediction_drifted"] is False
    assert record["disagreement_psi"] == pytest.approx(
        disagreement_boundary, rel=0, abs=1e-12
    )
    assert record["disagreement_drifted"] is False
    assert record["correlation_drifted"] is False
    assert record["leaf_drifted"] is False
    assert record["path_sketch_js"] == pytest.approx(
        path_boundary, rel=0, abs=1e-12
    )
    assert record["path_sketch_drifted"] is False
    assert record["drift_detected"] is False

def test_strict_drift_boundary_uses_greater_than(
    django_server: str,
    tmp_path: Path,
) -> None:
    """A policy threshold equal to the maximum observed KS statistic does not mark drift."""
    reference = pd.read_parquet(DEFAULT_DATA)
    batch = (
        reference[FEATURES]
        .sample(n=67, replace=True, random_state=818)
        .reset_index(drop=True)
    )
    batch.insert(0, "id", range(111001, 111001 + len(batch)))
    maximum_ks = max(
        float(ks_2samp(reference[feature], batch[feature]).statistic)
        for feature in FEATURES
    )
    policy = copy.deepcopy(_config())
    policy["model_version"] = "strict-boundary-release"
    policy["drift_ks_threshold"] = maximum_ks
    policy["drift_psi_threshold"] = 999.0
    policy["prediction_drift_psi_threshold"] = 999.0
    policy["disagreement_drift_psi_threshold"] = 999.0
    policy["correlation_drift_threshold"] = 2.0
    policy["leaf_drift_threshold"] = math.log(2.0)
    policy["path_sketch_drift_threshold"] = math.log(2.0)
    policy["drift_feature_quorum"] = 1
    artifacts = tmp_path / "strict-bundle"
    with _temporary_config(policy):
        _run_train(DEFAULT_DATA, artifacts)
        _assert_bundle(DEFAULT_DATA, artifacts)
        _insert_batch("strict-boundary", batch, tmp_path)
        result = _run_drift(
            "strict-boundary",
            api_url=django_server,
            artifacts=artifacts,
        )
        result.check_returncode()
        record = _assert_evaluation(
            "strict-boundary",
            result.stdout,
            artifacts=artifacts,
        )
        assert any(
            stats["ks_statistic"] == pytest.approx(maximum_ks)
            for stats in record["feature_stats"].values()
        )
        assert record["drifted_features"] == []
        assert record["correlation_drifted"] is False
        assert record["drift_detected"] is False


class _BadPageDigestHandler(BaseHTTPRequestHandler):
    gets_seen = 0
    posts_seen = 0

    def do_GET(self) -> None:
        type(self).gets_seen += 1
        batch_id = self.path.split("/inference-batches/", 1)[1].split("/", 1)[0]
        payload = {
            "batch_id": batch_id,
            "cursor": None,
            "records": [
                {
                    "id": 181001,
                    "features": {feature: 0.0 for feature in FEATURES},
                }
            ],
            "next_cursor": None,
            "page_sha256": "sha256:" + "0" * 64,
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        type(self).posts_seen += 1
        self.send_response(500)
        self.end_headers()

    def log_message(self, format_string: str, *args: object) -> None:
        return


def test_page_digest_tamper_blocks_submission(
    trained_default_bundle: Path,
) -> None:
    """A malformed cursor-page digest is rejected without a drift POST."""
    _BadPageDigestHandler.gets_seen = 0
    _BadPageDigestHandler.posts_seen = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _BadPageDigestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        api_url = f"http://127.0.0.1:{server.server_port}/api/v1"
        result = _run_drift("bad-page-digest", api_url=api_url)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    assert result.returncode != 0
    assert _BadPageDigestHandler.gets_seen == 1
    assert _BadPageDigestHandler.posts_seen == 0


class _CountingHandler(BaseHTTPRequestHandler):
    requests_seen = 0

    def do_GET(self) -> None:
        type(self).requests_seen += 1
        self.send_response(500)
        self.end_headers()

    def do_POST(self) -> None:
        type(self).requests_seen += 1
        self.send_response(500)
        self.end_headers()

    def log_message(self, format_string: str, *args: object) -> None:
        return


def _run_with_counting_server(
    callback: Callable[[str], subprocess.CompletedProcess[str]],
) -> tuple[subprocess.CompletedProcess[str], int]:
    _CountingHandler.requests_seen = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CountingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        api_url = f"http://127.0.0.1:{server.server_port}/api/v1"
        result = callback(api_url)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    return result, _CountingHandler.requests_seen


def _rewrite_manifest_release(manifest_path: Path, manifest: dict[str, Any]) -> None:
    release_binding = {
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
    manifest["release_sha256"] = _digest_bytes(_canonical_bytes(release_binding))
    manifest_path.write_bytes(_canonical_bytes(manifest) + b"\n")


def test_artifact_tamper_blocks_all_http_before_inference(
    trained_default_bundle: Path,
    tmp_path: Path,
) -> None:
    """A changed artifact fails with its full path before any product API request."""
    bundle = tmp_path / "tampered-artifact-bundle"
    shutil.copytree(trained_default_bundle, bundle)
    metrics_path = bundle / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["oof_f1"] = float(metrics["oof_f1"]) / 2
    metrics_path.write_text(json.dumps(metrics) + "\n", encoding="utf-8")
    result, count = _run_with_counting_server(
        lambda api_url: _run_drift(
            "never-fetched",
            api_url=api_url,
            artifacts=bundle,
        )
    )
    assert result.returncode != 0
    assert str(metrics_path) in result.stderr
    assert count == 0


def test_calibrator_semantic_tamper_rejected_with_rebound_hashes(
    trained_default_bundle: Path,
    tmp_path: Path,
) -> None:
    """A hash-consistent calibrator with changed coefficients fails before any HTTP request."""
    bundle = tmp_path / "semantic-calibrator-bundle"
    shutil.copytree(trained_default_bundle, bundle)
    calibrator_path = bundle / "calibrator.joblib"
    manifest_path = bundle / "artifact_manifest.json"
    calibrator = joblib.load(calibrator_path)
    calibrator.coef_ = calibrator.coef_.copy()
    calibrator.coef_[0, 0] = float(calibrator.coef_[0, 0]) + 0.125
    joblib.dump(calibrator, calibrator_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_sha256"]["calibrator.joblib"] = _sha256(calibrator_path)
    _rewrite_manifest_release(manifest_path, manifest)
    result, count = _run_with_counting_server(
        lambda api_url: _run_drift(
            "never-fetched",
            api_url=api_url,
            artifacts=bundle,
        )
    )
    assert result.returncode != 0
    assert str(calibrator_path) in result.stderr
    assert count == 0


def test_metrics_semantic_tamper_rejected_with_rebound_hashes(
    trained_default_bundle: Path,
    tmp_path: Path,
) -> None:
    """Hash-consistent candidate metrics are independently re-derived before HTTP."""
    bundle = tmp_path / "semantic-metrics-bundle"
    shutil.copytree(trained_default_bundle, bundle)
    metrics_path = bundle / "metrics.json"
    manifest_path = bundle / "artifact_manifest.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["candidate_scores"][0]["raw_brier"] = (
        float(metrics["candidate_scores"][0]["raw_brier"]) + 0.03125
    )
    metrics_path.write_bytes(_canonical_bytes(metrics) + b"\n")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_sha256"]["metrics.json"] = _sha256(metrics_path)
    _rewrite_manifest_release(manifest_path, manifest)
    result, count = _run_with_counting_server(
        lambda api_url: _run_drift(
            "never-fetched",
            api_url=api_url,
            artifacts=bundle,
        )
    )
    assert result.returncode != 0
    assert str(metrics_path) in result.stderr
    assert count == 0


def test_config_tamper_blocks_all_http_before_inference(
    trained_default_bundle: Path,
) -> None:
    """A policy byte change is detected by full path before any product API request."""
    original = CONFIG_PATH.read_bytes()
    config = _config()
    config["drift_ks_threshold"] = float(config["drift_ks_threshold"]) + 0.01
    CONFIG_PATH.write_text(json.dumps(config) + "\n", encoding="utf-8")
    try:
        result, count = _run_with_counting_server(
            lambda api_url: _run_drift("never-fetched", api_url=api_url)
        )
    finally:
        CONFIG_PATH.write_bytes(original)
    assert result.returncode != 0
    assert str(CONFIG_PATH) in result.stderr
    assert count == 0


def test_profile_semantic_tamper_rejected_even_with_rebound_hashes(
    trained_default_bundle: Path,
    tmp_path: Path,
) -> None:
    """A rebound prediction profile inconsistent with model calibration still fails before HTTP."""
    bundle = tmp_path / "semantic-tamper-bundle"
    shutil.copytree(trained_default_bundle, bundle)
    profile_path = bundle / "drift_profile.json"
    manifest_path = bundle / "artifact_manifest.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    prediction_profile = profile["prediction_profile"]
    prediction_profile["mean"] = float(prediction_profile["mean"]) + 0.125
    profile_path.write_bytes(_canonical_bytes(profile) + b"\n")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_sha256"]["drift_profile.json"] = _sha256(profile_path)
    _rewrite_manifest_release(manifest_path, manifest)
    result, count = _run_with_counting_server(
        lambda api_url: _run_drift(
            "never-fetched",
            api_url=api_url,
            artifacts=bundle,
        )
    )
    assert result.returncode != 0
    assert str(profile_path) in result.stderr
    assert count == 0


def test_correlation_profile_semantic_tamper_rejected_with_rebound_hashes(
    trained_default_bundle: Path,
    tmp_path: Path,
) -> None:
    """A rebound pairwise dependence profile inconsistent with training rows fails before HTTP."""
    bundle = tmp_path / "semantic-correlation-profile-bundle"
    shutil.copytree(trained_default_bundle, bundle)
    profile_path = bundle / "drift_profile.json"
    manifest_path = bundle / "artifact_manifest.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    pair = profile["correlation_profile"]["pairs"][0]
    coefficient = float(pair["coefficient"])
    pair["coefficient"] = coefficient - 0.125 if coefficient > 0.75 else coefficient + 0.125
    profile_path.write_bytes(_canonical_bytes(profile) + b"\n")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_sha256"]["drift_profile.json"] = _sha256(profile_path)
    _rewrite_manifest_release(manifest_path, manifest)
    result, count = _run_with_counting_server(
        lambda api_url: _run_drift(
            "never-fetched",
            api_url=api_url,
            artifacts=bundle,
        )
    )
    assert result.returncode != 0
    assert str(profile_path) in result.stderr
    assert count == 0


def test_leaf_profile_semantic_tamper_rejected_with_rebound_hashes(
    trained_default_bundle: Path,
    tmp_path: Path,
) -> None:
    """A rebound tree occupancy profile inconsistent with the forest fails before HTTP."""
    bundle = tmp_path / "semantic-leaf-profile-bundle"
    shutil.copytree(trained_default_bundle, bundle)
    profile_path = bundle / "drift_profile.json"
    manifest_path = bundle / "artifact_manifest.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    proportions = profile["leaf_profile"]["trees"][0]["bin_proportions"]
    assert len(proportions) >= 2
    delta = min(0.01, float(proportions[1]) / 2.0)
    proportions[0] = float(proportions[0]) + delta
    proportions[1] = float(proportions[1]) - delta
    profile_path.write_bytes(_canonical_bytes(profile) + b"\n")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_sha256"]["drift_profile.json"] = _sha256(profile_path)
    _rewrite_manifest_release(manifest_path, manifest)
    result, count = _run_with_counting_server(
        lambda api_url: _run_drift(
            "never-fetched",
            api_url=api_url,
            artifacts=bundle,
        )
    )
    assert result.returncode != 0
    assert str(profile_path) in result.stderr
    assert count == 0



def test_disagreement_profile_semantic_tamper_rejected_with_rebound_hashes(
    trained_default_bundle: Path,
    tmp_path: Path,
) -> None:
    """A rebound tree-disagreement distribution inconsistent with the forest fails before HTTP."""
    bundle = tmp_path / "semantic-disagreement-profile-bundle"
    shutil.copytree(trained_default_bundle, bundle)
    profile_path = bundle / "drift_profile.json"
    manifest_path = bundle / "artifact_manifest.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    disagreement = profile["disagreement_profile"]
    disagreement["mean"] = float(disagreement["mean"]) + 0.03125
    profile_path.write_bytes(_canonical_bytes(profile) + b"\n")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_sha256"]["drift_profile.json"] = _sha256(profile_path)
    _rewrite_manifest_release(manifest_path, manifest)
    result, count = _run_with_counting_server(
        lambda api_url: _run_drift(
            "never-fetched",
            api_url=api_url,
            artifacts=bundle,
        )
    )
    assert result.returncode != 0
    assert str(profile_path) in result.stderr
    assert count == 0


def test_path_sketch_profile_semantic_tamper_rejected_with_rebound_hashes(
    trained_default_bundle: Path,
    tmp_path: Path,
) -> None:
    """A rebound joint-path bucket profile inconsistent with complete leaf vectors fails before HTTP."""
    bundle = tmp_path / "semantic-path-sketch-profile-bundle"
    shutil.copytree(trained_default_bundle, bundle)
    profile_path = bundle / "drift_profile.json"
    manifest_path = bundle / "artifact_manifest.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    proportions = profile["path_sketch_profile"]["bin_proportions"]
    source = next(index for index, value in enumerate(proportions) if float(value) > 0.02)
    target = (source + 1) % len(proportions)
    delta = min(0.01, float(proportions[source]) / 2.0)
    proportions[source] = float(proportions[source]) - delta
    proportions[target] = float(proportions[target]) + delta
    profile_path.write_bytes(_canonical_bytes(profile) + b"\n")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_sha256"]["drift_profile.json"] = _sha256(profile_path)
    _rewrite_manifest_release(manifest_path, manifest)
    result, count = _run_with_counting_server(
        lambda api_url: _run_drift(
            "never-fetched",
            api_url=api_url,
            artifacts=bundle,
        )
    )
    assert result.returncode != 0
    assert str(profile_path) in result.stderr
    assert count == 0

def test_training_parquet_tamper_blocks_all_http(
    trained_default_bundle: Path,
    tmp_path: Path,
) -> None:
    """A changed training reference fails with the supplied full path before any API request."""
    frame = pd.read_parquet(DEFAULT_DATA)
    frame.loc[0, "feature_0"] = float(frame.loc[0, "feature_0"]) + 0.125
    tampered = tmp_path / "tampered-training.parquet"
    frame.to_parquet(tampered, index=False)
    result, count = _run_with_counting_server(
        lambda api_url: _run_drift(
            "never-fetched",
            api_url=api_url,
            data=tampered,
        )
    )
    assert result.returncode != 0
    assert str(tampered) in result.stderr
    assert count == 0
