import json
import math
import re
from pathlib import Path

import numpy as np
from rest_framework import serializers

from monitoring.models import DriftEvaluation, InferenceRecord

FEATURE_KEYS = ("feature_0", "feature_1", "feature_2", "feature_3")
CORRELATION_KEYS = tuple(
    f"{FEATURE_KEYS[left]}|{FEATURE_KEYS[right]}"
    for left in range(len(FEATURE_KEYS))
    for right in range(left + 1, len(FEATURE_KEYS))
)
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
CONFIG_PATH = Path("/app/config/repro_config.json")


def _policy() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _is_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


class InferenceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = InferenceRecord
        fields = ("id", "features")

    def validate_features(self, value: dict) -> dict:
        if not isinstance(value, dict) or set(value) != set(FEATURE_KEYS):
            raise serializers.ValidationError("features must contain exactly four keys")
        for key in FEATURE_KEYS:
            if not _is_number(value[key]):
                raise serializers.ValidationError(f"{key} must be finite numeric")
        return value


class DriftEvaluationSerializer(serializers.ModelSerializer):
    drifted_features = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
    )
    leaf_js_divergences = serializers.ListField(
        child=serializers.FloatField(),
        allow_empty=False,
    )
    correlation_deltas = serializers.DictField(
        child=serializers.FloatField(),
        allow_empty=False,
    )

    class Meta:
        model = DriftEvaluation
        fields = (
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
        )
        read_only_fields = ("id", "created_at")

    writable_fields = {
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
    }

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) != self.writable_fields:
            raise serializers.ValidationError(
                "drift evaluation fields must match schema"
            )
        return super().to_internal_value(data)

    def _validate_digest(self, value: str) -> str:
        if DIGEST_RE.fullmatch(value) is None:
            raise serializers.ValidationError("invalid sha256 digest")
        return value

    def validate_prediction_digest(self, value: str) -> str:
        return self._validate_digest(value)

    def validate_batch_source_digest(self, value: str) -> str:
        return self._validate_digest(value)

    def validate_path_sketch_digest(self, value: str) -> str:
        return self._validate_digest(value)

    def validate_correlation_deltas(self, value: dict) -> dict:
        if not isinstance(value, dict) or list(value) != list(CORRELATION_KEYS):
            raise serializers.ValidationError(
                "correlation_deltas must follow feature-pair order"
            )
        for key in CORRELATION_KEYS:
            if not _is_number(value[key]) or not 0 <= float(value[key]) <= 2:
                raise serializers.ValidationError(
                    f"{key} correlation delta must be finite in [0, 2]"
                )
        return value

    def validate_feature_stats(self, value: dict) -> dict:
        if not isinstance(value, dict) or list(value) != list(FEATURE_KEYS):
            raise serializers.ValidationError("feature_stats must follow feature order")
        for feature_name in FEATURE_KEYS:
            stats = value[feature_name]
            if not isinstance(stats, dict) or set(stats) != {
                "mean",
                "std",
                "ks_statistic",
                "psi",
                "drifted",
            }:
                raise serializers.ValidationError(
                    f"{feature_name} has an invalid statistics schema"
                )
            for stat_name in ("mean", "std", "ks_statistic", "psi"):
                if not _is_number(stats[stat_name]):
                    raise serializers.ValidationError(
                        f"{feature_name}.{stat_name} must be finite numeric"
                    )
            if not isinstance(stats["drifted"], bool):
                raise serializers.ValidationError(
                    f"{feature_name}.drifted must be boolean"
                )
            if stats["std"] < 0 or stats["psi"] < 0:
                raise serializers.ValidationError(
                    f"{feature_name} has a negative statistic"
                )
            if not 0 <= stats["ks_statistic"] <= 1:
                raise serializers.ValidationError(
                    f"{feature_name}.ks_statistic must be in [0, 1]"
                )
        return value

    def validate(self, attrs: dict) -> dict:
        count = attrs["prediction_count"]
        positives = attrs["positive_predictions"]
        if count <= 0 or positives < 0 or positives > count:
            raise serializers.ValidationError("invalid prediction counts")
        if attrs["source_page_count"] <= 0:
            raise serializers.ValidationError("source_page_count must be positive")
        for field in (
            "training_oof_f1",
            "training_calibrated_brier",
            "decision_threshold",
            "mean_raw_positive_probability",
            "mean_positive_probability",
        ):
            if not 0 <= attrs[field] <= 1:
                raise serializers.ValidationError(f"{field} must be in [0, 1]")
        for field in ("prediction_psi", "disagreement_psi"):
            if not _is_number(attrs[field]) or attrs[field] < 0:
                raise serializers.ValidationError(f"{field} must be non-negative")
        if (
            not _is_number(attrs["mean_tree_disagreement"])
            or not 0 <= attrs["mean_tree_disagreement"] <= 0.5 + 1e-12
        ):
            raise serializers.ValidationError(
                "mean_tree_disagreement must be finite in [0, 0.5]"
            )
        if (
            not _is_number(attrs["path_sketch_js"])
            or not 0 <= attrs["path_sketch_js"] <= math.log(2.0) + 1e-12
        ):
            raise serializers.ValidationError("path_sketch_js is invalid")
        if not _is_number(attrs["correlation_drift_score"]):
            raise serializers.ValidationError(
                "correlation_drift_score must be finite numeric"
            )
        expected_correlation_score = max(
            float(value) for value in attrs["correlation_deltas"].values()
        )
        if not math.isclose(
            float(attrs["correlation_drift_score"]),
            expected_correlation_score,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise serializers.ValidationError(
                "correlation_drift_score is inconsistent"
            )

        policy = _policy()
        champion = next(
            (item for item in policy["candidates"] if item["name"] == attrs["champion"]),
            None,
        )
        if champion is None:
            raise serializers.ValidationError("champion is not configured")
        leaf_values = attrs["leaf_js_divergences"]
        if len(leaf_values) != int(champion["n_estimators"]):
            raise serializers.ValidationError("leaf_js_divergences has wrong length")
        if any(
            not _is_number(value) or not 0 <= float(value) <= math.log(2.0) + 1e-12
            for value in leaf_values
        ):
            raise serializers.ValidationError("invalid leaf divergence")
        expected_leaf_score = float(
            np.quantile(
                np.asarray(leaf_values, dtype=float),
                float(policy["leaf_drift_quantile"]),
                method="linear",
            )
        )
        if not math.isclose(
            float(attrs["leaf_drift_score"]),
            expected_leaf_score,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise serializers.ValidationError("leaf_drift_score is inconsistent")

        expected_features = []
        for feature_name in FEATURE_KEYS:
            stats = attrs["feature_stats"][feature_name]
            expected = (
                stats["ks_statistic"] > policy["drift_ks_threshold"]
                or stats["psi"] > policy["drift_psi_threshold"]
            )
            if stats["drifted"] is not expected:
                raise serializers.ValidationError(
                    f"{feature_name}.drifted is inconsistent"
                )
            if expected:
                expected_features.append(feature_name)

        if attrs["drifted_features"] != expected_features:
            raise serializers.ValidationError("drifted_features is inconsistent")
        expected_prediction_drift = (
            attrs["prediction_psi"] > policy["prediction_drift_psi_threshold"]
        )
        if attrs["prediction_drifted"] is not expected_prediction_drift:
            raise serializers.ValidationError("prediction_drifted is inconsistent")
        expected_disagreement_drift = (
            attrs["disagreement_psi"]
            > policy["disagreement_drift_psi_threshold"]
        )
        if attrs["disagreement_drifted"] is not expected_disagreement_drift:
            raise serializers.ValidationError("disagreement_drifted is inconsistent")
        expected_correlation_drift = (
            attrs["correlation_drift_score"]
            > policy["correlation_drift_threshold"]
        )
        if attrs["correlation_drifted"] is not expected_correlation_drift:
            raise serializers.ValidationError("correlation_drifted is inconsistent")
        expected_leaf_drift = (
            attrs["leaf_drift_score"] > policy["leaf_drift_threshold"]
        )
        if attrs["leaf_drifted"] is not expected_leaf_drift:
            raise serializers.ValidationError("leaf_drifted is inconsistent")
        expected_path_drift = (
            attrs["path_sketch_js"] > policy["path_sketch_drift_threshold"]
        )
        if attrs["path_sketch_drifted"] is not expected_path_drift:
            raise serializers.ValidationError("path_sketch_drifted is inconsistent")
        expected_drift = (
            len(expected_features) >= policy["drift_feature_quorum"]
            or expected_prediction_drift
            or expected_disagreement_drift
            or expected_correlation_drift
            or expected_leaf_drift
            or expected_path_drift
        )
        if attrs["drift_detected"] is not expected_drift:
            raise serializers.ValidationError("drift_detected is inconsistent")
        return attrs
