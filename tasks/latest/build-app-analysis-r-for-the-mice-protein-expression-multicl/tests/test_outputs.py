"""Verifier for mice-protein-missing-multi-class."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("/app/outputs")
DATA = Path("/app/data/train.csv")
ANALYSIS = Path("/app/analysis.R")
TEST_DIR = Path(os.environ.get("TEST_DIR", "/tests"))
VERIFY_PY = Path(sys.executable)
PROTECTED_SOURCE_RE = re.compile(
    r"(/tests|test_outputs[.]py|/solution|solution/|/logs/verifier|reward[.]txt|ctrf[.]json)",
    re.IGNORECASE,
)
REF_CACHE = {}
TARGET = "class"
KIND = "multiclass"
POS = ""
NEG = ""
FN = 1
FP = 1
PROT = ""
NUMS = [
    "dyrk1a_n",
    "itsn1_n",
    "bdnf_n",
    "nr1_n",
    "nr2a_n",
    "pakt_n",
    "pbraf_n",
    "pcamkii_n",
    "pcreb_n",
    "pelk_n",
    "perk_n",
    "pjnk_n",
    "pkca_n",
    "pmek_n",
    "pnr1_n",
    "pnr2a_n",
    "pnr2b_n",
    "ppkcab_n",
    "prsk_n",
    "akt_n",
    "braf_n",
    "camkii_n",
    "creb_n",
    "elk_n",
    "erk_n",
    "gsk3b_n",
    "jnk_n",
    "mek_n",
    "trka_n",
    "rsk_n",
    "app_n",
    "bcatenin_n",
    "sod1_n",
    "mtor_n",
    "p38_n",
    "pmtor_n",
    "dscr1_n",
    "ampka_n",
    "nr2b_n",
    "pnumb_n",
    "raptor_n",
    "tiam1_n",
    "pp70s6_n",
    "numb_n",
    "p70s6_n",
    "pgsk3b_n",
    "ppkcg_n",
    "cdk5_n",
    "s6_n",
    "adarb1_n",
    "acetylh3k9_n",
    "rrp1_n",
    "bax_n",
    "arc_n",
    "erbb4_n",
    "nnos_n",
    "tau_n",
    "gfap_n",
    "glur3_n",
    "glur4_n",
    "il1b_n",
    "p3525_n",
    "pcasp9_n",
    "psd95_n",
    "snca_n",
    "ubiquitin_n",
    "pgsk3b_tyr216_n",
    "shh_n",
    "ps6_n",
    "syp_n",
    "cana_n",
    "bad_n",
    "bcl2_n",
    "pcfos_n",
    "h3ack18_n",
    "egr1_n",
    "h3mek4_n",
]
CATS = [
    "genotype",
    "treatment",
    "behavior",
]
CLASSES = [
    "c-CS-m",
    "c-CS-s",
    "c-SC-m",
    "c-SC-s",
    "t-CS-m",
    "t-CS-s",
    "t-SC-m",
    "t-SC-s",
]
LAM = [0.001, 0.01, 0.1, 1.0, 10.0]
PROTEIN_PAIRS = {
    "pair_01": ("dyrk1a_n", "itsn1_n"),
    "pair_02": ("bdnf_n", "nr1_n"),
    "pair_03": ("nr2a_n", "pakt_n"),
    "pair_04": ("pbraf_n", "pcamkii_n"),
    "pair_05": ("pcreb_n", "pelk_n"),
    "pair_06": ("perk_n", "pjnk_n"),
    "pair_07": ("pkca_n", "pmek_n"),
    "pair_08": ("pnr1_n", "pnr2a_n"),
}


def safe(x):
    s = re.sub("[^0-9A-Za-z]+", "_", str(x).lower()).strip("_") or "value"
    return "x_" + s if s[0].isdigit() else s


def cc(s):
    return (
        s.astype(str)
        .where(~s.isna(), "missing")
        .replace({"": "missing", "?": "missing", "nan": "missing", "NaN": "missing"})
    )


def lab(s):
    return s.map(
        lambda x: (
            str(int(float(x)))
            if pd.notna(x) and re.fullmatch(r"-?\d+(\.0+)?", str(x))
            else str(x)
        )
    ).astype(str)


def learn(d):
    f = d[d.split_role == "fit"]
    m = {}
    sd = {}
    lv = {}
    for c in NUMS:
        v = pd.to_numeric(f[c], errors="coerce")
        mu = float(v.mean()) if v.notna().any() else 0.0
        vv = v.fillna(mu)
        ss = float(vv.std(ddof=1)) if len(vv) > 1 else 1.0
        m[c] = mu
        sd[c] = ss if np.isfinite(ss) and ss != 0 else 1.0
    for c in CATS:
        lv[c] = sorted(cc(f[c]).unique().tolist())
    return m, sd, lv


def mx(d, o):
    m, sd, lv = o
    cols = [np.ones(len(d))]
    names = ["intercept"]
    for c in NUMS:
        v = pd.to_numeric(d[c], errors="coerce").fillna(m[c]).to_numpy(float)
        cols.append((v - m[c]) / sd[c])
        names.append(c)
    for c in CATS:
        v = cc(d[c])
        for a in lv[c]:
            cols.append((v == a).astype(float).to_numpy())
            names.append(f"{c}__{safe(a)}")
    return np.column_stack(cols), names


def ridge(x, y, lam):
    p = np.eye(x.shape[1])
    p[0, 0] = 0.0
    return np.linalg.solve(x.T @ x + lam * p, x.T @ y)


def sg(x):
    return 1 / (1 + np.exp(-np.clip(x, -35, 35)))


def sm(x):
    z = x - x.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


def llb(y, p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def llm(i, p):
    return float(-np.log(np.clip(p[np.arange(len(i)), i], 1e-9, 1)).mean())


def ba(a, p, cls):
    return float(np.mean([(p[a == c] == c).mean() for c in cls if (a == c).sum() > 0]))


def mf(a, p, cls):
    z = []
    for c in cls:
        tp = ((a == c) & (p == c)).sum()
        fp = ((a != c) & (p == c)).sum()
        fn = ((a == c) & (p != c)).sum()
        pr = 0 if tp + fp == 0 else tp / (tp + fp)
        rc = 0 if tp + fn == 0 else tp / (tp + fn)
        z.append(0 if pr + rc == 0 else 2 * pr * rc / (pr + rc))
    return float(np.mean(z))


def auc(y, p):
    y = np.asarray(y)
    r = pd.Series(p).rank(method="average").to_numpy()
    n1 = (y == 1).sum()
    n0 = (y == 0).sum()
    return (
        float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
        if n1 and n0
        else np.nan
    )


def stability_refits(d):
    """Recompute four fit-only internal validation refits."""
    fit_pool = d[d.split_role == "fit"].copy()
    probability_columns = ["proba_" + safe(label) for label in CLASSES]
    prediction_parts = []
    report_rows = []
    row_ids = pd.to_numeric(fit_pool.row_id).astype(int)

    for repeat_id in range(1, 5):
        validation_mask = row_ids % 4 == repeat_id - 1
        internal_fit = fit_pool.loc[~validation_mask].copy()
        internal_validation = fit_pool.loc[validation_mask].copy()
        internal_fit.loc[:, "split_role"] = "fit"
        prep = learn(internal_fit)
        x_fit, _ = mx(internal_fit, prep)
        x_validation, _ = mx(internal_validation, prep)
        y_fit_index = pd.Categorical(
            lab(internal_fit[TARGET]), categories=CLASSES
        ).codes
        y_validation_index = pd.Categorical(
            lab(internal_validation[TARGET]), categories=CLASSES
        ).codes
        y_fit = np.zeros((len(internal_fit), len(CLASSES)))
        y_fit[np.arange(len(internal_fit)), y_fit_index] = 1

        lambda_rows = []
        models = {}
        for lam in LAM:
            beta = ridge(x_fit, y_fit, lam)
            models[lam] = beta
            probability = sm(x_validation @ beta)
            lambda_rows.append(
                {
                    "lambda": lam,
                    "validation_log_loss": llm(y_validation_index, probability),
                }
            )
        lambda_report = pd.DataFrame(lambda_rows)
        best = lambda_report.sort_values(
            ["validation_log_loss", "lambda"]
        ).iloc[0]
        selected_lambda = float(best["lambda"])
        probability = sm(x_validation @ models[selected_lambda])
        predicted = np.array(CLASSES, dtype=object)[probability.argmax(axis=1)]
        actual = lab(internal_validation[TARGET]).to_numpy()
        prediction_frame = pd.DataFrame(
            {
                "repeat_id": repeat_id,
                "row_id": internal_validation.row_id.to_numpy(),
                "actual": actual,
                "predicted": predicted,
            }
        )
        for index, column in enumerate(probability_columns):
            prediction_frame[column] = probability[:, index]
        prediction_frame["split_role"] = "stability_validation"
        prediction_parts.append(prediction_frame)
        report_rows.append(
            {
                "repeat_id": repeat_id,
                "n_fit": len(internal_fit),
                "n_validation": len(internal_validation),
                "selected_lambda": selected_lambda,
                "validation_log_loss": float(best["validation_log_loss"]),
                "validation_macro_f1": mf(actual, predicted, CLASSES),
                "mean_confidence": float(probability.max(axis=1).mean()),
            }
        )

    predictions = (
        pd.concat(prediction_parts, ignore_index=True)
        .sort_values(["repeat_id", "row_id"])
        .reset_index(drop=True)
    )
    report = pd.DataFrame(report_rows).sort_values("repeat_id").reset_index(drop=True)
    return predictions, report


def robust_lambda_consensus(validation_report, stability_report):
    """Combine the supplied split winner with four fit-only refit winners."""
    supplied_winner = float(
        validation_report.sort_values(["validation_log_loss", "lambda"]).iloc[0][
            "lambda"
        ]
    )
    rows = []
    for lam in LAM:
        stability_count = int(
            np.isclose(stability_report["selected_lambda"], lam).sum()
        )
        total_count = stability_count + int(np.isclose(supplied_winner, lam))
        supplied_loss = float(
            validation_report.loc[
                np.isclose(validation_report["lambda"], lam), "validation_log_loss"
            ].iloc[0]
        )
        rows.append(
            {
                "lambda": lam,
                "supplied_validation_log_loss": supplied_loss,
                "stability_selection_count": stability_count,
                "total_selection_count": total_count,
                "selection_rate": total_count / 5.0,
            }
        )
    consensus = (
        pd.DataFrame(rows)
        .sort_values(
            ["total_selection_count", "supplied_validation_log_loss", "lambda"],
            ascending=[False, True, True],
        )
        .reset_index(drop=True)
    )
    consensus["selected"] = 0
    consensus.loc[0, "selected"] = 1
    return consensus


def boundary_refit_report(f, t, prep, selected_lambda, base_probability, base_predicted):
    """Recompute low-margin nearest-conflict removal refits."""
    x_fit, _ = mx(f, prep)
    x_test, _ = mx(t, prep)
    margins = np.sort(base_probability, axis=1)[:, -1] - np.sort(
        base_probability, axis=1
    )[:, -2]
    audit_positions = np.lexsort((pd.to_numeric(t.row_id).to_numpy(), margins))[
        : min(10, len(t))
    ]
    rows = []
    fit_labels = lab(f[TARGET]).to_numpy()
    fit_row_ids = pd.to_numeric(f.row_id).to_numpy()
    for audit_rank, test_pos in enumerate(audit_positions, start=1):
        predicted_label = str(base_predicted[test_pos])
        candidates = np.where(fit_labels != predicted_label)[0]
        delta = x_fit[candidates, 1:] - x_test[test_pos, 1:]
        distances = np.sqrt((delta**2).sum(axis=1))
        nearest_local = np.lexsort((fit_row_ids[candidates], distances))[0]
        nearest_pos = candidates[nearest_local]
        reduced_fit = f.drop(f.index[nearest_pos]).copy()
        reduced_fit.loc[:, "split_role"] = "fit"
        reduced_prep = learn(reduced_fit)
        reduced_x, _ = mx(reduced_fit, reduced_prep)
        test_x, _ = mx(t.iloc[[test_pos]].copy(), reduced_prep)
        reduced_index = pd.Categorical(
            lab(reduced_fit[TARGET]), categories=CLASSES
        ).codes
        reduced_y = np.zeros((len(reduced_fit), len(CLASSES)))
        reduced_y[np.arange(len(reduced_fit)), reduced_index] = 1
        beta = ridge(reduced_x, reduced_y, selected_lambda)
        refit_probability = sm(test_x @ beta)[0]
        refit_predicted = CLASSES[int(refit_probability.argmax())]
        base_ordered = np.sort(base_probability[test_pos])[::-1]
        refit_ordered = np.sort(refit_probability)[::-1]
        rows.append(
            {
                "audit_rank": audit_rank,
                "row_id": t.row_id.iloc[test_pos],
                "actual": lab(t[TARGET]).iloc[test_pos],
                "baseline_predicted": predicted_label,
                "refit_predicted": refit_predicted,
                "removed_row_id": f.row_id.iloc[nearest_pos],
                "removed_label": fit_labels[nearest_pos],
                "nearest_distance": float(distances[nearest_local]),
                "baseline_margin": float(base_ordered[0] - base_ordered[1]),
                "refit_margin": float(refit_ordered[0] - refit_ordered[1]),
                "probability_l1_shift": float(
                    np.abs(refit_probability - base_probability[test_pos]).sum()
                ),
                "decision_changed": int(refit_predicted != predicted_label),
            }
        )
    return pd.DataFrame(rows)


def paired_boundary_reselection_report(f, v, t, prep, base_probability, base_predicted):
    """Recompute paired nearest-boundary removals with local lambda reselection."""
    x_fit, _ = mx(f, prep)
    x_test, _ = mx(t, prep)
    margins = np.sort(base_probability, axis=1)[:, -1] - np.sort(
        base_probability, axis=1
    )[:, -2]
    audit_positions = np.lexsort((pd.to_numeric(t.row_id).to_numpy(), margins))[
        : min(10, len(t))
    ]
    validation_index = pd.Categorical(lab(v[TARGET]), categories=CLASSES).codes
    rows = []
    fit_labels = lab(f[TARGET]).to_numpy()
    fit_row_ids = pd.to_numeric(f.row_id).to_numpy()
    for audit_rank, test_pos in enumerate(audit_positions, start=1):
        predicted_label = str(base_predicted[test_pos])
        conflict_candidates = np.where(fit_labels != predicted_label)[0]
        conflict_delta = x_fit[conflict_candidates, 1:] - x_test[test_pos, 1:]
        conflict_distances = np.sqrt((conflict_delta**2).sum(axis=1))
        conflict_local = np.lexsort(
            (fit_row_ids[conflict_candidates], conflict_distances)
        )[0]
        conflict_pos = conflict_candidates[conflict_local]
        support_candidates = np.where(fit_labels == predicted_label)[0]
        support_delta = x_fit[support_candidates, 1:] - x_test[test_pos, 1:]
        support_distances = np.sqrt((support_delta**2).sum(axis=1))
        support_local = np.lexsort(
            (fit_row_ids[support_candidates], support_distances)
        )[0]
        support_pos = support_candidates[support_local]
        reduced_fit = f.drop(f.index[[conflict_pos, support_pos]]).copy()
        reduced_fit.loc[:, "split_role"] = "fit"
        reduced_prep = learn(reduced_fit)
        reduced_x, _ = mx(reduced_fit, reduced_prep)
        validation_x, _ = mx(v, reduced_prep)
        test_x, _ = mx(t.iloc[[test_pos]].copy(), reduced_prep)
        reduced_index = pd.Categorical(
            lab(reduced_fit[TARGET]), categories=CLASSES
        ).codes
        reduced_y = np.zeros((len(reduced_fit), len(CLASSES)))
        reduced_y[np.arange(len(reduced_fit)), reduced_index] = 1
        lambda_rows = []
        models = {}
        for lam in LAM:
            beta = ridge(reduced_x, reduced_y, lam)
            models[lam] = beta
            probability = sm(validation_x @ beta)
            lambda_rows.append(
                {
                    "lambda": lam,
                    "validation_log_loss": llm(validation_index, probability),
                }
            )
        lambda_report = pd.DataFrame(lambda_rows)
        best = lambda_report.sort_values(["validation_log_loss", "lambda"]).iloc[0]
        selected_lambda = float(best["lambda"])
        local_probability = sm(test_x @ models[selected_lambda])[0]
        local_predicted = CLASSES[int(local_probability.argmax())]
        base_ordered = np.sort(base_probability[test_pos])[::-1]
        local_ordered = np.sort(local_probability)[::-1]
        rows.append(
            {
                "audit_rank": audit_rank,
                "row_id": t.row_id.iloc[test_pos],
                "actual": lab(t[TARGET]).iloc[test_pos],
                "baseline_predicted": predicted_label,
                "local_refit_predicted": local_predicted,
                "conflict_removed_row_id": f.row_id.iloc[conflict_pos],
                "conflict_removed_label": fit_labels[conflict_pos],
                "support_removed_row_id": f.row_id.iloc[support_pos],
                "support_removed_label": fit_labels[support_pos],
                "conflict_distance": float(conflict_distances[conflict_local]),
                "support_distance": float(support_distances[support_local]),
                "baseline_margin": float(base_ordered[0] - base_ordered[1]),
                "local_selected_lambda": selected_lambda,
                "local_validation_log_loss": float(best["validation_log_loss"]),
                "local_margin": float(local_ordered[0] - local_ordered[1]),
                "probability_l1_shift": float(
                    np.abs(local_probability - base_probability[test_pos]).sum()
                ),
                "decision_changed": int(local_predicted != predicted_label),
            }
        )
    return pd.DataFrame(rows)


def ref(d):
    o = learn(d)
    f = d[d.split_role == "fit"]
    v = d[d.split_role == "validation"]
    t = d[d.split_role == "test"]
    xf, nm = mx(f, o)
    xv, _ = mx(v, o)
    xt, _ = mx(t, o)
    if KIND == "regression":
        yf = pd.to_numeric(f[TARGET]).to_numpy(float)
        yv = pd.to_numeric(v[TARGET]).to_numpy(float)
        yt = pd.to_numeric(t[TARGET]).to_numpy(float)
        val = []
        mods = {}
        for lam in LAM:
            b = ridge(xf, yf, lam)
            mods[lam] = b
            pv = xv @ b
            val.append(
                {
                    "lambda": lam,
                    "validation_rmse": float(np.sqrt(((yv - pv) ** 2).mean())),
                    "validation_mae": float(np.abs(yv - pv).mean()),
                }
            )
        va = pd.DataFrame(val)
        sl = float(va.sort_values(["validation_rmse", "lambda"]).iloc[0]["lambda"])
        b = mods[sl]
        pr = xt @ b
        rs = yt - pr
        pred = (
            pd.DataFrame(
                {
                    "row_id": t.row_id,
                    "actual": yt,
                    "predicted": pr,
                    "residual": rs,
                    "absolute_error": abs(rs),
                    "squared_error": rs**2,
                    "split_role": t.split_role,
                }
            )
            .sort_values("row_id")
            .reset_index(drop=True)
        )
        diag = (
            pd.DataFrame({"term": nm, "coefficient": b, "abs_coefficient": abs(b)})
            .sort_values(["abs_coefficient", "term"], ascending=[False, True])
            .reset_index(drop=True)
        )
        s = pred.sort_values(["predicted", "row_id"]).reset_index(drop=True)
        bins = np.ceil(np.arange(1, len(s) + 1) * 10 / len(s)).astype(int)
        rb = pd.DataFrame(
            [
                {
                    "bin_id": k,
                    "n": int((bins == k).sum()),
                    "mean_prediction": float(s.loc[bins == k, "predicted"].mean()),
                    "mean_actual": float(s.loc[bins == k, "actual"].mean()),
                    "mean_residual": float(s.loc[bins == k, "residual"].mean()),
                    "rmse": float(np.sqrt((s.loc[bins == k, "residual"] ** 2).mean())),
                }
                for k in sorted(set(bins))
            ]
        )
        met = {
            "rmse": float(np.sqrt((rs**2).mean())),
            "mae": float(abs(rs).mean()),
            "r2": float(1 - (rs**2).sum() / ((yt - yt.mean()) ** 2).sum()),
            "residual_bias": float(rs.mean()),
            "selected_lambda": sl,
            "validation_rmse": float(
                va.sort_values(["validation_rmse", "lambda"]).iloc[0]["validation_rmse"]
            ),
            "n_fit": len(f),
            "n_validation": len(v),
            "n_test": len(t),
        }
        return (
            met,
            {
                "predictions": pred,
                "diagnostics": diag,
                "residual_report": rb,
                "validation_report": va,
            },
            {
                "task_name": "mice-protein-missing-multi-class",
                "model_family": "ridge_linear",
                "target_column": TARGET,
                "feature_columns": NUMS + CATS,
                "numeric_features": NUMS,
                "categorical_features": CATS,
                "selected_lambda": sl,
                "split_source": "split_role",
                "preprocessing_source": "fit_rows_only",
            },
        )
    if KIND == "binary":
        yf = (lab(f[TARGET]) == POS).astype(float).to_numpy()
        yv = (lab(v[TARGET]) == POS).astype(float).to_numpy()
        yt = (lab(t[TARGET]) == POS).astype(float).to_numpy()
        val = []
        mods = {}
        for lam in LAM:
            b = ridge(xf, yf, lam)
            mods[lam] = b
            val.append({"lambda": lam, "validation_log_loss": llb(yv, sg(xv @ b))})
        va = pd.DataFrame(val)
        sl = float(va.sort_values(["validation_log_loss", "lambda"]).iloc[0]["lambda"])
        b = mods[sl]
        pv = sg(xv @ b)
        pt = sg(xt @ b)
        rows = []
        for th in np.arange(0.05, 0.951, 0.05):
            pp = (pv >= th).astype(int)
            rows.append(
                {
                    "threshold": float(round(th, 12)),
                    "false_positive": int(((pp == 1) & (yv == 0)).sum()),
                    "false_negative": int(((pp == 0) & (yv == 1)).sum()),
                    "expected_cost": float(
                        (
                            FN * ((pp == 0) & (yv == 1)).sum()
                            + FP * ((pp == 1) & (yv == 0)).sum()
                        )
                        / len(yv)
                    ),
                    "split_role": "validation",
                }
            )
        tr = pd.DataFrame(rows)
        th = float(tr.sort_values(["expected_cost", "threshold"]).iloc[0]["threshold"])
        pr = np.where(pt >= th, POS, NEG)
        ac = lab(t[TARGET]).to_numpy()
        pred = (
            pd.DataFrame(
                {
                    "row_id": t.row_id,
                    "actual": ac,
                    "predicted": pr,
                    "probability_positive": pt,
                    "expected_cost_negative": pt * FN,
                    "expected_cost_positive": (1 - pt) * FP,
                    "split_role": t.split_role,
                }
            )
            .sort_values("row_id")
            .reset_index(drop=True)
        )
        met = {
            "accuracy": float((ac == pr).mean()),
            "balanced_accuracy": ba(ac, pr, CLASSES),
            "roc_auc": auc(yt, pt),
            "brier_score": float(((pt - yt) ** 2).mean()),
            "expected_cost": float(
                (
                    FN * ((pr == NEG) & (ac == POS)).sum()
                    + FP * ((pr == POS) & (ac == NEG)).sum()
                )
                / len(ac)
            ),
            "selected_lambda": sl,
            "threshold": th,
            "n_fit": len(f),
            "n_validation": len(v),
            "n_test": len(t),
            "false_negative_cost": FN,
            "false_positive_cost": FP,
        }
        cf = (
            pd.DataFrame({"term": nm, "coefficient": b, "abs_coefficient": abs(b)})
            .sort_values(["abs_coefficient", "term"], ascending=[False, True])
            .reset_index(drop=True)
        )
        order = np.lexsort((t.row_id.to_numpy(), pt))
        bins = np.ceil(np.arange(1, len(pt) + 1) * 10 / len(pt)).astype(int)
        cal = pd.DataFrame(
            [
                {
                    "bin_id": k,
                    "n": int((bins == k).sum()),
                    "min_probability": float(pt[order][bins == k].min()),
                    "max_probability": float(pt[order][bins == k].max()),
                    "mean_probability": float(pt[order][bins == k].mean()),
                    "observed_positive_rate": float(yt[order][bins == k].mean()),
                    "absolute_calibration_error": float(
                        abs(yt[order][bins == k].mean() - pt[order][bins == k].mean())
                    ),
                }
                for k in sorted(set(bins))
            ]
        )
        out = {
            "predictions": pred,
            "threshold_report": tr,
            "calibration_report": cal,
            "coefficient_report": cf,
        }
        if PROT:
            g = sorted(cc(t[PROT]).unique().tolist())
            pv2 = cc(t[PROT]).to_numpy()
            out["subgroup_report"] = pd.DataFrame(
                [
                    {
                        "group": x,
                        "n": int((pv2 == x).sum()),
                        "predicted_positive_rate": float((pr[pv2 == x] == POS).mean()),
                        "observed_positive_rate": float(yt[pv2 == x].mean()),
                        "false_negative_rate": 0.0
                        if (ac[pv2 == x] == POS).sum() == 0
                        else float(
                            ((ac[pv2 == x] == POS) & (pr[pv2 == x] == NEG)).sum()
                            / (ac[pv2 == x] == POS).sum()
                        ),
                        "false_positive_rate": 0.0
                        if (ac[pv2 == x] == NEG).sum() == 0
                        else float(
                            ((ac[pv2 == x] == NEG) & (pr[pv2 == x] == POS)).sum()
                            / (ac[pv2 == x] == NEG).sum()
                        ),
                        "balanced_accuracy": ba(ac[pv2 == x], pr[pv2 == x], CLASSES),
                    }
                    for x in g
                ]
            )
        return (
            met,
            out,
            {
                "task_name": "mice-protein-missing-multi-class",
                "model_family": "ridge_sigmoid",
                "target_column": TARGET,
                "positive_class": POS,
                "negative_class": NEG,
                "feature_columns": NUMS + CATS,
                "numeric_features": NUMS,
                "categorical_features": CATS,
                "selected_lambda": sl,
                "split_source": "split_role",
                "preprocessing_source": "fit_rows_only",
            },
        )
    yf = pd.Categorical(lab(f[TARGET]), categories=CLASSES).codes
    yv = pd.Categorical(lab(v[TARGET]), categories=CLASSES).codes
    yt = pd.Categorical(lab(t[TARGET]), categories=CLASSES).codes
    Y = np.zeros((len(f), len(CLASSES)))
    Y[np.arange(len(f)), yf] = 1
    val = []
    mods = {}
    for lam in LAM:
        b = ridge(xf, Y, lam)
        mods[lam] = b
        val.append({"lambda": lam, "validation_log_loss": llm(yv, sm(xv @ b))})
    va = pd.DataFrame(val)
    stability_predictions, stability_report = stability_refits(d)
    consensus_report = robust_lambda_consensus(va, stability_report)
    sl = float(consensus_report.loc[consensus_report["selected"] == 1, "lambda"].iloc[0])
    b = mods[sl]
    baseline_validation_prob = sm(xv @ b)
    baseline_validation_pred = np.array(CLASSES, dtype=object)[
        baseline_validation_prob.argmax(1)
    ]
    validation_actual = lab(v[TARGET]).to_numpy()
    baseline_validation_log_loss = llm(yv, baseline_validation_prob)
    baseline_validation_macro_f1 = mf(
        validation_actual, baseline_validation_pred, CLASSES
    )
    feature_drop_rows = []
    nm_array = np.array(nm, dtype=object)
    for feature in NUMS:
        keep_terms = nm_array != feature
        drop_beta = ridge(xf[:, keep_terms], Y, sl)
        drop_prob = sm(xv[:, keep_terms] @ drop_beta)
        drop_pred = np.array(CLASSES, dtype=object)[drop_prob.argmax(1)]
        drop_log_loss = llm(yv, drop_prob)
        drop_macro_f1 = mf(validation_actual, drop_pred, CLASSES)
        feature_drop_rows.append(
            {
                "feature": feature,
                "n_terms": int(keep_terms.sum()),
                "validation_log_loss": round(float(drop_log_loss), 6),
                "validation_macro_f1": round(float(drop_macro_f1), 6),
                "delta_log_loss": round(
                    float(drop_log_loss - baseline_validation_log_loss), 6
                ),
                "delta_macro_f1": round(
                    float(drop_macro_f1 - baseline_validation_macro_f1), 6
                ),
            }
        )
    feature_drop_refit_report = (
        pd.DataFrame(feature_drop_rows)
        .sort_values(
            ["delta_log_loss", "delta_macro_f1", "feature"],
            ascending=[False, True, True],
        )
        .reset_index(drop=True)
    )
    feature_drop_refit_report["rank"] = np.arange(
        1, len(feature_drop_refit_report) + 1
    )
    pair_drop_rows = []
    for pair_id, (feature_a, feature_b) in PROTEIN_PAIRS.items():
        keep_terms = ~np.isin(nm_array, [feature_a, feature_b])
        drop_beta = ridge(xf[:, keep_terms], Y, sl)
        drop_prob = sm(xv[:, keep_terms] @ drop_beta)
        drop_pred = np.array(CLASSES, dtype=object)[drop_prob.argmax(1)]
        drop_log_loss = llm(yv, drop_prob)
        drop_macro_f1 = mf(validation_actual, drop_pred, CLASSES)
        pair_drop_rows.append(
            {
                "pair_id": pair_id,
                "feature_a": feature_a,
                "feature_b": feature_b,
                "n_terms": int(keep_terms.sum()),
                "validation_log_loss": round(float(drop_log_loss), 6),
                "validation_macro_f1": round(float(drop_macro_f1), 6),
                "delta_log_loss": round(
                    float(drop_log_loss - baseline_validation_log_loss), 6
                ),
                "delta_macro_f1": round(
                    float(drop_macro_f1 - baseline_validation_macro_f1), 6
                ),
            }
        )
    protein_pair_drop_refit_report = (
        pd.DataFrame(pair_drop_rows)
        .sort_values(
            ["delta_log_loss", "delta_macro_f1", "pair_id"],
            ascending=[False, True, True],
        )
        .reset_index(drop=True)
    )
    protein_pair_drop_refit_report["rank"] = np.arange(
        1, len(protein_pair_drop_refit_report) + 1
    )
    prob = sm(xt @ b)
    ix = prob.argmax(1)
    pr = np.array(CLASSES, dtype=object)[ix]
    ac = lab(t[TARGET]).to_numpy()
    pc = ["proba_" + safe(c) for c in CLASSES]
    pred = pd.DataFrame({"row_id": t.row_id, "actual": ac, "predicted": pr})
    [pred.__setitem__(pc[i], prob[:, i]) for i in range(len(pc))]
    pred["split_role"] = t.split_role
    pred = (
        pred[["row_id", "actual", "predicted"] + pc + ["split_role"]]
        .sort_values("row_id")
        .reset_index(drop=True)
    )
    cr = []
    for c in CLASSES:
        tp = ((ac == c) & (pr == c)).sum()
        fp = ((ac != c) & (pr == c)).sum()
        fn = ((ac == c) & (pr != c)).sum()
        pp = 0 if tp + fp == 0 else tp / (tp + fp)
        rr = 0 if tp + fn == 0 else tp / (tp + fn)
        cr.append(
            {
                "class": c,
                "precision": pp,
                "recall": rr,
                "f1": 0 if pp + rr == 0 else 2 * pp * rr / (pp + rr),
                "support": int((ac == c).sum()),
            }
        )
    cm = pd.DataFrame(
        [
            {"actual": a, "predicted": p, "n": int(((ac == a) & (pr == p)).sum())}
            for a in CLASSES
            for p in CLASSES
        ]
    )
    miss = pd.DataFrame(
        [
            {
                "feature": c,
                "missing_fit": int(
                    f[c].isna().sum() + f[c].astype(str).isin(["", "?"]).sum()
                ),
                "missing_validation": int(
                    v[c].isna().sum() + v[c].astype(str).isin(["", "?"]).sum()
                ),
                "missing_test": int(
                    t[c].isna().sum() + t[c].astype(str).isin(["", "?"]).sum()
                ),
                "imputation_value": str(o[0][c]) if c in NUMS else "missing",
            }
            for c in NUMS + CATS
        ]
    )
    met = {
        "accuracy": float((ac == pr).mean()),
        "macro_f1": mf(ac, pr, CLASSES),
        "log_loss": llm(yt, prob),
        "selected_lambda": sl,
        "validation_log_loss": float(
            va.loc[np.isclose(va["lambda"], sl), "validation_log_loss"].iloc[0]
        ),
        "n_fit": len(f),
        "n_validation": len(v),
        "n_test": len(t),
        "n_classes": len(CLASSES),
    }
    return (
        met,
        {
            "predictions": pred,
            "class_report": pd.DataFrame(cr),
            "confusion_matrix": cm,
            "missing_report": miss,
            "validation_report": va,
            "stability_refit_predictions": stability_predictions,
            "stability_refit_report": stability_report,
            "robust_lambda_consensus_report": consensus_report,
            "feature_drop_refit_report": feature_drop_refit_report[
                [
                    "feature",
                    "n_terms",
                    "validation_log_loss",
                    "validation_macro_f1",
                    "delta_log_loss",
                    "delta_macro_f1",
                    "rank",
                ]
            ],
            "protein_pair_drop_refit_report": protein_pair_drop_refit_report[
                [
                    "pair_id",
                    "feature_a",
                    "feature_b",
                    "n_terms",
                    "validation_log_loss",
                    "validation_macro_f1",
                    "delta_log_loss",
                    "delta_macro_f1",
                    "rank",
                ]
            ],
            "boundary_refit_report": boundary_refit_report(f, t, o, sl, prob, pr),
            "paired_boundary_reselection_report": paired_boundary_reselection_report(
                f, v, t, o, prob, pr
            ),
        },
        {
            "task_name": "mice-protein-missing-multi-class",
            "model_family": "ridge_one_vs_rest_softmax",
            "target_column": TARGET,
            "class_order": CLASSES,
            "feature_columns": NUMS + CATS,
            "numeric_features": NUMS,
            "categorical_features": CATS,
            "selected_lambda": sl,
            "split_source": "split_role",
            "preprocessing_source": "fit_rows_only",
        },
    )


def cmpj(a, e):
    for k, v in e.items():
        assert k in a
        if isinstance(v, list):
            av = a[k] if isinstance(a[k], list) else ([] if a[k] == "" else [a[k]])
            assert av == v, k
        else:
            assert (
                np.isclose(float(a[k]), v, rtol=1e-5, atol=1e-5)
                if isinstance(v, float)
                else a[k] == v
            ), k


def cmpf(a, e):
    assert list(a.columns) == list(e.columns)
    assert len(a) == len(e)
    if "term" in e.columns:
        a = a.sort_values("term").reset_index(drop=True)
        e = e.sort_values("term").reset_index(drop=True)
    for c in e.columns:
        if pd.api.types.is_numeric_dtype(e[c]):
            assert np.allclose(
                pd.to_numeric(a[c], errors="coerce"),
                pd.to_numeric(e[c], errors="coerce"),
                rtol=1e-5,
                atol=1e-5,
                equal_nan=True,
            ), c
        elif c == "imputation_value":
            for av, ev in zip(a[c].astype(str), e[c].astype(str)):
                aa = pd.to_numeric(pd.Series([av]), errors="coerce").iloc[0]
                ee = pd.to_numeric(pd.Series([ev]), errors="coerce").iloc[0]
                assert (
                    np.isclose(aa, ee, rtol=1e-5, atol=1e-5)
                    if pd.notna(aa) and pd.notna(ee)
                    else av == ev
                ), c
        else:
            assert a[c].astype(str).tolist() == e[c].astype(str).tolist(), c


def cached_ref():
    key = DATA.read_bytes()
    if key not in REF_CACHE:
        REF_CACHE[key] = ref(pd.read_csv(DATA))
    return REF_CACHE[key]


def validate():
    m, frames, man = cached_ref()
    cmpj(json.load(open(OUT / "metrics.json")), m)
    cmpj(json.load(open(OUT / "model_manifest.json")), man)
    for n, e in frames.items():
        cmpf(pd.read_csv(OUT / (n + ".csv")), e)


def chmod_tree(path, mode):
    if path.exists():
        subprocess.run(["chmod", "-R", mode, str(path)], check=True)


def restore_protected_permissions():
    for path in (TEST_DIR, Path("/solution")):
        if path.exists():
            subprocess.run(["chmod", "-R", "a+rX", str(path)], check=False)
    if Path("/logs/verifier").exists():
        subprocess.run(["chmod", "-R", "u+rwX,go-rwx", "/logs/verifier"], check=False)


def protect_trees_from_agent():
    for path in (TEST_DIR, Path("/solution"), Path("/logs/verifier")):
        chmod_tree(path, "u+rwX,go-rwx")


def make_outputs_agent_writable():
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(["chown", "-R", "65534:65534", str(OUT)], check=True)
    subprocess.run(["chmod", "700", str(OUT)], check=True)


def assert_agent_cannot_read(path):
    if not path.exists():
        return
    probe = """
import os
import pathlib
import sys

target = pathlib.Path(sys.argv[1])
try:
    os.setgid(65534)
    os.setuid(65534)
    if target.is_dir():
        next(target.iterdir())
    else:
        target.read_bytes()
except (FileNotFoundError, PermissionError):
    sys.exit(0)
except StopIteration:
    sys.exit(0)
sys.exit(1)
"""
    result = subprocess.run(
        [str(VERIFY_PY), "-c", probe, str(path)],
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, f"{path} is readable by the analysis user"


def run():
    assert ANALYSIS.exists(), "/app/analysis.R is missing"
    assert not PROTECTED_SOURCE_RE.search(
        ANALYSIS.read_text()
    ), "analysis.R references protected verifier, solution, or reward paths"
    make_outputs_agent_writable()
    protect_trees_from_agent()
    try:
        assert_agent_cannot_read(TEST_DIR / "test_outputs.py")
        assert_agent_cannot_read(Path("/logs/verifier/reward.txt"))
        code = """
import os
import subprocess
import sys

env = os.environ.copy()
env["HOME"] = "/tmp"
env["R_USER"] = "/tmp"
env["TMPDIR"] = "/tmp"
os.setgid(65534)
os.setuid(65534)
result = subprocess.run(
    ["Rscript", "/app/analysis.R"],
    cwd="/app",
    env=env,
    text=True,
    capture_output=True,
    timeout=1200,
)
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
"""
        r = subprocess.run(
            [str(VERIFY_PY), "-c", code],
            text=True,
            capture_output=True,
            timeout=1220,
        )
    finally:
        restore_protected_permissions()
    assert r.returncode == 0, r.stdout + r.stderr


def mutate(d):
    h = d.copy()
    row = pd.to_numeric(h.row_id, errors="coerce").fillna(0).to_numpy()
    for c in NUMS:
        v = pd.to_numeric(h[c], errors="coerce")
        sd = v.std() if np.isfinite(v.std()) and v.std() != 0 else 1.0
        h[c] = v + ((row % 7) - 3) * sd * 0.015
    for c in CATS[:4]:
        lv = sorted(cc(h[c]).unique().tolist())
        if len(lv) > 1:
            mp = {v: lv[(i + 1) % len(lv)] for i, v in enumerate(lv)}
            mask = (row.astype(int) % 11) == 0
            h.loc[mask, c] = cc(h.loc[mask, c]).map(mp)
    return h


def test_required_artifacts_and_schema():
    """Required artifacts should exist with the contracted names."""
    names = ["metrics.json", "predictions.csv", "model_manifest.json"] + (
        ["threshold_report.csv", "calibration_report.csv", "coefficient_report.csv"]
        + (["subgroup_report.csv"] if PROT else [])
        if KIND == "binary"
        else ["diagnostics.csv", "residual_report.csv", "validation_report.csv"]
        if KIND == "regression"
        else [
            "class_report.csv",
            "confusion_matrix.csv",
            "missing_report.csv",
            "validation_report.csv",
            "stability_refit_predictions.csv",
            "stability_refit_report.csv",
            "robust_lambda_consensus_report.csv",
            "feature_drop_refit_report.csv",
            "protein_pair_drop_refit_report.csv",
            "boundary_refit_report.csv",
            "paired_boundary_reselection_report.csv",
        ]
    )
    for n in names:
        assert (OUT / n).exists(), n


def test_artifact_columns_and_row_counts_are_structural():
    """Core CSV artifacts expose the expected columns and row counts quickly."""
    data = pd.read_csv(DATA, keep_default_na=False)
    n_test = int((data["split_role"] == "test").sum())
    n_fit = data[data["split_role"] == "fit"].copy()
    probability_columns = ["proba_" + safe(c) for c in CLASSES]
    expected_columns = {
        "predictions.csv": ["row_id", "actual", "predicted", *probability_columns, "split_role"],
        "class_report.csv": ["class", "precision", "recall", "f1", "support"],
        "confusion_matrix.csv": ["actual", "predicted", "n"],
        "missing_report.csv": [
            "feature",
            "missing_fit",
            "missing_validation",
            "missing_test",
            "imputation_value",
        ],
        "validation_report.csv": ["lambda", "validation_log_loss"],
        "stability_refit_predictions.csv": [
            "repeat_id",
            "row_id",
            "actual",
            "predicted",
            *probability_columns,
            "split_role",
        ],
        "stability_refit_report.csv": [
            "repeat_id",
            "n_fit",
            "n_validation",
            "selected_lambda",
            "validation_log_loss",
            "validation_macro_f1",
            "mean_confidence",
        ],
        "robust_lambda_consensus_report.csv": [
            "lambda",
            "supplied_validation_log_loss",
            "stability_selection_count",
            "total_selection_count",
            "selection_rate",
            "selected",
        ],
        "feature_drop_refit_report.csv": [
            "feature",
            "n_terms",
            "validation_log_loss",
            "validation_macro_f1",
            "delta_log_loss",
            "delta_macro_f1",
            "rank",
        ],
        "protein_pair_drop_refit_report.csv": [
            "pair_id",
            "feature_a",
            "feature_b",
            "n_terms",
            "validation_log_loss",
            "validation_macro_f1",
            "delta_log_loss",
            "delta_macro_f1",
            "rank",
        ],
        "boundary_refit_report.csv": [
            "audit_rank",
            "row_id",
            "actual",
            "baseline_predicted",
            "refit_predicted",
            "removed_row_id",
            "removed_label",
            "nearest_distance",
            "baseline_margin",
            "refit_margin",
            "probability_l1_shift",
            "decision_changed",
        ],
        "paired_boundary_reselection_report.csv": [
            "audit_rank",
            "row_id",
            "actual",
            "baseline_predicted",
            "local_refit_predicted",
            "conflict_removed_row_id",
            "conflict_removed_label",
            "support_removed_row_id",
            "support_removed_label",
            "conflict_distance",
            "support_distance",
            "baseline_margin",
            "local_selected_lambda",
            "local_validation_log_loss",
            "local_margin",
            "probability_l1_shift",
            "decision_changed",
        ],
    }
    expected_rows = {
        "predictions.csv": n_test,
        "class_report.csv": len(CLASSES),
        "confusion_matrix.csv": len(CLASSES) * len(CLASSES),
        "missing_report.csv": len(NUMS) + len(CATS),
        "validation_report.csv": len(LAM),
        "stability_refit_predictions.csv": int(
            sum(((n_fit["row_id"].astype(int) % 4) == (r - 1)).sum() for r in range(1, 5))
        ),
        "stability_refit_report.csv": 4,
        "robust_lambda_consensus_report.csv": len(LAM),
        "feature_drop_refit_report.csv": len(NUMS),
        "protein_pair_drop_refit_report.csv": len(PROTEIN_PAIRS),
        "boundary_refit_report.csv": min(10, n_test),
        "paired_boundary_reselection_report.csv": min(10, n_test),
    }
    for filename, columns in expected_columns.items():
        frame = pd.read_csv(OUT / filename)
        assert list(frame.columns) == columns, filename
        assert len(frame) == expected_rows[filename], filename


def test_analysis_source_does_not_reference_protected_paths():
    """The submitted analysis cannot rely on verifier, solution, or reward paths."""
    assert not PROTECTED_SOURCE_RE.search(ANALYSIS.read_text())


def test_metrics_and_manifest_match_reference():
    """Metrics and manifest should match independent re-estimation."""
    m, frames, man = cached_ref()
    cmpj(json.load(open(OUT / "metrics.json")), m)
    cmpj(json.load(open(OUT / "model_manifest.json")), man)


def test_predictions_match_reference_rows():
    """Predictions should match the deterministic reference rows."""
    cmpf(pd.read_csv(OUT / "predictions.csv"), cached_ref()[1]["predictions"])


def test_reports_match_reference_contract():
    """All secondary reports should match the reference contract."""
    validate()


def test_stability_refits_match_reference():
    """Every internal refit probability and summary metric is recomputed."""
    _, frames, _ = cached_ref()
    for name in (
        "stability_refit_predictions",
        "stability_refit_report",
        "robust_lambda_consensus_report",
        "feature_drop_refit_report",
        "boundary_refit_report",
        "paired_boundary_reselection_report",
    ):
        cmpf(pd.read_csv(OUT / f"{name}.csv"), frames[name])


def test_hidden_data_rerun_is_not_hardcoded():
    """A hidden data rerun should match reference and change outputs."""
    original = DATA.read_bytes()
    public = pd.read_csv(OUT / "predictions.csv")
    mutate(pd.read_csv(DATA)).to_csv(DATA, index=False)
    try:
        shutil.rmtree(OUT)
        OUT.mkdir(parents=True, exist_ok=True)
        run()
        validate()
        hidden = pd.read_csv(OUT / "predictions.csv")
        assert not hidden.equals(public)
    finally:
        DATA.write_bytes(original)
