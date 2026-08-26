"""Verifier for the calibrated purchase-intent task.

Grades the agent's held-out probabilities against a reference model refit on the
active data file, globally and within each engagement band (low ProductRelated
<= 7, med 8..20, high >= 21), on discrimination (ROC-AUC, PR-AUC), Brier score,
and calibration-in-the-large (per band and overall). Held-out labels live in
/tests/labels.csv, never in the agent-visible data.
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

OUT = Path(os.environ.get("AGENT_OUTPUT_DIR", "/app/environment/outputs"))
DATA = Path(os.environ.get("RAW_DATA_DIR", "/app/environment/data"))
LABELS = Path(os.environ.get("LABELS_PATH", "/tests/labels.csv"))
SRC = Path(os.environ.get("AGENT_SOURCE", "/app/environment/analysis.R"))

DATAFILE = "online_shoppers.csv"
NUMS = [
    "Administrative",
    "Administrative_Duration",
    "Informational",
    "Informational_Duration",
    "ProductRelated",
    "ProductRelated_Duration",
    "BounceRates",
    "ExitRates",
    "PageValues",
    "SpecialDay",
]
CATS = [
    "OperatingSystems",
    "Browser",
    "Region",
    "TrafficType",
    "VisitorType",
    "Weekend",
]
BAND_NAMES = ["low", "med", "high"]
# Global discrimination bar. The reference is a gradient-boosted model; a plain
# base-R glm tops out ~0.02 ROC-AUC below it, so this tolerance requires the agent
# to match the boosted reference's ranking (a from-scratch boosted/ensemble model
# in base R), not just fit a logistic regression.
AUC_TOL = 0.015
PR_TOL = 0.060
BRIER_MULT = 1.00
BAND_AUC_TOL = 0.060
# Band calibration-in-the-large tolerance. The only labeled window on the target
# regime is the 600-row pilot; a band there holds ~130-320 labeled rows, so the
# band purchase rate carries roughly 0.03-0.04 of sampling noise as an estimate of
# the held-out band rate, and the deterministically subsampled variant widens that
# gap to ~0.07 in the med band. The tolerance must clear that irreducible
# proxy-vs-held-out gap so a sound shift-adapted fit passes on every variant, while
# staying well under the >=0.10 low/high-band miss that a mis-adapted fit incurs.
CAL_TOL = 0.09
# Overall (global) calibration-in-the-large tolerance: the mean prediction over
# all unscored rows must track the overall held-out purchase rate. Looser than a
# single band because it aggregates the whole test set.
GLOBAL_CAL_TOL = 0.04


def _bands(pr):
    p = np.asarray(pr, dtype=float)
    return np.where(p >= 21, "high", np.where(p >= 8, "med", "low"))


@pytest.fixture(scope="module")
def labels():
    d = pd.read_csv(LABELS)
    return dict(zip(d["row_id"].astype(int), d["target"].astype(int)))


@pytest.fixture(scope="module")
def preds():
    return pd.read_csv(OUT / "predictions.csv")


@pytest.fixture(scope="module")
def metrics():
    return json.loads((OUT / "metrics.json").read_text())


@pytest.fixture(scope="module")
def oracle(labels):
    df = pd.read_csv(DATA / DATAFILE)
    assert "row_id" in df.columns, "row_id column missing from data file"
    lab = df["target"].notna()
    train = df.loc[lab].reset_index(drop=True)
    test = df.loc[~lab].reset_index(drop=True)
    ytr = train["target"].astype(int).to_numpy()
    y_true = np.array([labels[int(r)] for r in test["row_id"]])
    cols = [(c, False) for c in NUMS] + [(c, True) for c in CATS]
    Xtr = np.empty((len(train), len(cols)))
    Xte = np.empty((len(test), len(cols)))
    mask = []
    for j, (c, is_cat) in enumerate(cols):
        if is_cat:
            levels = sorted(df[c].astype(str).unique())
            m = {v: i for i, v in enumerate(levels)}
            Xtr[:, j] = train[c].astype(str).map(m).to_numpy()
            Xte[:, j] = test[c].astype(str).map(m).to_numpy()
        else:
            Xtr[:, j] = train[c].astype(float).to_numpy()
            Xte[:, j] = test[c].astype(float).to_numpy()
        mask.append(is_cat)
    fm = HistGradientBoostingClassifier(
        random_state=42,
        max_iter=300,
        learning_rate=0.08,
        categorical_features=mask,
    ).fit(Xtr, ytr)
    pte = fm.predict_proba(Xte)[:, 1]
    band = _bands(test["ProductRelated"])
    per_band = {}
    for g in BAND_NAMES:
        m = band == g
        per_band[g] = {
            "auc": roc_auc_score(y_true[m], pte[m]),
            "brier": brier_score_loss(y_true[m], pte[m]),
            "base_rate": float(y_true[m].mean()),
            "n": int(m.sum()),
        }
    n_pilot = int((train["domain"].astype(str) == "target").sum())
    return {
        "n_train": int(lab.sum()),
        "n_pilot": n_pilot,
        "n_test": int((~lab).sum()),
        "test_ids": set(int(r) for r in test["row_id"]),
        "auc": roc_auc_score(y_true, pte),
        "ap": average_precision_score(y_true, pte),
        "brier": brier_score_loss(y_true, pte),
        "per_band": per_band,
        "bands": dict(zip(test["row_id"].astype(int), band)),
    }


@pytest.fixture(scope="module")
def merged(preds, labels, oracle):
    m = preds.copy()
    m["row_id"] = m["row_id"].astype(int)
    m["target"] = m["row_id"].map(labels)
    m["band"] = m["row_id"].map(oracle["bands"])
    return m.dropna(subset=["target"])


class TestArtifacts:
    def test_predictions_exist(self):
        assert (OUT / "predictions.csv").is_file()

    def test_metrics_schema(self, metrics):
        expected = {
            "n_train",
            "n_pilot",
            "n_test",
            "n_test_low",
            "n_test_med",
            "n_test_high",
            "roc_auc_val",
            "pr_auc_val",
            "brier_val",
            "n_bands",
        }
        assert set(metrics) == expected
        for k, v in metrics.items():
            assert isinstance(v, str), f"metrics value {k} must be a quoted string"

    def test_validation_metrics_plausible(self, metrics):
        for key in ["roc_auc_val", "pr_auc_val", "brier_val"]:
            value = float(metrics[key])
            assert np.isfinite(value), f"{key} must be finite"
            assert 0.0 <= value <= 1.0, f"{key} must be in [0, 1]"

    def test_n_bands(self, metrics):
        assert int(metrics["n_bands"]) == len(BAND_NAMES)


class TestCoverage:
    def test_covers_every_test_row(self, preds, oracle):
        got = set(preds["row_id"].astype(int))
        assert got == oracle["test_ids"], (
            "predictions must cover exactly the unscored rows"
        )

    def test_schema_sorted_unique(self, preds):
        assert list(preds.columns) == ["row_id", "pred_proba"], (
            "predictions.csv must have exactly the columns row_id,pred_proba "
            "(no extra or renamed columns)"
        )
        ids = preds["row_id"].astype(int).tolist()
        assert ids == sorted(ids), "predictions not sorted by row_id"
        assert len(ids) == len(set(ids)), "duplicate row_id"

    def test_proba_in_unit_interval(self, preds):
        p = preds["pred_proba"].to_numpy(dtype=float)
        assert np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all()

    def test_n_train_reported(self, metrics, oracle):
        assert int(metrics["n_train"]) == oracle["n_train"]

    def test_n_pilot_reported(self, metrics, oracle):
        assert int(metrics["n_pilot"]) == oracle["n_pilot"]

    def test_n_test_reported(self, metrics, oracle):
        assert int(metrics["n_test"]) == oracle["n_test"]

    def test_band_counts_reported(self, metrics, oracle):
        for key, band in [
            ("n_test_low", "low"),
            ("n_test_med", "med"),
            ("n_test_high", "high"),
        ]:
            assert int(metrics[key]) == oracle["per_band"][band]["n"], (
                f"{key} does not match the unscored count in the {band} band"
            )

    def test_band_counts_sum_to_n_test(self, metrics):
        parts = (
            int(metrics["n_test_low"])
            + int(metrics["n_test_med"])
            + int(metrics["n_test_high"])
        )
        assert parts == int(metrics["n_test"]), (
            "per-band unscored counts do not sum to n_test"
        )


class TestGlobalDiscrimination:
    def test_auc_near_reference(self, merged, oracle):
        auc = roc_auc_score(
            merged["target"].to_numpy(int), merged["pred_proba"].to_numpy(float)
        )
        assert auc >= oracle["auc"] - AUC_TOL, (
            f"held-out AUC {auc:.4f} below reference {oracle['auc']:.4f} - {AUC_TOL}"
        )

    def test_pr_auc_near_reference(self, merged, oracle):
        ap = average_precision_score(
            merged["target"].to_numpy(int), merged["pred_proba"].to_numpy(float)
        )
        assert ap >= oracle["ap"] - PR_TOL, (
            f"held-out PR-AUC {ap:.4f} below reference {oracle['ap']:.4f} - {PR_TOL}"
        )

    def test_brier_not_worse_than_reference(self, merged, oracle):
        brier = brier_score_loss(
            merged["target"].to_numpy(int), merged["pred_proba"].to_numpy(float)
        )
        assert brier <= oracle["brier"] * BRIER_MULT, (
            f"held-out Brier {brier:.5f} worse than reference {oracle['brier']:.5f}"
        )

    def test_global_calibration_in_the_large(self, merged):
        gap = abs(float(merged["pred_proba"].mean()) - float(merged["target"].mean()))
        assert gap <= GLOBAL_CAL_TOL, (
            f"overall mean prediction is {gap:.4f} away from the overall held-out "
            "purchase rate; predictions are not globally calibrated to the target "
            "regime"
        )


class TestBandCalibration:
    @pytest.mark.parametrize("band", BAND_NAMES)
    def test_band_auc_floor(self, merged, oracle, band):
        group = merged[merged["band"] == band]
        ref = oracle["per_band"][band]
        auc = roc_auc_score(
            group["target"].to_numpy(int), group["pred_proba"].to_numpy(float)
        )
        assert auc >= ref["auc"] - BAND_AUC_TOL, (
            f"{band}-band AUC {auc:.4f} below reference "
            f"{ref['auc']:.4f} - {BAND_AUC_TOL}; the ranking does not hold up "
            "within this engagement band"
        )

    @pytest.mark.parametrize("band", BAND_NAMES)
    def test_band_calibration_in_the_large(self, merged, oracle, band):
        group = merged[merged["band"] == band]
        ref = oracle["per_band"][band]
        gap = abs(float(group["pred_proba"].mean()) - ref["base_rate"])
        assert gap <= CAL_TOL, (
            f"{band}-band mean prediction is {gap:.4f} away from the band "
            f"held-out purchase rate {ref['base_rate']:.4f}; probabilities are "
            "not calibrated to the peak-season regime within this band"
        )
