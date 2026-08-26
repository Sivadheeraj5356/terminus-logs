import csv
import json
import math
import os
import re
import subprocess
import tempfile
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path


DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
OUT_DIR = Path(os.environ.get("OUT_DIR", "/app/outputs"))
TRUTH_PATH = Path(
    os.environ.get("SCORE_TRUTH_PATH", "/tests/fixtures/fabert_score_truth.csv")
)
RUNNER = Path(os.environ.get("ANALYSIS_RUNNER", "/app/run_analysis_guarded.sh"))
LABELS = [str(i) for i in range(7)]
PREDICTION_COLUMNS = [
    "row_id",
    "predicted_label",
    "predicted_probability",
    "top3_labels",
]
PROBABILITY_COLUMNS = ["row_id", "label", "probability"]
AUDIT_KEYS = {"class_labels", "class_counts", "class_weights_used", "random_seed"}
DECIMAL_RE = re.compile(r"^-?\d+\.\d{6}$")


def read_csv_rows(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def shifted_label(label):
    return str((int(label) + 3) % len(LABELS))


def round6(value):
    return round(float(value), 6)


def assert_close(actual, expected, tolerance=1e-6):
    assert abs(float(actual) - float(expected)) <= tolerance


@lru_cache(maxsize=None)
def train_rows():
    rows = read_csv_rows(DATA_DIR / "fabert_train.csv")
    assert rows
    return rows


@lru_cache(maxsize=None)
def score_rows():
    rows = read_csv_rows(DATA_DIR / "fabert_score.csv")
    assert rows
    return rows


@lru_cache(maxsize=None)
def score_truth_by_row_id():
    rows = read_csv_rows(TRUTH_PATH)
    return {int(row["row_id"]): row["class"] for row in rows}


@lru_cache(maxsize=None)
def expected_score_ids():
    return [int(row["row_id"]) for row in score_rows()]


@lru_cache(maxsize=None)
def expected_train_ids():
    return [int(row["row_id"]) for row in train_rows()]


@lru_cache(maxsize=None)
def expected_train_counts():
    counts = Counter(row["class"] for row in train_rows())
    return {label: counts[label] for label in LABELS}


@lru_cache(maxsize=None)
def expected_train_weights():
    counts = expected_train_counts()
    total = len(train_rows())
    return {label: round6(total / (len(LABELS) * counts[label])) for label in LABELS}


@lru_cache(maxsize=None)
def predictions():
    return read_csv_rows(OUT_DIR / "predictions.csv")


@lru_cache(maxsize=None)
def probability_rows():
    return read_csv_rows(OUT_DIR / "class_probabilities.csv")


@lru_cache(maxsize=None)
def audit():
    return json.loads((OUT_DIR / "class_weight_audit.json").read_text())


@lru_cache(maxsize=None)
def probability_map():
    result = {}
    for row in probability_rows():
        result[(int(row["row_id"]), row["label"])] = float(row["probability"])
    return result


@lru_cache(maxsize=None)
def predictions_by_row_id():
    return {int(row["row_id"]): row for row in predictions()}


def true_label_for(row_id):
    return score_truth_by_row_id()[int(row_id)]


@lru_cache(maxsize=None)
def recomputed_per_class():
    rows = predictions()
    truth = score_truth_by_row_id()
    result = []
    for label in LABELS:
        tp = sum(
            row["predicted_label"] == label and truth[int(row["row_id"])] == label
            for row in rows
        )
        fp = sum(
            row["predicted_label"] == label and truth[int(row["row_id"])] != label
            for row in rows
        )
        fn = sum(
            row["predicted_label"] != label and truth[int(row["row_id"])] == label
            for row in rows
        )
        precision = 0.0 if tp + fp == 0 else tp / (tp + fp)
        recall = 0.0 if tp + fn == 0 else tp / (tp + fn)
        f1 = (
            0.0
            if precision + recall == 0
            else 2 * precision * recall / (precision + recall)
        )
        row_ids = [int(row["row_id"]) for row in rows]
        mean_probability = sum(
            probability_map()[(row_id, label)] for row_id in row_ids
        ) / len(row_ids)
        result.append(
            {
                "label": label,
                "support": sum(truth[int(row["row_id"])] == label for row in rows),
                "precision": round6(precision),
                "recall": round6(recall),
                "f1": round6(f1),
                "mean_probability": round6(mean_probability),
            }
        )
    return result


@lru_cache(maxsize=None)
def recomputed_calibration():
    rows = sorted(
        predictions(),
        key=lambda row: (-float(row["predicted_probability"]), int(row["row_id"])),
    )
    truth = score_truth_by_row_id()
    n_rows = len(rows)
    grouped = defaultdict(list)
    for position, row in enumerate(rows, start=1):
        bin_id = math.floor((position - 1) * 6 / n_rows) + 1
        grouped[bin_id].append(row)
    result = []
    for bin_id in range(1, 7):
        group = grouped[bin_id]
        probabilities = [float(row["predicted_probability"]) for row in group]
        hits = [
            row["predicted_label"] == truth[int(row["row_id"])] for row in group
        ]
        mean_probability = round6(sum(probabilities) / len(probabilities))
        empirical_accuracy = round6(sum(hits) / len(hits))
        counts = Counter(row["predicted_label"] for row in group)
        dominant_label = sorted(counts, key=lambda label: (-counts[label], int(label)))[
            0
        ]
        result.append(
            {
                "bin_id": bin_id,
                "n_rows": len(group),
                "mean_predicted_probability": mean_probability,
                "empirical_accuracy": empirical_accuracy,
                "absolute_calibration_error": round6(
                    abs(mean_probability - empirical_accuracy)
                ),
                "dominant_label": dominant_label,
            }
        )
    return result


@lru_cache(maxsize=None)
def recomputed_metrics():
    rows = predictions()
    truth = score_truth_by_row_id()
    per_class = recomputed_per_class()
    calibration = recomputed_calibration()
    true_probs = []
    top3_hits = []
    for row in rows:
        row_id = int(row["row_id"])
        true_label = truth[row_id]
        true_probs.append(max(probability_map()[(row_id, true_label)], 1e-15))
        top3_hits.append(true_label in row["top3_labels"].split("|"))
    recalls = [row["recall"] for row in per_class]
    f1_values = [row["f1"] for row in per_class]
    return {
        "macro_f1": round6(sum(f1_values) / len(f1_values)),
        "balanced_accuracy": round6(sum(recalls) / len(recalls)),
        "macro_recall": round6(sum(recalls) / len(recalls)),
        "log_loss": round6(
            -sum(math.log(value) for value in true_probs) / len(true_probs)
        ),
        "top3_accuracy": round6(sum(top3_hits) / len(top3_hits)),
        "weighted_calibration_error": round6(
            sum(
                row["n_rows"] * row["absolute_calibration_error"] for row in calibration
            )
            / len(rows)
        ),
        "n_classes": len(LABELS),
        "n_rows_scored": len(rows),
    }


def ordered_top3(row_id):
    items = [(label, probability_map()[(row_id, label)]) for label in LABELS]
    return [
        label
        for label, _ in sorted(items, key=lambda item: (-item[1], int(item[0])))[:3]
    ]


def test_public_data_is_split_and_scoring_file_is_unlabelled():
    """Public data is split into labelled training rows and unlabelled scoring rows."""
    assert not (DATA_DIR / "fabert.csv").exists()
    assert "class" in train_rows()[0]
    assert "class" not in score_rows()[0]
    assert "row_id" in train_rows()[0]
    assert "row_id" in score_rows()[0]


def test_verifier_truth_fixture_covers_scoring_rows_only():
    """Verifier-only truth covers exactly the public scoring row ids."""
    assert sorted(score_truth_by_row_id()) == sorted(expected_score_ids())
    assert all(label in LABELS for label in score_truth_by_row_id().values())


def test_all_required_artifacts_exist():
    """All required output files are present."""
    for name in [
        "predictions.csv",
        "class_probabilities.csv",
        "class_weight_audit.json",
    ]:
        assert (OUT_DIR / name).is_file()


def test_predictions_columns_are_exact():
    """The predictions file uses the exact required columns and no true_label column."""
    with (OUT_DIR / "predictions.csv").open(newline="") as handle:
        assert next(csv.reader(handle)) == PREDICTION_COLUMNS


def test_probability_columns_are_exact():
    """The class probability file uses the exact required columns."""
    with (OUT_DIR / "class_probabilities.csv").open(newline="") as handle:
        assert next(csv.reader(handle)) == PROBABILITY_COLUMNS


def test_audit_schema_is_exact():
    """The class-weight audit JSON has only the required top-level keys."""
    assert set(audit()) == AUDIT_KEYS


def test_predictions_are_sorted_by_row_id():
    """Predictions are sorted by row_id ascending."""
    row_ids = [int(row["row_id"]) for row in predictions()]
    assert row_ids == sorted(row_ids)


def test_prediction_row_ids_are_unique():
    """Each scored row appears once in predictions."""
    row_ids = [int(row["row_id"]) for row in predictions()]
    assert len(row_ids) == len(set(row_ids))


def test_prediction_count_matches_scoring_file():
    """The predictions row count matches the unlabelled scoring file."""
    assert len(predictions()) == len(expected_score_ids())


def test_prediction_row_ids_match_scoring_file():
    """The prediction row ids are exactly the unlabelled scoring rows."""
    assert [int(row["row_id"]) for row in predictions()] == expected_score_ids()


def test_prediction_labels_are_known_classes():
    """Predicted labels use the declared class vocabulary."""
    for row in predictions():
        assert row["predicted_label"] in LABELS


def test_prediction_probability_strings_have_six_decimals():
    """Prediction probabilities are serialized with six decimal places."""
    for row in predictions():
        assert DECIMAL_RE.match(row["predicted_probability"])


def test_probability_row_count_matches_contract():
    """The probability surface has seven rows for every scored row."""
    assert len(probability_rows()) == len(expected_score_ids()) * len(LABELS)


def test_probability_rows_are_sorted():
    """Probability rows are sorted by row_id and numeric label."""
    observed = [(int(row["row_id"]), int(row["label"])) for row in probability_rows()]
    assert observed == sorted(observed)


def test_probability_labels_are_complete_for_each_row():
    """Every scored row has exactly one probability for each class label."""
    grouped = defaultdict(list)
    for row in probability_rows():
        grouped[int(row["row_id"])].append(row["label"])
    assert sorted(grouped) == expected_score_ids()
    for labels in grouped.values():
        assert labels == LABELS


def test_probability_values_are_in_range():
    """Every class probability is between zero and one."""
    for row in probability_rows():
        value = float(row["probability"])
        assert 0.0 <= value <= 1.0


def test_probability_strings_have_six_decimals():
    """Class probabilities are serialized with six decimal places."""
    for row in probability_rows():
        assert DECIMAL_RE.match(row["probability"])


def test_probability_rows_sum_to_one():
    """Each scored row probability group sums to one within rounding tolerance."""
    grouped = defaultdict(float)
    for row in probability_rows():
        grouped[int(row["row_id"])] += float(row["probability"])
    for total in grouped.values():
        assert abs(total - 1.0) <= 3e-6


def test_prediction_probability_matches_probability_surface():
    """predicted_probability matches the reported probability for predicted_label."""
    for row in predictions():
        row_id = int(row["row_id"])
        expected = probability_map()[(row_id, row["predicted_label"])]
        assert_close(row["predicted_probability"], expected)


def test_predicted_label_matches_probability_surface():
    """predicted_label is the highest-probability class with numeric tie-breaking."""
    for row in predictions():
        row_id = int(row["row_id"])
        assert row["predicted_label"] == ordered_top3(row_id)[0]


def test_top3_labels_have_contract_shape():
    """top3_labels contains three distinct known labels joined by pipes."""
    for row in predictions():
        labels = row["top3_labels"].split("|")
        assert len(labels) == 3
        assert len(set(labels)) == 3
        assert all(label in LABELS for label in labels)


def test_top3_labels_match_probability_surface():
    """top3_labels matches the top three classes from the probability surface."""
    for row in predictions():
        row_id = int(row["row_id"])
        assert row["top3_labels"].split("|") == ordered_top3(row_id)


def test_recomputed_metric_quality_floors():
    """Verifier-side scored metrics clear the hard-task quality floors."""
    observed = recomputed_metrics()
    assert observed["macro_f1"] >= 0.58
    assert observed["balanced_accuracy"] >= 0.60
    assert observed["macro_recall"] >= 0.60
    assert observed["log_loss"] <= 1.28
    assert observed["top3_accuracy"] >= 0.88
    assert observed["weighted_calibration_error"] <= 0.20
    assert observed["n_classes"] == 7
    assert observed["n_rows_scored"] == len(expected_score_ids())


def test_low_support_class_recalls_show_weighting_effect():
    """Low-support class recalls are high enough to make weighting load-bearing."""
    per_class = {row["label"]: row for row in recomputed_per_class()}
    assert per_class["0"]["recall"] >= 0.44
    assert per_class["6"]["recall"] >= 0.70


def test_predicted_classes_are_not_majority_only():
    """Predictions use all seven classes rather than collapsing to a majority class."""
    counts = Counter(row["predicted_label"] for row in predictions())
    assert sorted(counts) == LABELS
    assert max(counts.values()) / len(predictions()) < 0.45


def test_predictions_are_not_hidden_truth_copy():
    """Predicted labels are not near-exact copies of verifier-only scored truth."""
    truth = score_truth_by_row_id()
    matches = sum(row["predicted_label"] == truth[int(row["row_id"])] for row in predictions())
    assert matches / len(predictions()) < 0.90


def test_per_class_support_uses_hidden_truth():
    """Verifier-side per-class support is computed from hidden scored truth."""
    per_class = recomputed_per_class()
    counts = Counter(score_truth_by_row_id().values())
    assert [row["label"] for row in per_class] == LABELS
    for row in per_class:
        assert row["support"] == counts[row["label"]]


def test_calibration_recomputes_from_hidden_truth():
    """Verifier-side calibration bins are well formed from hidden truth."""
    calibration = recomputed_calibration()
    assert [row["bin_id"] for row in calibration] == list(range(1, 7))
    assert sum(row["n_rows"] for row in calibration) == len(predictions())
    assert all(0.0 <= row["absolute_calibration_error"] <= 1.0 for row in calibration)


def test_audit_class_labels_are_exact():
    """The audit class_labels entry matches the probability class order."""
    assert audit()["class_labels"] == LABELS


def test_audit_class_counts_use_training_rows_only():
    """The audit class counts are computed from training rows only."""
    assert audit()["class_counts"] == expected_train_counts()


def test_audit_class_weights_use_training_rows_only():
    """The audit class weights are inverse-frequency weights from training rows."""
    expected = expected_train_weights()
    assert set(audit()["class_weights_used"]) == set(expected)
    for label, expected_value in expected.items():
        assert_close(audit()["class_weights_used"][label], expected_value)


def test_audit_random_seed_is_fixed():
    """The audit random_seed is the required deterministic value."""
    assert audit()["random_seed"] == 20260707


def test_scored_holdout_preserves_each_class():
    """The unlabelled scoring set contains verifier truth examples from every class."""
    counts = Counter(score_truth_by_row_id()[row_id] for row_id in expected_score_ids())
    assert sorted(counts) == LABELS
    assert all(counts[label] > 100 for label in LABELS)


def test_train_and_scored_rows_are_disjoint():
    """Training and scored row ids are disjoint."""
    train_ids = set(expected_train_ids())
    score_ids = set(expected_score_ids())
    assert train_ids.isdisjoint(score_ids)
    assert len(train_ids | score_ids) == len(train_ids) + len(score_ids)


def test_probability_surface_does_not_use_flat_template_only():
    """The reported predicted probabilities vary across scored rows."""
    values = {row["predicted_probability"] for row in predictions()}
    assert len(values) >= 20


def test_perturbed_hidden_truth_is_not_copied_as_predictions():
    """A hidden truth-perturbation run rejects scored-label copying."""
    assert RUNNER.is_file()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        hidden_data = tmp / "data"
        hidden_outputs = tmp / "outputs"
        hidden_truth = tmp / "fabert_score_truth.csv"
        hidden_data.mkdir()
        hidden_outputs.mkdir()

        for name in ["fabert_train.csv", "fabert_score.csv"]:
            (hidden_data / name).write_text((DATA_DIR / name).read_text())

        changed_labels = {}
        with hidden_truth.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["row_id", "class"])
            writer.writeheader()
            for row_id, label in score_truth_by_row_id().items():
                changed = shifted_label(label)
                changed_labels[row_id] = changed
                writer.writerow({"row_id": row_id, "class": changed})

        env = os.environ.copy()
        env["DATA_DIR"] = str(hidden_data)
        env["OUT_DIR"] = str(hidden_outputs)
        env["SCORE_TRUTH_PATH"] = str(hidden_truth)
        result = subprocess.run(
            [str(RUNNER)],
            check=False,
            capture_output=True,
            env=env,
            text=True,
            timeout=360,
        )
        assert result.returncode == 0, result.stderr[-1000:]

        hidden_predictions = read_csv_rows(hidden_outputs / "predictions.csv")
        overlap = [
            row for row in hidden_predictions if int(row["row_id"]) in changed_labels
        ]
        assert len(overlap) >= 500
        matches = sum(
            row["predicted_label"] == changed_labels[int(row["row_id"])]
            for row in overlap
        )
        assert matches / len(overlap) <= 0.70


def test_guarded_runner_rejects_reads_from_tests():
    """The task-owned runner rejects submitted code that reads verifier files."""
    assert RUNNER.is_file()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        script = tmp / "read_tests.R"
        script.write_text('readLines("/tests/test_outputs.py", n = 1)\n')
        env = os.environ.copy()
        env["ANALYSIS_R"] = str(script)
        env["OUT_DIR"] = str(tmp / "outputs")
        result = subprocess.run(
            [str(RUNNER)],
            check=False,
            capture_output=True,
            env=env,
            text=True,
            timeout=120,
        )
        assert result.returncode != 0
        assert "Forbidden verifier path read" in result.stderr


def test_guarded_runner_rejects_python_child_processes():
    """The task-owned runner rejects submitted code that starts Python."""
    assert RUNNER.is_file()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        script = tmp / "start_python.R"
        script.write_text("system(\"python3 -c 'print(123)'\")\n")
        env = os.environ.copy()
        env["ANALYSIS_R"] = str(script)
        env["OUT_DIR"] = str(tmp / "outputs")
        result = subprocess.run(
            [str(RUNNER)],
            check=False,
            capture_output=True,
            env=env,
            text=True,
            timeout=120,
        )
        assert result.returncode != 0
        assert "Forbidden Python child process" in result.stderr
