# Coarse-grained folding landscape and hopping kinetics

This note fixes the model and the estimator that the group agreed on. It defines
what the numbers mean, not how to compute them.

## 1. Landscape

A single collective coordinate x (nanometres) runs from the collapsed native
basin at negative x to the extended unfolded basin at positive x. The
free-energy profile at zero force, in units of kT, is

    U0(x) = c4*x^4 - c2*x^2 + c1*x + cs*exp(-(x - xd)^2 / (2*wd^2))

The quartic pair gives the two basins and the barrier between them. The linear
term c1 biases the native state. The Gaussian is the desolvation feature that
sits near the transition region: cs > 0 is a desolvation barrier, cs < 0 an
intermediate well, cs = 0 no feature at all. Its sign is not constrained.

A pulling force F (piconewtons) tilts the profile,

    U_F(x) = U0(x) - F*x/kT

with kT in piconewton nanometres.

Of the landscape constants, c4, c1, xd, wd and kT are known for this construct
and are stored with the study. The barrier scale c2 and the desolvation
amplitude cs are not known and have to be recovered.

## 2. Hopping rates

Transitions are diffusive crossings of the barrier at diffusion coefficient
D = exp(logD), with logD also unknown. The mean first passage time for
unfolding is taken from the native side, reflecting at xlo and absorbing at xau:

    tau_u(F) = (1/D) * INT[xlo..xau] dy exp(U_F(y)) * INT[xlo..y] dz exp(-U_F(z))

and for folding from the unfolded side, reflecting at xhi and absorbing at xaf:

    tau_f(F) = (1/D) * INT[xaf..xhi] dy exp(U_F(y)) * INT[y..xhi] dz exp(-U_F(z))

The rates are k_u(F) = 1/tau_u(F) and k_f(F) = 1/tau_f(F). The four boundaries
xlo, xau, xaf and xhi are fixed constants of the study. Both integrands are
smooth on their intervals; evaluate the integrals to a relative accuracy of
1e-6 or better.

## 3. What was measured

Each molecule m is held at several clamp forces. At every force its hopping
trace yields one unfolding log-rate and one folding log-rate. Two things vary
from molecule to molecule and are not observed:

  - a_m, a shift of the attempt frequency for that molecule (bead and linker
    geometry), which moves both log-rates together;
  - b_m, an error in that molecule's force calibration, so the force it really
    felt at nominal setting F was F*exp(b_m).

With those, the measurement model at nominal force F_mj is

    y_u(m,j) = a_m + log k_u(F_mj*exp(b_m)) + e
    y_f(m,j) = a_m + log k_f(F_mj*exp(b_m)) + e

where a_m ~ Normal(0, sigma_a^2), b_m ~ Normal(0, sigma_b^2) and each
measurement error e ~ Normal(0, sigma_e^2), all independent of one another.

The six unknowns are

    theta = (c2, cs, logD, sigma_a, sigma_b, sigma_e)

## 4. The estimator

Write u for the whole nuisance vector (a_1, b_1, ..., a_M, b_M) and let
J(theta, u) be the negative log of the joint density of the observations and u,

    J(theta, u) = SUM over observations [ r^2/(2*sigma_e^2) + log(sigma_e)
                                          + 0.5*log(2*pi) ]
                + SUM over molecules [ a_m^2/(2*sigma_a^2) + log(sigma_a)
                                       + b_m^2/(2*sigma_b^2) + log(sigma_b)
                                       + log(2*pi) ]

where r is the residual of the corresponding line of section 3.

a_m and b_m are random effects, not free parameters: they are integrated out
rather than fitted. The integral is defined by Laplace's method taken at the
conditional mode of the whole nuisance block,

    u*(theta) = argmin over u of J(theta, u)
    H(theta)  = the second derivative matrix of J with respect to u at u*
    F(theta)  = J(theta, u*) + 0.5*log(det H) - M*log(2*pi)

H is the exact second derivative matrix, not a curvature surrogate. J is
separable across molecules, so H is block diagonal in the M pairs (a_m, b_m)
and its determinant is the product of those 2 by 2 blocks.

The reported parameters are theta* = argmin F(theta), and neg_log_marg is
F(theta*). F has a single interior minimum over the region of interest.
Converge theta* to a relative accuracy of 1e-6 or better in every coordinate.

## 5. Uncertainty and the desolvation test

Standard errors come from the curvature of the same marginal objective. Let
Hth be the second derivative matrix of F with respect to the six parameters in
their natural units, evaluated at theta*. The standard error of a parameter is
the square root of its diagonal entry in the inverse of Hth. No residual
rescaling is applied. Standard errors are reported for c2, cs and logD.

Whether the desolvation feature is there at all is settled by the likelihood
ratio, not by the standard error. Refit with cs held at zero, the other five
parameters free, and report the deviance

    dev_cs = 2*(min over theta with cs = 0 of F(theta) - F(theta*))

## 6. Derived quantities

Two numbers are wanted at theta*, both for the population landscape, that is
with a and b set to zero:

  - f_half, the coexistence force, the F at which k_u(F) = k_f(F). It is unique
    and lies between 0.05 and 30 piconewtons.
  - log_k_fold_zero, the natural log of the folding rate at zero force, the
    quantity the force experiment cannot reach directly.

## 7. Study schema

A study is one SQLite file.

    config(c4, c1, xd, wd, kt, xlo, xhi, xau, xaf,
           init_c2, init_cs, init_log_d,
           init_sigma_a, init_sigma_b, init_sigma_e)

One row. The landscape constants of section 1, the four boundaries of section
2, and a rough starting guess for each of the six unknowns. The starting guess
is a guess only; it is not the answer and is not close enough to report.

    molecules(id)

One row per molecule, id ascending from 1.

    observations(molecule_id, force_pn, log_k_unfold, log_k_fold)

One row per molecule and clamp force. force_pn is the nominal setting F_mj,
not the force the molecule felt. log_k_unfold and log_k_fold are y_u and y_f.
