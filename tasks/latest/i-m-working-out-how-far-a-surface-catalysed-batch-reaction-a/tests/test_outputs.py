"""Checks each run's reported product conversion at t=5 against the true value
from the kinetic process that generated the count trajectories.

Each run is observed only as noisy count trajectories of the on-surface species
-- adsorbed, activated, product, decomposed -- sampled over time. Three biases
stack against any direct read of the tables: decomposition is a genuine
competing pathway that removes molecules for good; reactant desorption is
informative because the activated intermediate speeds up both conversion and
desorption, so the molecules that leave are disproportionately the ones about
to convert; and product itself desorbs out of the field of view, so the
observed product count is only the on-surface remnant, not the cumulative
number converted. On top of that the activation is reversible -- the activated
form can relax back to the ground adsorbed state -- so the two on-surface
reactant states form a genuinely coupled linear system rather than a one-way
cascade. Recovering the true conversion of the whole starting population means
fitting that coupled reversible two-state model (each state with its own
conversion, decomposition, desorption rate plus the forward and back
activation rates) together with a product desorption channel, then re-solving
with the reactant desorption channels removed and evaluating the loss-free
conversion at t=5. That fit recovers the truth to within about a hundredth and
a half. Reading the observed on-patch product fraction is low by 0.35 to 0.45;
the eventual on-patch product fraction is even lower once more product has
left; treating n_product as cumulative (no product desorption) wrecks the rate
fit; and a one-way (irreversible) cascade approximation, though it still fits
the reactant trajectories passably, overstates the loss-free conversion by
about 0.05 to 0.08. The tolerance passes the correct reconstruction while
failing every one of those shortcuts, and the shipped count tables must be
left untouched.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REACTOR = Path("/app/reactor")
HARNESS = Path("/tests/harness")

EXPECTED = {
    "run1": 0.5457,
    "run2": 0.6659,
    "run3": 0.4379,
    "run4": 0.7001,
    "run5": 0.5217,
}
TOL = 0.02


def test_inputs_unchanged():
    """Every run's count table must be left exactly as shipped."""
    for run in EXPECTED:
        exp = (HARNESS / f"{run}.sha256").read_text(encoding="utf-8").strip().split()[0]
        got = hashlib.sha256((REACTOR / run / "counts.csv").read_bytes()).hexdigest()
        assert got == exp, f"{run}/counts.csv must not be modified"


def test_outputs_present():
    """Every run folder has a conversion.txt holding a single number."""
    for run in EXPECTED:
        ans = REACTOR / run / "conversion.txt"
        assert ans.is_file(), f"missing {ans}"
        float(ans.read_text(encoding="utf-8").strip())


def test_conversion():
    """Every run's product conversion at t=5 matches the true value."""
    for run, expected in EXPECTED.items():
        got = float((REACTOR / run / "conversion.txt").read_text(encoding="utf-8").strip())
        assert abs(got - expected) <= TOL, (
            f"{run}: conversion {got} not within {TOL} of {expected}"
        )
