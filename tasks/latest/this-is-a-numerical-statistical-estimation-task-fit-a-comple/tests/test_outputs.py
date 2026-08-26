"""Deterministic verifier for climate-crashes-cloglog, recomputed from the raw crash data."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import chi2, norm

DATA = Path("/app/data")
OUT = Path("/app/outputs")


def _irls_cloglog(x, y, iters=300):
    b = np.zeros(x.shape[1])
    for _ in range(iters):
        eta = np.clip(x @ b, -30, 30)
        mu = np.clip(1 - np.exp(-np.exp(eta)), 1e-12, 1 - 1e-12)
        dmu = np.exp(eta - np.exp(eta))
        w = dmu**2 / (mu * (1 - mu))
        z = eta + (y - mu) / dmu
        xtw = x.T * w
        nb = np.linalg.solve(xtw @ x, xtw @ z)
        if np.max(np.abs(nb - b)) < 1e-11:
            b = nb
            break
        b = nb
    eta = x @ b
    mu = np.clip(1 - np.exp(-np.exp(eta)), 1e-12, 1 - 1e-12)
    dmu = np.exp(eta - np.exp(eta))
    w = dmu**2 / (mu * (1 - mu))
    cov = np.linalg.inv((x.T * w) @ x)
    se = np.sqrt(np.diag(cov))
    dev = -2 * np.sum(y * np.log(mu) + (1 - y) * np.log(1 - mu))
    aic = dev + 2 * x.shape[1]
    return b, dev, aic, mu, se, dmu


def _fit_coef(x, y, iters=200):
    """Fitted cloglog coefficients only (used inside the permutation loop)."""
    b = np.zeros(x.shape[1])
    for _ in range(iters):
        eta = np.clip(x @ b, -30, 30)
        mu = np.clip(1 - np.exp(-np.exp(eta)), 1e-12, 1 - 1e-12)
        dmu = np.exp(eta - np.exp(eta))
        w = dmu**2 / (mu * (1 - mu))
        z = eta + (y - mu) / dmu
        xtw = x.T * w
        nb = np.linalg.solve(xtw @ x, xtw @ z)
        if np.max(np.abs(nb - b)) < 1e-10:
            b = nb
            break
        b = nb
    return b


@pytest.fixture(scope="module")
def ref():
    dat = pd.read_csv(DATA / "climate_crashes.csv")
    preds = [c for c in dat.columns if c != "failure"]
    x = np.column_stack([np.ones(len(dat)), dat[preds].to_numpy(float)])
    y = dat["failure"].to_numpy(float)
    b, dev, aic, mu, se, dens = _irls_cloglog(x, y)
    mu0 = y.mean()
    nulldev = -2 * np.sum(y * np.log(mu0) + (1 - y) * np.log(1 - mu0))
    names = ["(Intercept)"] + preds

    zval = b / se
    pval = 2 * norm.cdf(-np.abs(zval))
    lr_stat = float(nulldev - dev)
    lr_df = len(preds)
    lr_p = float(chi2.sf(lr_stat, lr_df))
    # Average marginal effect per predictor: beta_k * mean(density), density =
    # exp(eta - exp(eta)) for the cloglog link. b[0] is the intercept.
    mean_dens = float(dens.mean())
    ame = {p: float(b[i + 1] * mean_dens) for i, p in enumerate(preds)}

    # Permutation inference: refit under the committed failure-label reorderings and
    # build the null distribution of the largest predictor coefficient magnitude.
    perm = pd.read_csv(DATA / "permutation_index.csv").to_numpy(int) - 1
    perm_b = len(perm)
    obs_max_abs_coef = float(np.abs(b[1:]).max())
    perm_stats = np.array(
        [np.abs(_fit_coef(x, y[perm[k]])[1:]).max() for k in range(perm_b)]
    )
    perm_q95 = float(np.quantile(perm_stats, 0.95))

    return {
        "names": names,
        "preds": preds,
        "perm_B": perm_b,
        "obs_max_abs_coef": obs_max_abs_coef,
        "perm_q95": perm_q95,
        "coef": dict(zip(names, b)),
        "se": dict(zip(names, se)),
        "z": dict(zip(names, zval)),
        "pval": dict(zip(names, pval)),
        "lr_stat": lr_stat,
        "lr_df": lr_df,
        "lr_p": lr_p,
        "ame": ame,
        "dev": float(dev),
        "aic": float(aic),
        "nulldev": float(nulldev),
        "mu": mu,
        "n_events": int(y.sum()),
    }


@pytest.fixture(scope="module")
def model():
    return json.loads((OUT / "cloglog_model.json").read_text())


@pytest.fixture(scope="module")
def fitted():
    return pd.read_csv(OUT / "fitted.csv")


class TestGuards:
    def test_all_artifacts_exist(self):
        """Both output artifacts were written."""
        for name in ("cloglog_model.json", "fitted.csv"):
            assert (OUT / name).exists(), f"missing output {name}"

    def test_model_schema(self, model):
        """cloglog_model.json carries the pinned top-level keys."""
        for key in (
            "n_obs",
            "n_events",
            "coefficients",
            "null_deviance",
            "deviance",
            "aic",
            "lr_statistic",
            "lr_df",
            "lr_pvalue",
            "average_marginal_effects",
            "permutation_test",
        ):
            assert key in model, f"cloglog_model.json missing key {key}"


class TestReestimation:
    def test_n_events(self, model, ref):
        """The reported event count matches the number of crashes."""
        assert model["n_events"] == ref["n_events"], (
            f"n_events={model['n_events']} disagrees with re-estimate {ref['n_events']}"
        )

    def test_deviance(self, model, ref):
        """The residual deviance matches the cloglog re-estimate."""
        assert abs(model["deviance"] - ref["dev"]) < 0.1, (
            f"deviance={model['deviance']} disagrees with re-estimate {ref['dev']:.4f}"
        )

    def test_null_deviance(self, model, ref):
        """The null deviance matches the intercept-only re-estimate."""
        assert abs(model["null_deviance"] - ref["nulldev"]) < 0.1, (
            f"null_deviance={model['null_deviance']} disagrees with re-estimate {ref['nulldev']:.4f}"
        )

    def test_aic(self, model, ref):
        """The AIC matches the cloglog re-estimate."""
        assert abs(model["aic"] - ref["aic"]) < 0.1, (
            f"aic={model['aic']} disagrees with re-estimate {ref['aic']:.4f}"
        )

    def test_coefficients(self, model, ref):
        """The coefficients match the cloglog re-estimate within a near-separation tolerance."""
        got = model["coefficients"]
        assert set(got) == set(ref["names"]), "coefficient name set disagrees"
        for n in ref["names"]:
            tol = max(0.5, 0.05 * abs(ref["coef"][n]))
            assert abs(got[n]["estimate"] - ref["coef"][n]) < tol, (
                f"coefficient {n}={got[n]['estimate']} disagrees with re-estimate "
                f"{ref['coef'][n]:.6f}"
            )

    def test_standard_errors(self, model, ref):
        """Each coefficient standard error matches the re-estimated observed
        information, so a fabricated SE or one from the wrong link disagrees."""
        got = model["coefficients"]
        for n in ref["names"]:
            assert abs(got[n]["std_error"] - ref["se"][n]) < 0.05, (
                f"std_error {n}={got[n]['std_error']} disagrees with re-estimate "
                f"{ref['se'][n]:.6f}"
            )

    def test_wald_statistics(self, model, ref):
        """Each Wald z and its two-sided p-value match the re-estimate."""
        got = model["coefficients"]
        for n in ref["names"]:
            assert abs(got[n]["z_value"] - ref["z"][n]) < 0.1, (
                f"z_value {n}={got[n]['z_value']} disagrees with {ref['z'][n]:.6f}"
            )
            assert abs(got[n]["p_value"] - ref["pval"][n]) < 0.001, (
                f"p_value {n}={got[n]['p_value']} disagrees with {ref['pval'][n]:.8f}"
            )

    def test_likelihood_ratio_test(self, model, ref):
        """The likelihood-ratio statistic, degrees of freedom and p-value match the
        re-estimate against the intercept-only null."""
        assert abs(model["lr_statistic"] - ref["lr_stat"]) < 0.1, (
            f"lr_statistic={model['lr_statistic']} disagrees with {ref['lr_stat']:.4f}"
        )
        assert model["lr_df"] == ref["lr_df"], "lr_df disagrees"
        assert abs(model["lr_pvalue"] - ref["lr_p"]) < 0.001, (
            f"lr_pvalue={model['lr_pvalue']} disagrees with {ref['lr_p']:.8f}"
        )

    def test_average_marginal_effects(self, model, ref):
        """The average marginal effects match the re-estimate. Each is beta times the
        mean cloglog density; a coefficient, a logit-link derivative, or an at-means
        effect disagrees."""
        got = model["average_marginal_effects"]
        assert set(got) == set(ref["preds"]), (
            "average_marginal_effects predictor set disagrees"
        )
        for p in ref["preds"]:
            assert abs(got[p] - ref["ame"][p]) < 0.0005, (
                f"average marginal effect {p}={got[p]} disagrees with re-estimate "
                f"{ref['ame'][p]:.8f}"
            )

    def test_fitted_probs(self, fitted, ref):
        """The fitted failure probabilities match the cloglog re-estimate."""
        got = fitted.sort_values("row_id")["fitted_prob"].to_numpy(float)
        assert len(got) == len(ref["mu"]), "fitted row count disagrees"
        assert np.all(np.abs(got - ref["mu"]) < 0.02), (
            "fitted probabilities disagree with re-estimate"
        )


class TestPermutation:
    def test_permutation_structure(self, model, ref):
        """The permutation block reports the committed permutation count and an
        observed statistic equal to the largest predictor coefficient magnitude."""
        pt = model["permutation_test"]
        for key in ("n_permutations", "observed_max_abs_coef", "null_q95_max_abs_coef"):
            assert key in pt, f"permutation_test missing key {key}"
        assert int(pt["n_permutations"]) == ref["perm_B"], (
            f"n_permutations={pt['n_permutations']} disagrees with {ref['perm_B']}"
        )
        assert (
            abs(float(pt["observed_max_abs_coef"]) - ref["obs_max_abs_coef"]) < 0.05
        ), "observed_max_abs_coef is not the largest predictor coefficient magnitude"

    def test_permutation_null_q95(self, model, ref):
        """The 95th percentile of the permutation null distribution of the largest
        predictor coefficient magnitude matches the re-estimate. This quantity has no
        closed-form shortcut, so it can only be produced by actually refitting the
        model under the committed label reorderings."""
        got = float(model["permutation_test"]["null_q95_max_abs_coef"])
        assert abs(got - ref["perm_q95"]) < 0.1, (
            f"null_q95_max_abs_coef={got} disagrees with re-estimate {ref['perm_q95']:.6f}"
        )


class TestAntiCheat:
    def test_fitted_in_unit_interval(self, fitted):
        """Fitted probabilities lie within the unit interval."""
        v = fitted["fitted_prob"].to_numpy(float)
        assert np.all((v >= 0) & (v <= 1)), "fitted probabilities fall outside [0, 1]"

    def test_fitted_not_constant(self, fitted):
        """Fitted probabilities are not a degenerate constant."""
        assert fitted["fitted_prob"].std() > 1e-3, (
            "fitted probabilities are near-constant"
        )

    def test_deviance_nontrivial(self, model):
        """The residual deviance reflects a genuine finite fit, not a separation collapse."""
        assert model["deviance"] > 1.0, "deviance is implausibly small"

    def test_deviance_below_null(self, model):
        """The residual deviance is below the null deviance."""
        assert model["deviance"] < model["null_deviance"], (
            "deviance is not below the null deviance"
        )
