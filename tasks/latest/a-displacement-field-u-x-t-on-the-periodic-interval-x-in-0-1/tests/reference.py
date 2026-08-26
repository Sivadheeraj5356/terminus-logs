"""Independent closed-form reference for the periodic damped wave (telegraph).

The agent implements a finite-difference solver from scratch for

    u_tt + 2 g u_t = c^2 u_xx,   x in [0, 1),   u_t(x, 0) = 0,

with periodic boundaries, wave speed c, and damping rate g. This module supplies
a genuinely independent reference that uses no time integrator at all: it
evaluates the exact solution mode by mode. For an initial displacement that is a
sum of sinusoids, each Fourier mode evolves as a damped harmonic oscillator with
its own frequency, and the constant part is preserved. No matrix product, no FFT,
no time stepping is involved, so the reference shares no code path with any
marching stencil.

For a single mode of wavenumber k >= 1 released from rest,

    W_k = sqrt((2 pi k c)^2 - g^2)   (underdamped: (2 pi k c)^2 > g^2)
    T(t)  = exp(-g t) [cos(W_k t) + (g / W_k) sin(W_k t)]
    T'(t) = -exp(-g t) sin(W_k t) (2 pi k c)^2 / W_k

so the spatial mode sin(2 pi k x + p) contributes T(t) to the displacement and
T'(t) to the velocity. The constant (k = 0) part stays constant with zero
velocity.
"""

import math

import numpy as np


def grid(N):
    """The pinned periodic grid x_i = i/N for i = 0 .. N-1."""
    return np.arange(N, dtype=float) / N


def eval_profile(prof, x):
    """Evaluate the initial displacement profile u0 at coordinates x."""
    x = np.asarray(x, dtype=float)
    if prof["kind"] == "gaussian":
        d = x - float(prof["center"])
        d = d - np.round(d)  # nearest periodic image on the unit circle
        w = float(prof["width"])
        return np.exp(-((d / w) ** 2))
    if prof["kind"] == "sinsum":
        v = np.full_like(x, float(prof["c0"]))
        for a, k, p in zip(prof["amps"], prof["waves"], prof["phases"]):
            v = v + float(a) * np.sin(2.0 * np.pi * float(k) * x + float(p))
        return v
    raise ValueError("unknown profile kind: " + repr(prof.get("kind")))


def initial_field(prof, N):
    """Sample the initial displacement onto the grid: shape (N,)."""
    return eval_profile(prof, grid(N))


def _omega(k, c, g):
    val = (2.0 * math.pi * k * c) ** 2 - g * g
    if val <= 0.0:
        raise ValueError("mode k=%r is not underdamped for c=%r g=%r" % (k, c, g))
    return math.sqrt(val)


def analytic_solution(prof, c, g, x, t):
    """Exact displacement u(x, t); returns shape (len(x),).

    Defined for sinsum profiles: each sinusoid is an exact eigenmode of the PDE.
    """
    if prof["kind"] != "sinsum":
        raise ValueError("closed-form reference is defined for sinsum profiles")
    x = np.asarray(x, dtype=float)
    u = np.full_like(x, float(prof["c0"]))  # constant (DC) part is time-invariant
    for a, k, p in zip(prof["amps"], prof["waves"], prof["phases"]):
        a, k, p = float(a), float(k), float(p)
        if k == 0.0:
            u = u + a * math.sin(p) * np.ones_like(x)
            continue
        W = _omega(k, c, g)
        env = math.exp(-g * t) * (math.cos(W * t) + (g / W) * math.sin(W * t))
        u = u + a * env * np.sin(2.0 * np.pi * k * x + p)
    return u


def analytic_velocity(prof, c, g, x, t):
    """Exact velocity u_t(x, t); returns shape (len(x),)."""
    if prof["kind"] != "sinsum":
        raise ValueError("closed-form reference is defined for sinsum profiles")
    x = np.asarray(x, dtype=float)
    v = np.zeros_like(x)
    for a, k, p in zip(prof["amps"], prof["waves"], prof["phases"]):
        a, k, p = float(a), float(k), float(p)
        if k == 0.0:
            continue
        W = _omega(k, c, g)
        fprime = -math.exp(-g * t) * math.sin(W * t) * (2.0 * math.pi * k * c) ** 2 / W
        v = v + a * fprime * np.sin(2.0 * np.pi * k * x + p)
    return v


def discrete_energy(u, v, c, N):
    """Discrete energy 0.5 |v|^2 + 0.5 c^2 |u_x|^2 with a centered second-order u_x.

    Uses only the emitted displacement and velocity on the grid; independent of
    any scheme. For a dissipative solver this is non-increasing across snapshots.
    """
    u = np.asarray(u, dtype=float)
    v = np.asarray(v, dtype=float)
    dx = 1.0 / N
    ux = (np.roll(u, -1) - np.roll(u, 1)) / (2.0 * dx)
    return float(np.sum(0.5 * v * v + 0.5 * c * c * ux * ux) * dx)
