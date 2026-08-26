"""Behavioral verifier for the MGUS competing-risks modelling task.

An independent NumPy oracle recomputes the reduced exact estimand block and an
independent cause-specific-Cox competing-risks reference for the held-out
predictions, from the pristine truth fixtures, before the candidate ``analysis.R``
runs (unprivileged, once per isolated case). The candidate is graded on:

* exact agreement with the reduced marginal estimators and cohort counts, and
* reference-relative predictive performance on the held-out patients: IPCW
  competing-risks Brier score, cumulative/dynamic AUC (discrimination floor),
  calibration-in-the-large band, and anti-degeneracy checks.

The frozen gate constants were fixed from a measured gap pre-flight in which the
proper competing-risks model clears every gate with margin >= 25% of the gap
while a covariate-free marginal predictor and a competing-risk-ignoring
single-cause predictor each fail >= 2 gates on both the clean and hidden
variants.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

CASES = ("public", "hidden", "scaled")
GATED_CASES = ("public", "hidden")
FIXTURES = Path(os.environ.get("TEST_FIXTURES", "/tests/fixtures"))
CASE_ROOT = Path(os.environ.get("CASE_ROOT", "/tmp/mgus-cases"))

COVS = ("age_z", "male", "hgb_z", "creat_z", "mspike_z")
CONT = ("age", "hgb", "creat", "mspike")
STRATA = ("overall", "age_low", "age_high")
CAUSES = ("pcm", "death")
CAUSE_CODE = {"pcm": 1, "death": 2}

DELIVERABLES = (
    "estimands.csv",
    "prediction_spec.csv",
    "predictions.csv",
    "cohort_summary.json",
)
ESTIMAND_COLUMNS = ("quantity", "value")
SPEC_COLUMNS = ("cause", "model", "scale")
PREDICTION_COLUMNS = ("row_id", "horizon_month", "pcm_prob")
SUMMARY_KEYS = (
    "n_active",
    "n_heldout",
    "n_pcm_active",
    "n_death_active",
    "n_censored_active",
    "n_male_active",
    "n_female_active",
)

# Frozen gate constants (see the module docstring / task design record).
BRIER_MULT = 1.15
AUC_FLOOR = (0.52, 0.53)  # by horizon index
CALIB_LO, CALIB_HI = 0.65, 1.65
NUNIQUE_MIN = 50
FAMILIES = {
    "core": (0, 1, 3),
    "expanded": (0, 1, 2, 3),
    "full": (0, 1, 2, 3, 4),
}
FAMILY_PRIORITY = {"full": 0, "expanded": 1, "core": 2}
PREDICTION_SCALES = (0.75, 0.9, 1.0, 1.1, 1.25)

CIF_ATOL = 1e-6
BETA_ATOL = 1e-5
MEDIAN_ATOL = 1e-6
METAMORPHIC_ATOL = 1e-3

INTEGER_TOKEN = re.compile(r"-?(?:0|[1-9][0-9]*)")
DECIMAL_TOKEN = re.compile(r"-?(?:0|[1-9][0-9]*)\.[0-9]{8,}")


# --------------------------------------------------------------------------- #
# Estimators (independent of the candidate implementation).
# --------------------------------------------------------------------------- #
def _cr_setup(df):
    pstat = df["pstat"].to_numpy(float)
    death = df["death"].to_numpy(float)
    ptime = df["ptime"].to_numpy(float)
    futime = df["futime"].to_numpy(float)
    etime = np.where(pstat == 1, ptime, futime)
    event = np.where(pstat == 1, 1, np.where(death == 1, 2, 0)).astype(int)
    return etime, event


def _design(active, targets):
    med = {c: float(np.nanmedian(active[c].to_numpy(float))) for c in CONT}

    def fill(df):
        out = {}
        for c in CONT:
            v = df[c].to_numpy(float).copy()
            v[~np.isfinite(v)] = med[c]
            out[c] = v
        out["male"] = (df["sex"].to_numpy(str) == "M").astype(float)
        return out

    fa = fill(active)
    mean = {c: float(np.mean(fa[c])) for c in CONT}
    sd = {c: float(np.sqrt(np.mean((fa[c] - mean[c]) ** 2))) for c in CONT}
    for c in CONT:
        if sd[c] == 0:
            sd[c] = 1.0

    def mat(f):
        return np.column_stack(
            [
                (f["age"] - mean["age"]) / sd["age"],
                f["male"],
                (f["hgb"] - mean["hgb"]) / sd["hgb"],
                (f["creat"] - mean["creat"]) / sd["creat"],
                (f["mspike"] - mean["mspike"]) / sd["mspike"],
            ]
        )

    return mat(fa), mat(fill(targets))


def _cox_breslow(etime, event, X, cause):
    ev = (event == cause).astype(int)
    times = np.sort(np.unique(etime[ev == 1]))
    p = X.shape[1]
    beta = np.zeros(p)
    for _ in range(200):
        w = np.exp(X @ beta)
        score = np.zeros(p)
        info = np.zeros((p, p))
        for u in times:
            at_risk = etime >= u
            Xr = X[at_risk]
            wr = w[at_risk]
            s0 = wr.sum()
            s1 = Xr.T @ wr
            s2 = (Xr.T * wr) @ Xr
            d_idx = (etime == u) & (ev == 1)
            m = int(d_idx.sum())
            if m == 0:
                continue
            xbar = s1 / s0
            score += X[d_idx].sum(axis=0) - m * xbar
            info += m * (s2 / s0 - np.outer(xbar, xbar))
        step = np.linalg.solve(info, score)
        beta = beta + step
        if np.max(np.abs(step)) < 1e-12 and np.max(np.abs(score)) < 1e-8:
            break
    w = np.exp(X @ beta)
    dl0 = np.array(
        [
            m / w[etime >= u].sum()
            for u in times
            for m in [int(((etime == u) & (ev == 1)).sum())]
        ]
    )
    return beta, times, dl0


def _predict_cif_pcm(b1, t1, dl01, b2, t2, dl02, X1, X2, horizons):
    all_t = np.sort(np.unique(np.concatenate([t1, t2])))
    d1 = dict(zip(t1, dl01))
    d2 = dict(zip(t2, dl02))
    r1 = np.exp(X1 @ b1)
    r2 = np.exp(X2 @ b2)
    surv = np.ones(X1.shape[0])
    cif1 = np.zeros(X1.shape[0])
    out = np.zeros((X1.shape[0], len(horizons)))
    for u in all_t:
        dl1 = d1.get(u, 0.0) * r1
        dl2 = d2.get(u, 0.0) * r2
        cif1 = cif1 + surv * dl1
        surv = surv * (1.0 - dl1 - dl2)
        for h, hv in enumerate(horizons):
            if u <= hv:
                out[:, h] = cif1
    return out


def _aj_cif(etime, event, cause, horizons):
    times = np.sort(np.unique(etime[event > 0]))
    surv, cif = 1.0, 0.0
    out = [0.0] * len(horizons)
    for u in times:
        at_risk = int((etime >= u).sum())
        dk = int(((event == cause) & (etime == u)).sum())
        d_all = int(((event > 0) & (etime == u)).sum())
        cif += surv * (dk / at_risk)
        surv *= 1 - d_all / at_risk
        for h, hv in enumerate(horizons):
            if u <= hv:
                out[h] = cif
    return out


def _reverse_km_median(etime, event):
    cev = (event == 0).astype(int)
    times = np.sort(np.unique(etime[cev == 1]))
    surv = 1.0
    for u in times:
        at_risk = int((etime >= u).sum())
        dc = int(((cev == 1) & (etime == u)).sum())
        surv *= 1 - dc / at_risk
        if surv <= 0.5:
            return float(u)
    raise AssertionError("reverse KM never reaches 0.5")


def _reverse_km_curve(etime, event):
    cev = (event == 0).astype(int)
    times = np.sort(np.unique(etime[cev == 1]))
    G = 1.0
    tt, gg = [0.0], [1.0]
    for u in times:
        at_risk = int((etime >= u).sum())
        dc = int(((cev == 1) & (etime == u)).sum())
        G *= 1 - dc / at_risk
        tt.append(float(u))
        gg.append(G)
    return np.array(tt), np.array(gg)


def _g_at(tt, gg, t, left=False):
    side = "left" if left else "right"
    idx = max(np.searchsorted(tt, t, side=side) - 1, 0)
    return gg[idx]


def _ipcw_brier(pred, etime, event, horizon, gtt, ggg, eps=1e-8):
    n = len(pred)
    total = 0.0
    Gt = max(_g_at(gtt, ggg, horizon, left=False), eps)
    for i in range(n):
        T, e, p = etime[i], event[i], pred[i]
        if T <= horizon and e == 1:
            total += (1.0 - p) ** 2 / max(_g_at(gtt, ggg, T, left=True), eps)
        elif T <= horizon and e == 2:
            total += p * p / max(_g_at(gtt, ggg, T, left=True), eps)
        elif T > horizon:
            total += p * p / Gt
    return total / n


def _horizon_auc(pred, etime, event, horizon):
    cases = (etime <= horizon) & (event == 1)
    controls = (etime > horizon) | ((etime <= horizon) & (event == 2))
    pc, qc = pred[cases], pred[controls]
    if len(pc) == 0 or len(qc) == 0:
        return float("nan")
    greater = ties = 0.0
    for a in pc:
        greater += np.sum(a > qc)
        ties += np.sum(a == qc)
    return (greater + 0.5 * ties) / (len(pc) * len(qc))


# --------------------------------------------------------------------------- #
# Oracle construction from pristine truth fixtures.
# --------------------------------------------------------------------------- #
def _read_registry(path):
    return pd.read_csv(path)


def _build_oracle(case):
    fixture = FIXTURES / case
    truth = _read_registry(fixture / "registry_truth.csv")
    shipped = _read_registry(fixture / "registry_input.csv")
    config = pd.read_csv(fixture / "analysis.csv")
    age_cut = int(config.loc[config["parameter"] == "age_cutpoint", "value"].iloc[0])
    horizons = [int(v) for v in config.loc[config["parameter"] == "horizon", "value"]]

    held_ids = set(shipped.loc[shipped["pstat"].isna(), "row_id"].astype(int))
    truth = truth.reset_index(drop=True)
    is_held = truth["row_id"].astype(int).isin(held_ids)
    active = truth.loc[~is_held].reset_index(drop=True)
    held = truth.loc[is_held].reset_index(drop=True)

    Xa, Xt = _design(active, held)
    et, ev = _cr_setup(active)
    b1, t1, dl01 = _cox_breslow(et, ev, Xa, 1)
    b2, t2, dl02 = _cox_breslow(et, ev, Xa, 2)
    ref_pred = _predict_cif_pcm(
        b1, t1, dl01, b2, t2, dl02, Xt, Xt, horizons
    )

    def select_spec(cause):
        candidates = []
        folds = np.arange(len(active)) % 5
        for model_name, cols in FAMILIES.items():
            for scale in PREDICTION_SCALES:
                fold_scores = []
                for fold in range(5):
                    tr = folds != fold
                    va = folds == fold
                    cb, ct, cdl = _cox_breslow(
                        et[tr], ev[tr], Xa[tr][:, cols], cause
                    )
                    ob, ot, odl = _cox_breslow(
                        et[tr], ev[tr], Xa[tr], 3 - cause
                    )
                    cb = cb * scale
                    if cause == 1:
                        pv = _predict_cif_pcm(
                            cb, ct, cdl, ob, ot, odl,
                            Xa[va][:, cols], Xa[va], horizons
                        )
                    else:
                        pv = _predict_cif_pcm(
                            ob, ot, odl, cb, ct, cdl,
                            Xa[va], Xa[va][:, cols], horizons
                        )
                    scores = []
                    for h, hv in enumerate(horizons):
                        known = (ev[va] > 0) | (et[va] > hv)
                        y = ((ev[va] == 1) & (et[va] <= hv)).astype(float)
                        scores.append(float(np.mean((pv[known, h] - y[known]) ** 2)))
                    fold_scores.append(float(np.mean(scores)))
                candidates.append({
                    "model": model_name,
                    "scale": float(scale),
                    "score": float(np.mean(fold_scores)),
                })
        best = min(x["score"] for x in candidates)
        tied = [x for x in candidates if x["score"] <= best + 1e-12]
        tied.sort(key=lambda x: (
            abs(x["scale"] - 1.0),
            FAMILY_PRIORITY[x["model"]],
        ))
        return tied[0]

    pcm_spec = select_spec(1)
    death_spec = select_spec(2)

    # Refit selected specifications on the complete active cohort for grading
    # the candidate's held-out predictions.
    pcm_cols = FAMILIES[pcm_spec["model"]]
    death_cols = FAMILIES[death_spec["model"]]
    pb1, pt1, pdl01 = _cox_breslow(et, ev, Xa[:, pcm_cols], 1)
    pb2, pt2, pdl02 = _cox_breslow(et, ev, Xa[:, death_cols], 2)
    pb1 = pb1 * pcm_spec["scale"]
    pb2 = pb2 * death_spec["scale"]
    selected_pred = _predict_cif_pcm(
        pb1, pt1, pdl01, pb2, pt2, pdl02,
        Xt[:, pcm_cols], Xt[:, death_cols], horizons
    )

    # The exact reference remains the unshrunk full five-covariate model.

    # reduced exact estimand block
    est = {}
    strata = {
        "overall": active,
        "age_low": active.loc[active["age"] <= age_cut],
        "age_high": active.loc[active["age"] > age_cut],
    }
    for sname in STRATA:
        se, sv = _cr_setup(strata[sname])
        for cname in CAUSES:
            vals = _aj_cif(se, sv, CAUSE_CODE[cname], horizons)
            for h, hv in enumerate(horizons):
                est[f"aj_cif_{cname}_{sname}_{hv}"] = vals[h]
    est["reverse_km_median"] = _reverse_km_median(et, ev)
    for i, c in enumerate(COVS):
        est[f"cox_pcm_beta_{c}"] = float(b1[i])
        est[f"cox_death_beta_{c}"] = float(b2[i])

    # held-out truth for grading
    het, hev = _cr_setup(held)
    gtt, ggg = _reverse_km_curve(et, ev)
    obs = [_aj_cif(het, hev, 1, [hv])[0] for hv in horizons]
    ref_brier = [
        _ipcw_brier(ref_pred[:, h], het, hev, hv, gtt, ggg)
        for h, hv in enumerate(horizons)
    ]

    summary = {
        "n_active": int(len(active)),
        "n_heldout": int(len(held)),
        "n_pcm_active": int((active["pstat"] == 1).sum()),
        "n_death_active": int(((active["pstat"] == 0) & (active["death"] == 1)).sum()),
        "n_censored_active": int(
            ((active["pstat"] == 0) & (active["death"] == 0)).sum()
        ),
        "n_male_active": int((active["sex"] == "M").sum()),
        "n_female_active": int((active["sex"] == "F").sum()),
    }

    return {
        "horizons": horizons,
        "held_ids": sorted(int(x) for x in held["row_id"]),
        "estimands": est,
        "prediction_spec": {
            "PCM": pcm_spec,
            "DEATH": death_spec,
        },
        "selected_pred": selected_pred,
        "summary": summary,
        "held_etime": het,
        "held_event": hev,
        "gtt": gtt,
        "ggg": ggg,
        "obs": obs,
        "ref_brier": ref_brier,
        "ref_pred": ref_pred,
        "held_row_order": [int(x) for x in held["row_id"]],
    }


ORACLES = {case: _build_oracle(case) for case in CASES}
RUN_RESULTS: dict[str, tuple[int, str]] = {}


# --------------------------------------------------------------------------- #
# Candidate output access.
# --------------------------------------------------------------------------- #
def _output_path(case, filename):
    return CASE_ROOT / "outputs" / case / filename


@lru_cache(maxsize=None)
def _csv_output(case, filename):
    with _output_path(case, filename).open(newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows, f"{case}/{filename} is empty"
    return tuple(rows[0]), rows[1:]


@lru_cache(maxsize=None)
def _summary_output(case):
    with _output_path(case, "cohort_summary.json").open() as handle:
        value = json.load(handle)
    assert isinstance(value, dict)
    return value


def _parse_integer(token):
    assert INTEGER_TOKEN.fullmatch(token), f"expected integer, got {token!r}"
    return int(token)


def _parse_decimal(token):
    assert DECIMAL_TOKEN.fullmatch(token), f"expected >=8-digit decimal, got {token!r}"
    v = float(token)
    assert math.isfinite(v)
    return v


@lru_cache(maxsize=None)
def _estimand_table(case):
    _, rows = _csv_output(case, "estimands.csv")
    return {r[0]: r[1] for r in rows}


@lru_cache(maxsize=None)
def _prediction_spec(case):
    header, rows = _csv_output(case, "prediction_spec.csv")
    assert list(header) == list(SPEC_COLUMNS)
    assert len(rows) == 2
    return {r[0]: {"model": r[1], "scale": _parse_decimal(r[2])} for r in rows}


@lru_cache(maxsize=None)
def _prediction_map(case):
    _, rows = _csv_output(case, "predictions.csv")
    out = {}
    for r in rows:
        rid = _parse_integer(r[0])
        hz = _parse_integer(r[1])
        out[(rid, hz)] = _parse_decimal(r[2])
    return out


def _pred_vector(case, horizon):
    """Candidate predictions ordered by the oracle's held-row order."""
    pm = _prediction_map(case)
    order = ORACLES[case]["held_row_order"]
    return np.array([pm[(rid, horizon)] for rid in order])


def _close(actual, expected, atol):
    assert math.isclose(actual, expected, abs_tol=atol, rel_tol=1e-7), (
        f"actual {actual:.10g} != expected {expected:.10g} (atol {atol:g})"
    )


# --------------------------------------------------------------------------- #
# Candidate execution (unprivileged, once per isolated case).
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session", autouse=True)
def run_candidate_on_isolated_cases():
    source = Path("/app/analysis.R")
    if not source.is_file():
        for case in CASES:
            RUN_RESULTS[case] = (127, "missing /app/analysis.R")
        return
    cand_dir = CASE_ROOT / "candidate"
    cand_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
    script = cand_dir / "analysis.R"
    shutil.copyfile(source, script)
    script.chmod(0o444)

    for case in CASES:
        input_dir = CASE_ROOT / "inputs" / case
        output_dir = CASE_ROOT / "outputs" / case
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        os.chown(output_dir, 65534, 65534)
        env = {
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "HOME": "/tmp",
            "TMPDIR": "/tmp",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TZ": "Etc/UTC",
            "R_ENVIRON_USER": "/dev/null",
            "R_PROFILE_USER": "/dev/null",
            "DATA_PATH": str(input_dir / "registry.csv"),
            "CONFIG_PATH": str(input_dir / "analysis.csv"),
            "OUTPUT_PATH": str(output_dir),
        }
        try:
            completed = subprocess.run(
                [
                    "/usr/bin/setpriv",
                    "--reuid=65534",
                    "--regid=65534",
                    "--clear-groups",
                    "--no-new-privs",
                    "/usr/bin/Rscript",
                    "--vanilla",
                    str(script),
                ],
                check=False,
                cwd=input_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=600,
            )
            RUN_RESULTS[case] = (completed.returncode, completed.stdout[-4000:])
        except subprocess.TimeoutExpired as error:
            out = error.stdout or ""
            if isinstance(out, bytes):
                out = out.decode(errors="replace")
            RUN_RESULTS[case] = (124, f"timed out\n{out[-4000:]}")


# --------------------------------------------------------------------------- #
# Structural tests.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case", CASES)
def test_analysis_run_exited_successfully(case):
    """Every isolated candidate execution completed with a zero exit status."""
    rc, out = RUN_RESULTS[case]
    assert rc == 0, f"{case} exited {rc}\n{out}"


@pytest.mark.parametrize("case,filename", [(c, f) for c in CASES for f in DELIVERABLES])
def test_deliverable_exists(case, filename):
    """Each isolated run writes every required output deliverable."""
    assert _output_path(case, filename).is_file(), f"missing {case}/{filename}"


@pytest.mark.parametrize("case", CASES)
def test_estimands_schema(case):
    """estimands.csv has the required header and exactly the expected keys."""
    header, rows = _csv_output(case, "estimands.csv")
    assert list(header) == list(ESTIMAND_COLUMNS)
    keys = [r[0] for r in rows]
    assert set(keys) == set(ORACLES[case]["estimands"])
    assert len(keys) == len(ORACLES[case]["estimands"])


@pytest.mark.parametrize("case", CASES)
def test_predictions_schema(case):
    """predictions.csv covers exactly the held-out row_ids at both horizons."""
    header, rows = _csv_output(case, "predictions.csv")
    assert list(header) == list(PREDICTION_COLUMNS)
    horizons = ORACLES[case]["horizons"]
    expected = {(rid, hz) for rid in ORACLES[case]["held_ids"] for hz in horizons}
    got = {(_parse_integer(r[0]), _parse_integer(r[1])) for r in rows}
    assert got == expected
    assert len(rows) == len(expected)


# --------------------------------------------------------------------------- #
# Exact estimand block.
# --------------------------------------------------------------------------- #
def _estimand_atol(key):
    if key.startswith("cox_"):
        return BETA_ATOL
    if key == "reverse_km_median":
        return MEDIAN_ATOL
    return CIF_ATOL


@pytest.mark.parametrize(
    "case,key",
    [(c, k) for c in CASES for k in ORACLES[c]["estimands"]],
)
def test_estimand_value(case, key):
    """One reduced exact estimator matches the independent oracle."""
    table = _estimand_table(case)
    assert key in table, f"missing estimand {key}"
    _close(
        _parse_decimal(table[key]), ORACLES[case]["estimands"][key], _estimand_atol(key)
    )


@pytest.mark.parametrize("case", CASES)
def test_prediction_spec_schema(case):
    """The two cause-specific prediction specifications have the exact schema."""
    spec = _prediction_spec(case)
    assert list(spec) == ["PCM", "DEATH"]
    assert all(row["model"] in FAMILIES for row in spec.values())
    assert all(math.isfinite(row["scale"]) for row in spec.values())


@pytest.mark.parametrize("case,cause", [(c, cause) for c in CASES for cause in CAUSES])
def test_prediction_spec_matches_validation(case, cause):
    """Each reported cause specification matches independent fold validation."""
    got = _prediction_spec(case)[cause.upper()]
    expected = ORACLES[case]["prediction_spec"][cause.upper()]
    assert got["model"] == expected["model"]
    _close(got["scale"], expected["scale"], 1e-8)


@pytest.mark.parametrize("case", CASES)
def test_cif_two_cause_bound(case):
    """Marginal PCM and death incidences are non-negative and jointly < 1."""
    est = {k: _parse_decimal(v) for k, v in _estimand_table(case).items()}
    for sname in STRATA:
        for hv in ORACLES[case]["horizons"]:
            p = est[f"aj_cif_pcm_{sname}_{hv}"]
            d = est[f"aj_cif_death_{sname}_{hv}"]
            assert p >= -CIF_ATOL and d >= -CIF_ATOL
            assert p + d <= 1.0 + CIF_ATOL


# --------------------------------------------------------------------------- #
# Cohort summary.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case", CASES)
def test_summary_schema_and_types(case):
    """cohort_summary.json exposes exactly the required integer fields."""
    summary = _summary_output(case)
    assert set(summary) == set(SUMMARY_KEYS)
    assert all(type(summary[k]) is int for k in SUMMARY_KEYS)


@pytest.mark.parametrize("case,key", [(c, k) for c in CASES for k in SUMMARY_KEYS])
def test_summary_count(case, key):
    """One cohort count exactly matches the pristine truth registry."""
    assert _summary_output(case)[key] == ORACLES[case]["summary"][key]


@pytest.mark.parametrize("case", CASES)
def test_summary_partition(case):
    """Active event-type counts partition the active cohort."""
    s = _summary_output(case)
    assert (
        s["n_pcm_active"] + s["n_death_active"] + s["n_censored_active"]
        == s["n_active"]
    )
    assert s["n_male_active"] + s["n_female_active"] == s["n_active"]


# --------------------------------------------------------------------------- #
# Predictions: range / anti-degeneracy.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case", CASES)
def test_predictions_in_range(case):
    """Every predicted PCM incidence is a probability (small drift tolerated)."""
    for (_, _), p in _prediction_map(case).items():
        assert -0.02 <= p <= 1.0, f"prediction {p} out of range"


@pytest.mark.parametrize("case,h", [(c, h) for c in CASES for h in range(2)])
def test_predictions_not_degenerate(case, h):
    """Predictions vary across patients (a constant vector is rejected)."""
    horizon = ORACLES[case]["horizons"][h]
    vec = _pred_vector(case, horizon)
    assert len(np.unique(np.round(vec, 8))) >= NUNIQUE_MIN


# --------------------------------------------------------------------------- #
# Predictions: reference-relative gates (public + hidden variants).
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case,h", [(c, h) for c in GATED_CASES for h in range(2)])
def test_prediction_brier_gate(case, h):
    """Candidate IPCW competing-risks Brier beats the reference multiplier."""
    o = ORACLES[case]
    horizon = o["horizons"][h]
    vec = _pred_vector(case, horizon)
    cand = _ipcw_brier(
        vec, o["held_etime"], o["held_event"], horizon, o["gtt"], o["ggg"]
    )
    gate = BRIER_MULT * o["ref_brier"][h]
    assert cand <= gate, f"{case} h{horizon}: Brier {cand:.5f} > gate {gate:.5f}"


@pytest.mark.parametrize("case,h", [(c, h) for c in GATED_CASES for h in range(2)])
def test_prediction_discrimination_gate(case, h):
    """Candidate cumulative/dynamic AUC clears the discrimination floor."""
    o = ORACLES[case]
    horizon = o["horizons"][h]
    vec = _pred_vector(case, horizon)
    auc = _horizon_auc(vec, o["held_etime"], o["held_event"], horizon)
    assert auc >= AUC_FLOOR[h], (
        f"{case} h{horizon}: AUC {auc:.4f} < floor {AUC_FLOOR[h]}"
    )


@pytest.mark.parametrize("case,h", [(c, h) for c in GATED_CASES for h in range(2)])
def test_prediction_calibration_gate(case, h):
    """Mean predicted incidence stays within the calibration-in-the-large band."""
    o = ORACLES[case]
    horizon = o["horizons"][h]
    vec = _pred_vector(case, horizon)
    ratio = float(np.mean(vec)) / o["obs"][h]
    assert CALIB_LO <= ratio <= CALIB_HI, (
        f"{case} h{horizon}: calibration ratio {ratio:.3f} outside "
        f"[{CALIB_LO}, {CALIB_HI}]"
    )


# --------------------------------------------------------------------------- #
# Metamorphic: tripling every observed month.
# --------------------------------------------------------------------------- #
def _scaled_key(key):
    """Map a public estimand key to its scaled-case counterpart (horizon x3)."""
    if key.startswith("aj_cif_"):
        head, h = key.rsplit("_", 1)
        return f"{head}_{int(h) * 3}"
    return key


@pytest.mark.parametrize("key", list(ORACLES["public"]["estimands"]))
def test_time_scaling_estimands(key):
    """Scaling time triples the follow-up median and leaves scale-free estimators fixed."""
    pub = {k: _parse_decimal(v) for k, v in _estimand_table("public").items()}
    sca = {k: _parse_decimal(v) for k, v in _estimand_table("scaled").items()}
    skey = _scaled_key(key)
    if key == "reverse_km_median":
        _close(sca[skey], 3 * pub[key], MEDIAN_ATOL)
    elif key.startswith("cox_"):
        _close(sca[skey], pub[key], BETA_ATOL)
    else:  # marginal AJ CIF is invariant to the time unit
        _close(sca[skey], pub[key], CIF_ATOL)


@pytest.mark.parametrize("h", range(2))
def test_time_scaling_predictions(h):
    """Held-out CIF predictions are invariant to the time unit."""
    pub_h = ORACLES["public"]["horizons"][h]
    sca_h = ORACLES["scaled"]["horizons"][h]
    pub_map = _prediction_map("public")
    sca_map = _prediction_map("scaled")
    for rid in ORACLES["public"]["held_ids"]:
        _close(sca_map[(rid, sca_h)], pub_map[(rid, pub_h)], METAMORPHIC_ATOL)
