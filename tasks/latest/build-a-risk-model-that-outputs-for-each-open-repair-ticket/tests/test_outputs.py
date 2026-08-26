"""Verifier for the field-service repeat-visit task.

The hidden outcomes for the open service_month never enter the image; they live only
at /tests/eval_labels.csv. Every gate recomputes its reference in numpy/pandas from the
agent's submitted predictions and the hidden labels, then turns pass/fail into the
reward. The load-bearing gate is within-equipment_class calibration across the
job_complexity range on the open batch, which sits three service_months past the last
labeled period: only a full-history saturating fit with a per-class complexity slope
clears the tolerance, while flat, linear, and pooled fits fail.
"""
import json
import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

warnings.filterwarnings("ignore")

PUBLIC = Path(os.environ.get("APP_PUBLIC", "/app/data/service_ledger.csv"))
OUT = Path(os.environ.get("APP_OUT", "/app/outputs"))
LABELS = Path(os.environ.get("APP_LABELS", "/tests/eval_labels.csv"))

FN_COST, FP_COST = 5, 1
IDC = "ticket_id"
PERIOD = "service_month"
TARGET = "repeat_visit"
CLASS = "equipment_class"
DRIVER = "job_complexity"
LEAK = "qa_signoff_code"
PEND_PERIOD = 13
KNOWN = ["hvac", "elevator", "chiller", "generator", "boiler"]
COLD = "solar_pv"
VALID_TOKENS = {"0", "1", "0.0", "1.0", "", "nan", "none"}

CALIB_TOL = 0.05
ECE_TOL = 0.05
SEG_TOL = 0.08
COLD_TOL = 0.11
AUC_BAND = (0.68, 0.88)
EVAL_AUC_FLOOR = 0.68
GEN_TOL = 0.08
RECALL_FLOOR = 0.50
COST_FRAC = 0.70

COST_CURVE_COLS = ["threshold", "tp", "fp", "tn", "fn", "expected_cost"]
REQUIRED_METRIC_KEYS = [
    "n_train", "n_validation", "n_test",
    "train_positive_rate", "validation_positive_rate",
    "roc_auc", "pr_auc", "recall",
    "threshold", "expected_cost", "cost_fn", "cost_fp",
]
UNIT_INTERVAL_METRICS = [
    "train_positive_rate", "validation_positive_rate",
    "roc_auc", "pr_auc", "recall", "threshold",
]

_C = {}


def ctx():
    if _C:
        return _C
    raw = pd.read_csv(PUBLIC, dtype=str, keep_default_na=False)
    d = raw.drop_duplicates(IDC, keep="first").copy()
    live = d[d["record_type"].str.strip().str.lower() != "qa_audit"].copy()
    tok = live[TARGET].str.strip().str.lower()
    used = live[tok.isin(VALID_TOKENS) & live[TARGET].str.strip().ne("")]
    pend = raw[raw[PERIOD] == str(PEND_PERIOD)].drop_duplicates(IDC, keep="first").copy()
    labels = pd.read_csv(LABELS).drop_duplicates(IDC).set_index(IDC)[TARGET].astype(int)
    order = pend[IDC].astype(str).to_numpy()
    cl = pend[CLASS].astype(str).str.strip().str.lower().to_numpy()
    drv = pd.to_numeric(pend[DRIVER], errors="coerce").to_numpy()
    hist_raw_rows = int((pd.to_numeric(raw[PERIOD], errors="coerce") < PEND_PERIOD).sum())
    _C.update(dict(
        order=order, pend_ids=set(order.tolist()), n_pending=len(order),
        labels=labels, cl=cl, drv=drv, raw_rows=hist_raw_rows, unique_tickets=len(d),
        rows_used=len(used), forbidden={IDC, TARGET, PERIOD, LEAK},
        n_pos=int(labels.reindex(order).sum()),
        seen=set(KNOWN), unseen={COLD}, raw=raw,
    ))
    return _C


def preds():
    return pd.read_csv(OUT / "predictions.csv")


def metrics():
    return json.loads((OUT / "metrics.json").read_text())


def cost_curve():
    return pd.read_csv(OUT / "cost_curve.csv")


def aligned(c):
    p = preds().drop_duplicates(IDC).set_index(IDC)
    ids = list(c["order"])
    prob = pd.to_numeric(p["repeat_probability"].reindex(ids), errors="coerce").to_numpy()
    flag = pd.to_numeric(p["dispatch_flag"].reindex(ids), errors="coerce").to_numpy()
    y = c["labels"].reindex(ids).to_numpy().astype(float)
    return prob, flag, y


def _cost(y, flag):
    fn = int(((flag == 0) & (y == 1)).sum())
    fp = int(((flag == 1) & (y == 0)).sum())
    return FN_COST * fn + FP_COST * fp


def _decile_ece(p, y):
    q = pd.qcut(p, 10, labels=False, duplicates="drop")
    g = pd.DataFrame({"p": p, "y": y, "q": q}).groupby("q").agg(
        mp=("p", "mean"), my=("y", "mean"), n=("y", "size"))
    return float((g["n"] / g["n"].sum() * (g["mp"] - g["my"]).abs()).sum())


def _seg_gce(c, p, y):
    """Worst within-class x job_complexity-tertile calibration gap on the open batch. Max
    (not weighted mean) so a pooled slope's over/under errors inside a class do not cancel."""
    cl, drv = c["cl"], c["drv"]
    worst = 0.0
    for seg in KNOWN:
        m = cl == seg
        if m.sum() < 200:
            continue
        try:
            t = pd.qcut(drv[m], 3, labels=False, duplicates="drop")
        except ValueError:
            continue
        for k in np.unique(t):
            cell = m.copy()
            cell[m] = t == k
            if int(cell.sum()) < 80:
                continue
            worst = max(worst, abs(p[cell].mean() - y[cell].mean()))
    return worst


def test_predictions_cover_every_pending_ticket():
    """Every open ticket, cold-start class included, carries one finite probability in [0, 1] and a binary flag."""
    c = ctx()
    p = preds().drop_duplicates(IDC)
    assert len(set(p[IDC].astype(str)) & c["pend_ids"]) == c["n_pending"], "not every open ticket is scored"
    prob, flag, _ = aligned(c)
    assert np.all(np.isfinite(prob)) and np.all((prob >= 0) & (prob <= 1)), "probabilities missing or out of range"
    assert set(np.unique(flag[np.isfinite(flag)]).tolist()) <= {0, 1}, "flag is not binary"


def test_probabilities_calibrated_in_aggregate():
    """Mean predicted probability on the open batch must match the observed repeat rate."""
    c = ctx()
    prob, _, y = aligned(c)
    assert abs(float(np.mean(prob)) - float(np.mean(y))) <= CALIB_TOL


def test_probabilities_calibrated_across_range():
    """Predicted probabilities must be calibrated across their range, not only on average."""
    c = ctx()
    prob, _, y = aligned(c)
    assert _decile_ece(prob, y) <= ECE_TOL


def test_probabilities_calibrated_within_each_class():
    """Within each equipment_class the mean probability must track the observed repeat rate across the job_complexity range; a flat, linear, or pooled fit fails while a full-history saturating fit with per-class slope clears the band."""
    c = ctx()
    prob, _, y = aligned(c)
    gce = _seg_gce(c, prob, y)
    assert gce <= SEG_TOL, f"within-class calibration error {gce:.4f} exceeds {SEG_TOL}"


def test_cold_start_class_scored_from_fallback():
    """The class absent from the labeled history is scored finitely and calibrated to its own base rate through a pooled fallback."""
    c = ctx()
    prob, _, y = aligned(c)
    m = c["cl"] == COLD
    assert m.sum() > 0 and np.all(np.isfinite(prob[m]))
    assert abs(float(prob[m].mean()) - float(y[m].mean())) <= COLD_TOL


def test_eval_auc_meets_floor():
    """Open-batch ranking must clear the concordance floor; a model whose discrimination came from a now-provisional leak collapses here."""
    c = ctx()
    prob, _, y = aligned(c)
    assert roc_auc_score(y, prob) >= EVAL_AUC_FLOOR


def test_reported_validation_generalizes_to_open():
    """The reported validation ROC AUC must approximately hold on the open batch; a leak-inflated validation score does not."""
    c = ctx()
    prob, _, y = aligned(c)
    assert abs(float(metrics()["roc_auc"]) - roc_auc_score(y, prob)) <= GEN_TOL


def test_validation_auc_in_band():
    """The reported validation ROC AUC sits in the leakage-free band; retaining the post-outcome qa_signoff_code field pushes it above the ceiling."""
    lo, hi = AUC_BAND
    assert lo <= float(metrics()["roc_auc"]) <= hi


def test_dispatch_recall_above_floor():
    """Enough true repeat tickets must be flagged; a flag-almost-nothing policy is rejected."""
    c = ctx()
    _, flag, y = aligned(c)
    flag = np.where(np.isfinite(flag), flag, 0).astype(int)
    recall = float(flag[y == 1].mean()) if (y == 1).any() else 0.0
    assert recall >= RECALL_FLOOR, f"recall {recall:.3f} below floor {RECALL_FLOOR}"


def test_eval_cost_within_ceiling():
    """Expected mis-dispatch cost on the open batch stays within the five-to-one budget ceiling."""
    c = ctx()
    _, flag, y = aligned(c)
    flag = np.where(np.isfinite(flag), flag, 0).astype(int)
    assert _cost(y, flag) <= COST_FRAC * FN_COST * c["n_pos"]


def test_model_terms_exclude_id_target_period_and_leak():
    """Reported model terms exclude the identifier, target, service_month index, and the post-outcome qa_signoff_code field."""
    c = ctx()
    feats = [str(x) for x in pd.read_csv(OUT / "model_terms.csv")["feature"].tolist()]
    for f in feats:
        assert f not in c["forbidden"], f"model term {f} is an excluded field"
        assert LEAK not in f, f"model term {f} derives from the leak field {LEAK}"


def test_model_terms_keep_signal_features():
    """The genuine ticket features and the equipment_class appear among the inputs."""
    feats = " ".join(str(x) for x in pd.read_csv(OUT / "model_terms.csv")["feature"].tolist())
    assert "job_complexity" in feats and ("equipment_class" in feats or "cls_" in feats)


def test_model_terms_importance_nonnegative():
    """model_terms.csv importances are finite nonnegative magnitudes, as the contract
    requires; a signed or missing importance is rejected."""
    imp = pd.to_numeric(pd.read_csv(OUT / "model_terms.csv")["importance"], errors="coerce").to_numpy()
    assert np.all(np.isfinite(imp)), "model_terms importance has missing or non-numeric values"
    assert np.all(imp >= 0), "model_terms importance must be nonnegative"


def test_fit_summary_reconciles_counts():
    """The fit summary reports the raw, deduplicated and usable ticket counts; usable drops the internal qa_audit tickets."""
    c = ctx()
    fs = pd.read_csv(OUT / "fit_summary.csv").set_index("metric")["value"].to_dict()
    assert int(fs.get("raw_historical_rows", -1)) == c["raw_rows"], "raw historical row count wrong (distinct ticket_id over the whole ledger)"
    assert int(fs.get("unique_tickets", -1)) == c["unique_tickets"], "deduplicated ticket count wrong"
    assert int(fs.get("rows_used", -1)) == c["rows_used"], "usable-record count wrong (labeled live rows; drops qa_audit and open)"


def test_declared_cost_and_test_size():
    """The declared cost ratio and open-batch count match the task facts."""
    c = ctx()
    m = metrics()
    assert int(m["cost_fn"]) == FN_COST and int(m["cost_fp"]) == FP_COST
    assert int(m["n_test"]) == c["n_pending"]


def test_leak_is_present_not_blank_on_open():
    """The qa_signoff_code leak carries a provisional value on the open tickets (not blank), so a drop-blank-on-open screen misses it; it must be excluded by meaning."""
    c = ctx()
    pend = c["raw"][c["raw"][PERIOD] == str(PEND_PERIOD)]
    vals = pend[LEAK].astype(str).str.strip()
    assert (vals != "").mean() > 0.95, "leak should be populated (provisional) on the open batch"


def test_cleaning_artifacts_present():
    """The raw export carries duplicate tickets, a -1 sentinel, junk dispatch tokens, and internal qa_audit rows that the cohort must handle."""
    raw = ctx()["raw"]
    assert int(raw[IDC].duplicated().sum()) >= 1, "no duplicate tickets"
    assert (pd.to_numeric(raw["prior_tickets_90d"], errors="coerce") == -1).any(), "no -1 sentinel"
    ch = raw["dispatch_channel"].astype(str).str.strip().str.lower()
    assert (~ch.isin(["phone", "portal", "auto", ""])).any(), "no junk dispatch tokens"
    assert (raw["record_type"].str.strip().str.lower() == "qa_audit").any(), "no internal qa_audit rows"


def test_all_required_artifacts_present_with_columns():
    """Every artifact named in the output contract exists and carries its required columns, so no
    required output is silently missing or renamed."""
    for name in ("predictions.csv", "metrics.json", "cost_curve.csv", "model_terms.csv", "fit_summary.csv"):
        assert (OUT / name).exists(), f"required artifact {name} is missing"
    for col in [IDC, "repeat_probability", "dispatch_flag"]:
        assert col in preds().columns, f"predictions.csv missing required column {col}"
    assert isinstance(metrics(), dict), "metrics.json must be a single JSON object"
    cc = cost_curve()
    assert list(cc.columns) == COST_CURVE_COLS, (
        f"cost_curve.csv columns {list(cc.columns)} do not match required {COST_CURVE_COLS}"
    )
    mt = pd.read_csv(OUT / "model_terms.csv")
    assert list(mt.columns) == ["feature", "importance"], "model_terms.csv columns must be feature,importance"
    fs = pd.read_csv(OUT / "fit_summary.csv")
    assert list(fs.columns) == ["metric", "value"], "fit_summary.csv columns must be metric,value"


def test_metrics_reports_every_required_field():
    """metrics.json carries every required key with values in a sane range, so no required field is
    silently missing or malformed."""
    m = metrics()
    for k in REQUIRED_METRIC_KEYS:
        assert k in m, f"metrics.json missing required key {k}"
    for k in UNIT_INTERVAL_METRICS:
        v = float(m[k])
        assert 0.0 <= v <= 1.0, f"metrics.json {k}={v} outside [0, 1]"
    assert float(m["expected_cost"]) >= 0, "expected_cost must be non-negative"
    for k in ["n_train", "n_validation", "n_test"]:
        assert int(m[k]) > 0, f"metrics.json {k} must be a positive count"


def test_cost_curve_present_and_reconciles():
    """cost_curve.csv carries every required column in order and at least two swept operating points,
    each row's expected_cost reconciles with the 5:1 miss-to-false-alarm weighting over one fixed
    validation cohort, and the reported operating threshold lies inside the swept range."""
    cc = cost_curve()
    assert list(cc.columns) == COST_CURVE_COLS, (
        f"cost_curve.csv columns {list(cc.columns)} do not match required {COST_CURVE_COLS}"
    )
    assert len(cc) >= 2, "cost_curve.csv reports no swept operating points"
    thr = pd.to_numeric(cc["threshold"], errors="coerce").to_numpy()
    tp = pd.to_numeric(cc["tp"], errors="coerce").to_numpy()
    fp = pd.to_numeric(cc["fp"], errors="coerce").to_numpy()
    tn = pd.to_numeric(cc["tn"], errors="coerce").to_numpy()
    fn = pd.to_numeric(cc["fn"], errors="coerce").to_numpy()
    ec = pd.to_numeric(cc["expected_cost"], errors="coerce").to_numpy()
    assert np.all(np.isfinite(thr)) and np.all((thr >= 0) & (thr <= 1)), "cost_curve thresholds must lie in [0, 1]"
    for name, a in [("tp", tp), ("fp", fp), ("tn", tn), ("fn", fn), ("expected_cost", ec)]:
        assert np.all(np.isfinite(a)) and np.all(a >= 0), f"cost_curve column {name} has negative or missing values"
    total = tp + fp + tn + fn
    assert total[0] > 0 and np.all(total == total[0]), "every row must confuse the same validation cohort"
    assert np.allclose(ec, FN_COST * fn + FP_COST * fp), "expected_cost does not apply the 5:1 weighting"
    t = float(metrics()["threshold"])
    assert float(thr.min()) <= t <= float(thr.max()), "reported operating threshold lies outside the swept cost curve"


def test_metrics_reconcile_with_cost_curve():
    """The reported validation expected_cost, recall and positive rate reconcile with the swept cost
    curve at the reported operating threshold, binding the headline numbers to the fitted model's
    behaviour on the validation cohort rather than letting them be declared independently."""
    m = metrics()
    cc = cost_curve()
    thr = float(m["threshold"])
    tcol = pd.to_numeric(cc["threshold"], errors="coerce").to_numpy()
    j = int(np.argmin(np.abs(tcol - thr)))
    assert abs(float(tcol[j]) - thr) <= 1e-6, "reported threshold is not one of the swept cost-curve operating points"
    tp = float(cc["tp"].iloc[j])
    fp = float(cc["fp"].iloc[j])
    fn = float(cc["fn"].iloc[j])
    tn = float(cc["tn"].iloc[j])
    total = tp + fp + tn + fn
    pos = tp + fn
    assert pos > 0 and total > 0, "cost curve operating point has an empty cohort"
    assert abs(float(m["expected_cost"]) - (FN_COST * fn + FP_COST * fp)) <= 1e-6, "reported expected_cost does not match the cost curve at the operating threshold"
    assert abs(float(m["recall"]) - tp / pos) <= 1e-3, "reported recall does not match the cost curve at the operating threshold"
    assert abs(float(m["validation_positive_rate"]) - pos / total) <= 1e-3, "reported validation_positive_rate does not match the cost curve cohort"
