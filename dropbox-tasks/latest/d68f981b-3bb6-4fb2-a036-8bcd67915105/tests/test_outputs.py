"""Verifier for confounder-selection-bias-amplification-instrument-ate. The agent
reports one population average treatment effect of program enrollment on the
wellbeing index. Recovering it needs both hidden three-way oscillatory
confounders reconstructed from the baseline covariates at their own frequencies,
the eight linear baselines and tenure adjusted for, the administrative
outreach count left out (conditioning on it amplifies the residual bias), and
the heterogeneous enrolled-minus-not contrast standardized over every employee.
The held-out structure lives in fixtures/scm_params.json; every negative check
recomputes the wrong estimator independently in numpy and confirms it lands
outside the accept band, and the hidden seeds regenerate fresh samples the agent
script must re-solve."""

import importlib.util
import json
import math
import os
import subprocess

import numpy as np

APP = "/app"
ANALYSIS = os.path.join(APP, "analysis.R")
ESTIMATE = os.path.join(APP, "estimate.json")
HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")

_gspec = importlib.util.spec_from_file_location(
    "generate", os.path.join(FIX, "generate.py")
)
gen = importlib.util.module_from_spec(_gspec)
_gspec.loader.exec_module(gen)

with open(os.path.join(FIX, "scm_params.json")) as _fh:
    P = json.load(_fh)

REL_TOL = float(P["rel_tol"])
NEAR = float(P["near_min_rel"])
GROSS = float(P["gross_min_rel"])
BASE = P["base_covariates"]
TRI_A = tuple(P["confounder_triple_a"])
TRI_B = tuple(P["confounder_triple_b"])
COMMITTED = P["committed"]
HIDDEN = P["hidden_instances"]

_HIDDEN_DIRS = {}
_AGENT_CACHE = {}


def _load(data_dir):
    """Read the five committed CSVs from a directory and join them on employee_id."""

    def read(name):
        with open(os.path.join(data_dir, name)) as fh:
            head = fh.readline().strip().split(",")
            rows = {}
            for line in fh:
                parts = line.strip().split(",")
                rows[parts[0]] = dict(zip(head, parts))
            return rows

    b = read("baseline_covariates.csv")
    t = read("tenure.csv")
    o = read("outreach.csv")
    e = read("enrollment.csv")
    y = read("outcome.csv")
    ids = sorted(set(b) & set(t) & set(o) & set(e) & set(y))
    d = {c: np.array([float(b[i][c]) for i in ids]) for c in BASE}
    d["tenure"] = np.array([float(t[i]["tenure_years"]) for i in ids])
    d["outreach"] = np.array([float(o[i]["outreach_contacts"]) for i in ids])
    d["A"] = np.array([float(e[i]["enrolled"]) for i in ids])
    d["Y"] = np.array([float(y[i]["wellbeing_index"]) for i in ids])
    return d


def _prod(d, tri, w):
    """Build a three-way product of sines column at frequency w."""
    return np.sin(w * d[tri[0]]) * np.sin(w * d[tri[1]]) * np.sin(w * d[tri[2]])


def _ols(cols, y):
    """Least-squares fit; return coefficients keyed by design-column name."""
    names = list(cols)
    xm = np.column_stack([np.ones(len(y))] + [cols[k] for k in names])
    beta, _, _, _ = np.linalg.lstsq(xm, y, rcond=None)
    return dict(zip(["__int__"] + names, beta))


def _fit_ate(d, extra=(), use_outreach=False, interaction=True, read_coef=False):
    """Fit an outcome model and return either the standardized ATE or the bare
    enrollment coefficient, with optional oscillatory columns and the outreach
    decoy included."""
    cols = {"A": d["A"].copy(), "tenure": d["tenure"]}
    for c in BASE:
        cols[c] = d[c]
    if use_outreach:
        cols["outreach"] = d["outreach"]
    for i, col in enumerate(extra):
        cols["osc%d" % i] = col
    if interaction:
        cols["A_x_tenure"] = d["A"] * d["tenure"]
    beta = _ols(cols, d["Y"])
    if read_coef or not interaction:
        return float(beta["A"])
    return float(beta["A"] + beta["A_x_tenure"] * d["tenure"].mean())


def _true(data_dir, inst):
    """Population ATE for a data directory: tau + tau_het times the mean tenure on disk."""
    d = _load(data_dir)
    return float(inst["tau"] + inst["tau_het"] * d["tenure"].mean())


def _correct(d, inst):
    """Standardized ATE using both true oscillatory confounders at their true frequencies."""
    ga = _prod(d, TRI_A, inst["w_a"])
    gb = _prod(d, TRI_B, inst["w_b"])
    return _fit_ate(d, extra=(ga, gb))


def _relerr(v, truth):
    """Relative absolute error against the truth."""
    return abs(v - truth) / abs(truth)


def _committed_dir():
    """Path to the committed agent-visible data directory."""
    return os.path.join(APP, "data")


def _hidden_dir(inst):
    """Generate (once) a fresh hidden-seed dataset for an instance and return its path."""
    key = inst["seed"]
    if key not in _HIDDEN_DIRS:
        import tempfile

        td = tempfile.mkdtemp(prefix="hidden_%d_" % key)
        sample = gen.draw(
            inst["seed"], P["n"], inst["tau"], inst["tau_het"], inst["w_a"], inst["w_b"]
        )
        gen.write_dataset(td, sample)
        _HIDDEN_DIRS[key] = td
    return _HIDDEN_DIRS[key]


def _run_agent(data_dir):
    """Run the agent R script against a data directory and return parsed estimate.json."""
    if data_dir in _AGENT_CACHE:
        return _AGENT_CACHE[data_dir]
    env = dict(os.environ, CAUSAL_DATA_DIR=data_dir)
    proc = subprocess.run(
        ["Rscript", ANALYSIS],
        cwd=APP,
        env=env,
        capture_output=True,
        text=True,
        timeout=1000,
    )
    assert proc.returncode == 0, proc.stderr
    with open(ESTIMATE) as fh:
        out = json.load(fh)
    _AGENT_CACHE[data_dir] = out
    return out


def _agent_estimate(data_dir):
    """The numeric estimate field from an agent run on a data directory."""
    return float(_run_agent(data_dir)["estimate"])


def test_estimate_json_written():
    """Running the agent on the committed data writes estimate.json."""
    _run_agent(_committed_dir())
    assert os.path.exists(ESTIMATE)


def test_estimate_field_present():
    """estimate.json carries a field named estimate."""
    assert "estimate" in _run_agent(_committed_dir())


def test_estimate_is_finite():
    """The reported estimate is a finite real number."""
    assert math.isfinite(_agent_estimate(_committed_dir()))


def test_estimate_is_scalar():
    """The reported estimate is a single scalar, not a list or object."""
    val = _run_agent(_committed_dir())["estimate"]
    assert isinstance(val, (int, float))


def test_committed_data_has_expected_rows():
    """The committed sample loads the configured number of employees."""
    assert len(_load(_committed_dir())["A"]) == P["n"]


def test_committed_treatment_has_overlap():
    """Both enrolled and non-enrolled employees are present in the committed sample."""
    a = _load(_committed_dir())["A"]
    assert 0.2 < a.mean() < 0.8


def test_committed_truth_is_positive():
    """The committed population ATE recomputed from disk is positive."""
    assert _true(_committed_dir(), COMMITTED) > 0


def test_committed_truth_matches_stored():
    """The truth recomputed from the committed tenure column matches the stored value."""
    assert abs(_true(_committed_dir(), COMMITTED) - COMMITTED["true_ate"]) < 1e-4


def test_agent_matches_committed_truth():
    """The agent estimate on the committed data is within tolerance of the true ATE."""
    truth = _true(_committed_dir(), COMMITTED)
    assert _relerr(_agent_estimate(_committed_dir()), truth) <= REL_TOL


def test_python_correct_recovers_committed_truth():
    """The independent two-confounder g-computation recovers the committed truth."""
    d = _load(_committed_dir())
    assert (
        _relerr(_correct(d, COMMITTED), _true(_committed_dir(), COMMITTED)) <= REL_TOL
    )


def test_agent_close_to_python_correct():
    """The agent estimate agrees with the independent correct estimator on committed data."""
    d = _load(_committed_dir())
    assert abs(_agent_estimate(_committed_dir()) - _correct(d, COMMITTED)) <= 0.1


def test_unadjusted_difference_fails():
    """The raw enrolled-minus-not mean difference is grossly confounded."""
    d = _load(_committed_dir())
    est = d["Y"][d["A"] == 1].mean() - d["Y"][d["A"] == 0].mean()
    assert _relerr(est, _true(_committed_dir(), COMMITTED)) > GROSS


def test_linear_adjustment_no_oscillation_fails():
    """Adjusting linearly for every baseline but neither oscillatory term fails grossly."""
    d = _load(_committed_dir())
    est = _fit_ate(d, extra=())
    assert _relerr(est, _true(_committed_dir(), COMMITTED)) > GROSS


def test_linear_plus_outreach_fails():
    """Throwing every predictor including the outreach count into a linear model fails."""
    d = _load(_committed_dir())
    est = _fit_ate(d, extra=(), use_outreach=True)
    assert _relerr(est, _true(_committed_dir(), COMMITTED)) > GROSS


def test_only_first_confounder_fails():
    """Reconstructing only the diet-sleep-stress term and stopping leaves the other confounder."""
    d = _load(_committed_dir())
    ga = _prod(d, TRI_A, COMMITTED["w_a"])
    est = _fit_ate(d, extra=(ga,))
    assert _relerr(est, _true(_committed_dir(), COMMITTED)) > GROSS


def test_only_second_confounder_fails():
    """Reconstructing only the activity-chronic-income term and stopping leaves the other confounder."""
    d = _load(_committed_dir())
    gb = _prod(d, TRI_B, COMMITTED["w_b"])
    est = _fit_ate(d, extra=(gb,))
    assert _relerr(est, _true(_committed_dir(), COMMITTED)) > GROSS


def test_outreach_inclusion_amplifies_bias():
    """Adding the outreach count to a mis-specified linear model amplifies the bias."""
    d = _load(_committed_dir())
    truth = _true(_committed_dir(), COMMITTED)
    without = _relerr(_fit_ate(d, extra=()), truth)
    with_z = _relerr(_fit_ate(d, extra=(), use_outreach=True), truth)
    assert with_z > without


def test_single_confounder_plus_outreach_still_fails():
    """A half reconstruction that also conditions on outreach stays outside tolerance."""
    d = _load(_committed_dir())
    ga = _prod(d, TRI_A, COMMITTED["w_a"])
    est = _fit_ate(d, extra=(ga,), use_outreach=True)
    assert _relerr(est, _true(_committed_dir(), COMMITTED)) > GROSS


def test_coefficient_read_fails():
    """Reading the bare enrollment coefficient from the interaction model misses the heterogeneity."""
    d = _load(_committed_dir())
    ga = _prod(d, TRI_A, COMMITTED["w_a"])
    gb = _prod(d, TRI_B, COMMITTED["w_b"])
    est = _fit_ate(d, extra=(ga, gb), read_coef=True)
    assert _relerr(est, _true(_committed_dir(), COMMITTED)) > NEAR


def test_wrong_frequency_confounders_fail():
    """Using the right covariate triples but the wrong frequency leaves residual confounding."""
    d = _load(_committed_dir())
    ga = _prod(d, TRI_A, COMMITTED["w_a"] + 0.6)
    gb = _prod(d, TRI_B, COMMITTED["w_b"] + 0.6)
    est = _fit_ate(d, extra=(ga, gb))
    assert _relerr(est, _true(_committed_dir(), COMMITTED)) > GROSS


def test_pairwise_interaction_expansion_fails():
    """A linear model with all pairwise covariate products cannot span the three-way terms."""
    d = _load(_committed_dir())
    extra = []
    for i in range(len(BASE)):
        for j in range(i + 1, len(BASE)):
            extra.append(d[BASE[i]] * d[BASE[j]])
    est = _fit_ate(d, extra=tuple(extra))
    assert _relerr(est, _true(_committed_dir(), COMMITTED)) > GROSS


def test_quadratic_expansion_fails():
    """A linear model with squared covariates misses the oscillatory structure."""
    d = _load(_committed_dir())
    extra = tuple(d[c] ** 2 for c in BASE)
    est = _fit_ate(d, extra=extra)
    assert _relerr(est, _true(_committed_dir(), COMMITTED)) > GROSS


def test_wrong_triple_confounders_fail():
    """Oscillatory terms on the wrong covariate triples do not remove the confounding."""
    d = _load(_committed_dir())
    ga = _prod(d, ("age_index", "bmi_index", "income_index"), COMMITTED["w_a"])
    gb = _prod(d, ("age_index", "bmi_index", "activity_index"), COMMITTED["w_b"])
    est = _fit_ate(d, extra=(ga, gb))
    assert _relerr(est, _true(_committed_dir(), COMMITTED)) > GROSS


def test_agent_beats_unadjusted():
    """The agent estimate is far closer to the truth than the unadjusted difference."""
    d = _load(_committed_dir())
    truth = _true(_committed_dir(), COMMITTED)
    unadj = d["Y"][d["A"] == 1].mean() - d["Y"][d["A"] == 0].mean()
    assert _relerr(_agent_estimate(_committed_dir()), truth) < _relerr(unadj, truth)


def test_agent_beats_linear_no_oscillation():
    """The agent estimate is far closer to the truth than a linear adjustment without oscillation."""
    d = _load(_committed_dir())
    truth = _true(_committed_dir(), COMMITTED)
    lin = _fit_ate(d, extra=())
    assert _relerr(_agent_estimate(_committed_dir()), truth) < _relerr(lin, truth)


def test_correct_much_better_than_single_confounder():
    """The two-confounder estimator beats either single-confounder estimator by a wide margin."""
    d = _load(_committed_dir())
    truth = _true(_committed_dir(), COMMITTED)
    ga = _prod(d, TRI_A, COMMITTED["w_a"])
    one = _relerr(_fit_ate(d, extra=(ga,)), truth)
    both = _relerr(_correct(d, COMMITTED), truth)
    assert one - both > 0.3


def test_correct_on_first_half_subsample():
    """The correct estimator stays near the subsample truth on the first half of the committed data."""
    d = _load(_committed_dir())
    half = {k: v[: P["n"] // 2] for k, v in d.items()}
    ga = _prod(half, TRI_A, COMMITTED["w_a"])
    gb = _prod(half, TRI_B, COMMITTED["w_b"])
    est = _fit_ate(half, extra=(ga, gb))
    truth = COMMITTED["tau"] + COMMITTED["tau_het"] * half["tenure"].mean()
    assert _relerr(est, truth) <= 0.15


def test_correct_on_second_half_subsample():
    """The correct estimator stays near the subsample truth on the second half of the committed data."""
    d = _load(_committed_dir())
    half = {k: v[P["n"] // 2 :] for k, v in d.items()}
    ga = _prod(half, TRI_A, COMMITTED["w_a"])
    gb = _prod(half, TRI_B, COMMITTED["w_b"])
    est = _fit_ate(half, extra=(ga, gb))
    truth = COMMITTED["tau"] + COMMITTED["tau_het"] * half["tenure"].mean()
    assert _relerr(est, truth) <= 0.15


def test_hidden_instance_1_matches_truth():
    """The agent re-solves a fresh hidden sample (instance 1) within tolerance."""
    inst = HIDDEN[0]
    d = _hidden_dir(inst)
    assert _relerr(_agent_estimate(d), _true(d, inst)) <= REL_TOL


def test_hidden_instance_2_matches_truth():
    """The agent re-solves a fresh hidden sample (instance 2) within tolerance."""
    inst = HIDDEN[1]
    d = _hidden_dir(inst)
    assert _relerr(_agent_estimate(d), _true(d, inst)) <= REL_TOL


def test_hidden_instance_3_matches_truth():
    """The agent re-solves a fresh hidden sample (instance 3) within tolerance."""
    inst = HIDDEN[2]
    d = _hidden_dir(inst)
    assert _relerr(_agent_estimate(d), _true(d, inst)) <= REL_TOL


def test_hidden_instance_4_matches_truth():
    """The agent re-solves a fresh hidden sample (instance 4) within tolerance."""
    inst = HIDDEN[3]
    d = _hidden_dir(inst)
    assert _relerr(_agent_estimate(d), _true(d, inst)) <= REL_TOL


def test_hidden_instance_5_matches_truth():
    """The agent re-solves a fresh hidden sample (instance 5) within tolerance."""
    inst = HIDDEN[4]
    d = _hidden_dir(inst)
    assert _relerr(_agent_estimate(d), _true(d, inst)) <= REL_TOL


def test_hidden_instance_6_matches_truth():
    """The agent re-solves a fresh hidden sample (instance 6) within tolerance."""
    inst = HIDDEN[5]
    d = _hidden_dir(inst)
    assert _relerr(_agent_estimate(d), _true(d, inst)) <= REL_TOL


def test_python_correct_recovers_hidden_1():
    """The independent estimator recovers the truth on hidden instance 1."""
    inst = HIDDEN[0]
    d = _hidden_dir(inst)
    assert _relerr(_correct(_load(d), inst), _true(d, inst)) <= REL_TOL


def test_python_correct_recovers_hidden_4():
    """The independent estimator recovers the truth on hidden instance 4."""
    inst = HIDDEN[3]
    d = _hidden_dir(inst)
    assert _relerr(_correct(_load(d), inst), _true(d, inst)) <= REL_TOL


def test_linear_fails_on_hidden_2():
    """A linear no-oscillation adjustment is grossly biased on hidden instance 2."""
    inst = HIDDEN[1]
    d = _hidden_dir(inst)
    est = _fit_ate(_load(d), extra=())
    assert _relerr(est, _true(d, inst)) > GROSS


def test_single_confounder_fails_on_hidden_5():
    """Reconstructing only one oscillatory term is biased on hidden instance 5."""
    inst = HIDDEN[4]
    d = _hidden_dir(inst)
    ld = _load(d)
    est = _fit_ate(ld, extra=(_prod(ld, TRI_A, inst["w_a"]),))
    assert _relerr(est, _true(d, inst)) > GROSS


def test_hidden_estimates_vary():
    """The agent's estimates differ across hidden instances, so a constant cannot pass."""
    vals = [_agent_estimate(_hidden_dir(inst)) for inst in HIDDEN[:3]]
    assert max(vals) - min(vals) > 1e-2


def test_hidden_differs_from_committed():
    """The agent's committed and hidden estimates differ, ruling out a memorized number."""
    c = _agent_estimate(_committed_dir())
    h = _agent_estimate(_hidden_dir(HIDDEN[0]))
    assert abs(c - h) > 1e-2


def test_committed_constant_fails_a_hidden_instance():
    """The committed truth used as a constant guess fails at least one hidden instance."""
    const = COMMITTED["true_ate"]
    fails = [_relerr(const, _true(_hidden_dir(i), i)) > REL_TOL for i in HIDDEN]
    assert any(fails)


def test_no_forbidden_tests_path():
    """The agent script does not reach into the verifier tree."""
    src = open(ANALYSIS).read()
    assert "/tests" not in src


def test_no_forbidden_fixtures():
    """The agent script does not read the held-back fixtures."""
    assert "fixtures" not in open(ANALYSIS).read()


def test_no_forbidden_scm_params():
    """The agent script does not read the structural parameter file."""
    assert "scm_params" not in open(ANALYSIS).read()


def test_agent_does_not_hardcode_committed_truth():
    """The committed true-effect literal does not appear in the agent script."""
    assert "1.240451" not in open(ANALYSIS).read()
