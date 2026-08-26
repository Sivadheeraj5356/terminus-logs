"""Discriminating verifier for deployment-calibrated, education-fair subscription
scoring under case-control training.

The training rows are enriched (subscribers kept, non-subscribers down-sampled), so a
model left at the training rate reads far too high and is badly miscalibrated within
every education group. The protected attribute `education` may not be a model input.
Held-out scores are graded on ranking and, within every substantial education
subgroup, on calibration and Brier against a reference gradient-boosted model that is
blind to education, recovers the deployment subscription rate from the unlabelled
held-out contacts by black-box shift estimation, and reconciles onto it. A model that
skips the reconciliation fails the per-subgroup calibration floors; a model that
conditions on education fails the permutation-invariance stage. Held-out truth lives
in /tests/labels.csv, never in the agent-visible data.
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
BASELINE_OUTPUT_DIR = os.environ.get("BASELINE_OUTPUT_DIR")
STAGE_IS_PERMUTE = bool(BASELINE_OUTPUT_DIR)

DATAFILE = "bank_additional.csv"
SUBGROUP = "education"
NUMS = [
    "age",
    "campaign",
    "pdays",
    "previous",
    "emp.var.rate",
    "cons.price.idx",
    "cons.conf.idx",
    "euribor3m",
    "nr.employed",
]
# model categoricals deliberately EXCLUDE the protected attribute education
CATS = [
    "job",
    "marital",
    "default",
    "housing",
    "loan",
    "contact",
    "month",
    "day_of_week",
    "poutcome",
]
MIN_EVAL = 300
MIN_POS = 15

AUC_TOL = 0.025
PR_TOL = 0.045
BRIER_MULT = 1.10
SUB_AUC_TOL = 0.055
SUB_BRIER_MULT = 1.15
CAL_SLACK = 0.025
DISP_CAL_TOL = 0.030
DISP_AUC_TOL = 0.043
DISP_BRIER_TOL = 0.020

ref_skip = pytest.mark.skipif(
    STAGE_IS_PERMUTE,
    reason="reference-relative checks do not run on the education-permutation stage",
)


def _bbse_reconcile(p_cal, y_cal, p_test, pi_train):
    thr = 0.5
    yhat_cal = (p_cal >= thr).astype(int)
    C = np.zeros((2, 2))
    for j in (0, 1):
        sel = y_cal == j
        for i in (0, 1):
            C[i, j] = (yhat_cal[sel] == i).mean() if sel.sum() else 0.0
    q = np.array([(p_test < thr).mean(), (p_test >= thr).mean()])
    try:
        w = np.linalg.solve(C, q)
    except np.linalg.LinAlgError:
        w = np.array([1.0, 1.0])
    pv = np.clip(w * np.array([1 - pi_train, pi_train]), 1e-6, None)
    pid = float(np.clip(pv[1] / pv.sum(), 1e-4, 0.95))
    p = np.clip(p_test, 1e-6, 1 - 1e-6)

    def recon(delta):
        odds = (
            (p / (1 - p))
            * (pid / (1 - pid))
            * ((1 - pi_train) / pi_train)
            * np.exp(delta)
        )
        return odds / (1 + odds)

    lo, hi = -8.0, 8.0
    if (recon(lo).mean() - pid) * (recon(hi).mean() - pid) <= 0:
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if (recon(mid).mean() - pid) * (recon(lo).mean() - pid) <= 0:
                hi = mid
            else:
                lo = mid
        delta = 0.5 * (lo + hi)
    else:
        delta = 0.0
    return np.clip(recon(delta), 1e-6, 1 - 1e-6)


@pytest.fixture(scope="module")
def labels():
    d = pd.read_csv(LABELS)
    return dict(zip(d["row_id"].astype(int), (d["y"].astype(str) == "yes").astype(int)))


@pytest.fixture(scope="module")
def preds():
    return pd.read_csv(OUT / "predictions.csv")


@pytest.fixture(scope="module")
def metrics():
    return json.loads((OUT / "metrics.json").read_text())


@pytest.fixture(scope="module")
def oracle(labels):
    df = pd.read_csv(DATA / DATAFILE)
    assert "row_id" in df.columns
    lab = df["y"].astype(str).isin(["yes", "no"])
    train = df.loc[lab].reset_index(drop=True)
    test = df.loc[~lab].reset_index(drop=True)
    y_true = np.array([labels[int(r)] for r in test["row_id"]])
    cols = [(c, False) for c in NUMS] + [(c, True) for c in CATS]
    maps = {}
    for c in CATS:
        maps[c] = {v: i for i, v in enumerate(sorted(df[c].astype(str).unique()))}

    def encode(fr):
        X = np.empty((len(fr), len(cols)))
        for j, (c, is_cat) in enumerate(cols):
            X[:, j] = (
                fr[c].astype(str).map(maps[c]).to_numpy()
                if is_cat
                else fr[c].astype(float).to_numpy()
            )
        return X

    mask = [is_cat for _, is_cat in cols]
    n = len(train)
    cal_mask = (np.arange(n) % 4) == 0
    fit = train.loc[~cal_mask]
    cal = train.loc[cal_mask]
    m = HistGradientBoostingClassifier(
        random_state=42, max_iter=300, learning_rate=0.08, categorical_features=mask
    ).fit(encode(fit), fit["y"].astype(str).eq("yes").astype(int))
    p_cal = np.clip(m.predict_proba(encode(cal))[:, 1], 1e-6, 1 - 1e-6)
    p_test = np.clip(m.predict_proba(encode(test))[:, 1], 1e-6, 1 - 1e-6)
    pi_train = float(fit["y"].astype(str).eq("yes").mean())
    pte = _bbse_reconcile(
        p_cal, cal["y"].astype(str).eq("yes").astype(int).to_numpy(), p_test, pi_train
    )
    sub = test[SUBGROUP].astype(str).to_numpy()
    graded, per_sub = [], {}
    for g in sorted(set(sub)):
        mk = sub == g
        if int(mk.sum()) < MIN_EVAL or int(y_true[mk].sum()) < MIN_POS:
            continue
        graded.append(g)
        per_sub[g] = {
            "auc": roc_auc_score(y_true[mk], pte[mk]),
            "brier": brier_score_loss(y_true[mk], pte[mk]),
            "base_rate": float(y_true[mk].mean()),
            "cal_gap": abs(float(pte[mk].mean()) - float(y_true[mk].mean())),
        }
    aucs = [per_sub[g]["auc"] for g in graded]
    briers = [per_sub[g]["brier"] for g in graded]
    cals = [per_sub[g]["cal_gap"] for g in graded]
    return {
        "n_train": int(lab.sum()),
        "n_test": int((~lab).sum()),
        "n_subgroups": int(df[SUBGROUP].nunique()),
        "test_ids": set(int(r) for r in test["row_id"]),
        "auc": roc_auc_score(y_true, pte),
        "ap": average_precision_score(y_true, pte),
        "brier": brier_score_loss(y_true, pte),
        "graded": graded,
        "per_sub": per_sub,
        "worst_cal": max(cals),
        "auc_spread": max(aucs) - min(aucs),
        "brier_spread": max(briers) - min(briers),
        "subgroups": dict(zip(test["row_id"].astype(int), sub)),
    }


@pytest.fixture(scope="module")
def merged(preds, labels, oracle):
    m = preds.copy()
    m["row_id"] = m["row_id"].astype(int)
    m["y"] = m["row_id"].map(labels)
    m["subgroup"] = m["row_id"].map(oracle["subgroups"])
    return m.dropna(subset=["y"])


def _sub_stats(merged, oracle):
    out = {}
    for g in oracle["graded"]:
        grp = merged[merged["subgroup"] == g]
        out[g] = {
            "auc": roc_auc_score(
                grp["y"].to_numpy(int), grp["pred_proba"].to_numpy(float)
            ),
            "brier": brier_score_loss(
                grp["y"].to_numpy(int), grp["pred_proba"].to_numpy(float)
            ),
            "cal_gap": abs(
                float(grp["pred_proba"].mean()) - oracle["per_sub"][g]["base_rate"]
            ),
        }
    return out


class TestArtifacts:
    def test_predictions_exist(self):
        assert (OUT / "predictions.csv").is_file()

    def test_metrics_schema(self, metrics):
        expected = {
            "n_train",
            "n_test",
            "roc_auc_val",
            "pr_auc_val",
            "brier_val",
            "n_subgroups",
        }
        assert set(metrics) == expected
        for k, v in metrics.items():
            assert isinstance(v, str)

    def test_validation_metrics_plausible(self, metrics):
        for key in ["roc_auc_val", "pr_auc_val", "brier_val"]:
            value = float(metrics[key])
            assert np.isfinite(value) and 0.0 <= value <= 1.0


class TestCoverage:
    def test_covers_every_test_row(self, preds, oracle):
        assert set(preds["row_id"].astype(int)) == oracle["test_ids"]

    def test_schema_sorted_unique(self, preds):
        assert list(preds.columns[:2]) == ["row_id", "pred_proba"]
        ids = preds["row_id"].astype(int).tolist()
        assert ids == sorted(ids) and len(ids) == len(set(ids))

    def test_proba_in_unit_interval(self, preds):
        p = preds["pred_proba"].to_numpy(dtype=float)
        assert np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all()

    def test_counts_reported(self, metrics, oracle):
        assert int(metrics["n_train"]) == oracle["n_train"]
        assert int(metrics["n_test"]) == oracle["n_test"]
        assert int(metrics["n_subgroups"]) == oracle["n_subgroups"]


@ref_skip
class TestGlobalDiscrimination:
    def test_auc_near_reference(self, merged, oracle):
        auc = roc_auc_score(
            merged["y"].to_numpy(int), merged["pred_proba"].to_numpy(float)
        )
        assert auc >= oracle["auc"] - AUC_TOL, (
            f"held-out AUC {auc:.4f} below reference {oracle['auc']:.4f} - {AUC_TOL}"
        )

    def test_pr_auc_near_reference(self, merged, oracle):
        ap = average_precision_score(
            merged["y"].to_numpy(int), merged["pred_proba"].to_numpy(float)
        )
        assert ap >= oracle["ap"] - PR_TOL

    def test_brier_near_reference(self, merged, oracle):
        brier = brier_score_loss(
            merged["y"].to_numpy(int), merged["pred_proba"].to_numpy(float)
        )
        assert brier <= oracle["brier"] * BRIER_MULT


@ref_skip
class TestSubgroupCalibration:
    def test_graded_subgroups_present(self, oracle):
        assert len(oracle["graded"]) >= 5

    def test_subgroup_auc_floor(self, merged, oracle):
        stats = _sub_stats(merged, oracle)
        for g in oracle["graded"]:
            ref = oracle["per_sub"][g]
            assert stats[g]["auc"] >= ref["auc"] - SUB_AUC_TOL, (
                f"{g}: subgroup AUC {stats[g]['auc']:.4f} below reference {ref['auc']:.4f} - {SUB_AUC_TOL}"
            )

    def test_subgroup_brier_ceiling(self, merged, oracle):
        stats = _sub_stats(merged, oracle)
        for g in oracle["graded"]:
            ref = oracle["per_sub"][g]
            assert stats[g]["brier"] <= ref["brier"] * SUB_BRIER_MULT, (
                f"{g}: subgroup Brier {stats[g]['brier']:.5f} exceeds reference {ref['brier']:.5f} x{SUB_BRIER_MULT}"
            )

    def test_subgroup_calibration_ref_relative(self, merged, oracle):
        stats = _sub_stats(merged, oracle)
        for g in oracle["graded"]:
            ref = oracle["per_sub"][g]
            assert stats[g]["cal_gap"] <= ref["cal_gap"] + CAL_SLACK, (
                f"{g}: calibration gap {stats[g]['cal_gap']:.4f} exceeds the reference's "
                f"{ref['cal_gap']:.4f} + {CAL_SLACK}; this group is left at the enriched "
                "training rate. Recover the deployment rate and reconcile onto it."
            )


@ref_skip
class TestDisparityCertificate:
    def test_worst_subgroup_calibration(self, merged, oracle):
        stats = _sub_stats(merged, oracle)
        worst = max(stats[g]["cal_gap"] for g in oracle["graded"])
        assert worst <= oracle["worst_cal"] + DISP_CAL_TOL, (
            f"worst-subgroup calibration {worst:.4f} exceeds reference {oracle['worst_cal']:.4f} + {DISP_CAL_TOL}"
        )

    def test_auc_equity_spread(self, merged, oracle):
        stats = _sub_stats(merged, oracle)
        aucs = [stats[g]["auc"] for g in oracle["graded"]]
        assert (max(aucs) - min(aucs)) <= oracle["auc_spread"] + DISP_AUC_TOL

    def test_brier_equity_spread(self, merged, oracle):
        stats = _sub_stats(merged, oracle)
        briers = [stats[g]["brier"] for g in oracle["graded"]]
        assert (max(briers) - min(briers)) <= oracle["brier_spread"] + DISP_BRIER_TOL


class TestAntiCheat:
    def test_auc_not_perfect(self, merged):
        auc = roc_auc_score(
            merged["y"].to_numpy(int), merged["pred_proba"].to_numpy(float)
        )
        assert auc < 0.999, "AUC implausibly perfect; possible label leakage"

    def test_not_single_valued(self, preds):
        assert preds["pred_proba"].nunique() > 50, "predictions nearly constant"


class TestProtectedAttributeInvariance:
    def test_education_permutation_is_invariant(self, preds, metrics):
        if not STAGE_IS_PERMUTE:
            pytest.skip("invariance comparison only runs on the permutation stage")
        base_dir = Path(BASELINE_OUTPUT_DIR)
        base_preds = pd.read_csv(base_dir / "predictions.csv")
        base_metrics = json.loads((base_dir / "metrics.json").read_text())
        got = preds.sort_values("row_id").reset_index(drop=True)
        base = base_preds.sort_values("row_id").reset_index(drop=True)
        assert got["row_id"].astype(int).tolist() == base["row_id"].astype(int).tolist()
        delta = np.abs(
            got["pred_proba"].to_numpy(dtype=float)
            - base["pred_proba"].to_numpy(dtype=float)
        )
        assert float(delta.max(initial=0.0)) <= 1e-9, (
            "predictions changed when only the protected attribute education was permuted"
        )
        assert metrics == base_metrics, (
            "metrics.json changed after permuting only education"
        )


class TestCapability:
    def test_source_present(self):
        assert SRC.is_file() or any(Path("/app/environment").glob("*.R"))

    def test_uses_probability_model(self):
        src = _src_text().lower()
        assert any(
            m in src for m in ["glm", "binomial", "predict", "prob", "logit", "plogis"]
        )

    def test_addresses_shift_and_subgroups(self):
        src = _src_text().lower()
        assert any(
            m in src
            for m in [
                "rate",
                "prior",
                "shift",
                "reconcil",
                "recover",
                "deploy",
                "calibr",
                "education",
                "group",
            ]
        ), "source shows no deployment-rate reconciliation or subgroup handling"


def _src_text():
    if SRC.is_file():
        return SRC.read_text()
    return "\n".join(p.read_text() for p in Path("/app/environment").glob("*.R"))
