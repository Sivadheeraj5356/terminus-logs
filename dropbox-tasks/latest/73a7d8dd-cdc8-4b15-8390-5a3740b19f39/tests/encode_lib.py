import os
import subprocess
import tempfile

import numpy as np

from qasm_state import (
    cx_count,
    only_allowed,
    parse,
    phase_aligned_distance,
    simulate,
)

BIN = os.environ.get("SUBMISSION_BIN", "/app/submission")

TOL = 1e-9


def _normalize(a):
    a = np.asarray(a, dtype=np.float64)
    a = np.abs(a)
    nrm = np.linalg.norm(a)
    if nrm == 0.0:
        a = np.ones_like(a)
        nrm = np.linalg.norm(a)
    return a / nrm


def _gaussian(n, mean, width):
    x = np.arange(1 << n, dtype=np.float64)
    return _normalize(np.exp(-0.5 * ((x - mean) / width) ** 2))


def _triangular(n, peak):
    x = np.arange(1 << n, dtype=np.float64)
    span = float((1 << n) - 1)
    a = 1.0 - np.abs(x - peak) / span
    a = np.clip(a, 0.0, None)
    return _normalize(a)


def _exponential(n, rate):
    x = np.arange(1 << n, dtype=np.float64)
    return _normalize(np.exp(-rate * x))


def _bimodal(n, m1, w1, m2, w2, mix):
    x = np.arange(1 << n, dtype=np.float64)
    g1 = np.exp(-0.5 * ((x - m1) / w1) ** 2)
    g2 = np.exp(-0.5 * ((x - m2) / w2) ** 2)
    return _normalize(mix * g1 + (1.0 - mix) * g2)


def _product(n, na, va, nb, vb):
    """Outer product of two smaller nonnegative vectors over sub-registers.

    na + nb == n. The high na qubits carry distribution va, the low nb qubits
    carry vb; big-endian tensor order gives amp[j] = va[hi] * vb[lo].
    """
    va = _normalize(va)
    vb = _normalize(vb)
    out = np.zeros(1 << n, dtype=np.float64)
    for hi in range(1 << na):
        for lo in range(1 << nb):
            out[(hi << nb) | lo] = va[hi] * vb[lo]
    return _normalize(out)


def distributions():
    """Return the ordered list of (label, n, amplitude_vector) specs.

    Fixed parameters, no randomness. Families span discretized Gaussian,
    triangular, exponential, bimodal, and product distributions across
    n in 3..8. Metamorphic partners (reversed vectors and a probability
    vs amplitude pair) are included deliberately.
    """
    d = []
    d.append(("gauss_n3_c", 3, _gaussian(3, 3.5, 1.2)))
    d.append(("gauss_n4_left", 4, _gaussian(4, 3.0, 1.5)))
    d.append(("gauss_n5_right", 5, _gaussian(5, 22.0, 3.0)))
    d.append(("gauss_n6_wide", 6, _gaussian(6, 31.5, 12.0)))
    d.append(("tri_n4_peak10", 4, _triangular(4, 10.0)))
    d.append(("tri_n5_peak8", 5, _triangular(5, 8.0)))
    d.append(("exp_n3_fast", 3, _exponential(3, 0.9)))
    d.append(("exp_n5_slow", 5, _exponential(5, 0.15)))
    d.append(("exp_n7_mid", 7, _exponential(7, 0.05)))
    d.append(("bimodal_n5", 5, _bimodal(5, 6.0, 2.0, 25.0, 2.5, 0.6)))
    d.append(("bimodal_n6", 6, _bimodal(6, 10.0, 3.0, 50.0, 4.0, 0.45)))
    d.append(
        (
            "prod_n6",
            6,
            _product(6, 3, _gaussian(3, 3.5, 1.0), 3, _exponential(3, 0.4)),
        )
    )
    d.append(
        (
            "prod_n8",
            8,
            _product(8, 4, _gaussian(4, 7.5, 2.0), 4, _triangular(4, 4.0)),
        )
    )
    d.append(("gauss_n4_rev", 4, _gaussian(4, 3.0, 1.5)[::-1].copy()))
    return d


def amplitude_probability_pair():
    """Return (amp_spec, prob_spec) sharing the same base vector.

    amp_spec carries amplitudes a; prob_spec carries the L2-normalized
    version of a**2 (as amplitudes). A solver that loads probabilities as
    amplitudes prepares the wrong state on amp_spec and the right one on
    prob_spec, so scoring both catches the confusion.
    """
    n = 4
    a = _gaussian(n, 5.0, 1.6)
    p = _normalize(a * a)
    return ("guard_amp_n4", n, a), ("guard_prob_n4", n, p)


def bcx_of(n):
    """CX count of the Mottonen cascade at width n: 2**n - 2 (0 when n<=1)."""
    if n <= 1:
        return 0
    return (1 << n) - 2


def write_spec(path, n, amps):
    lines = [str(n)]
    for v in amps:
        lines.append(repr(float(v)))
    lines.append("B %d" % bcx_of(n))
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def all_specs():
    specs = list(distributions())
    ap, pp = amplitude_probability_pair()
    specs.append(ap)
    specs.append(pp)
    return specs


def emit(n, amps):
    spec = os.path.join(tempfile.gettempdir(), "enc_spec.txt")
    out = os.path.join(tempfile.gettempdir(), "enc_out.qasm")
    write_spec(spec, n, amps)
    try:
        r = subprocess.run([BIN, spec, out], capture_output=True, timeout=120)
    except Exception:
        return None
    if r.returncode != 0 or not os.path.exists(out):
        return None
    with open(out) as f:
        return f.read()


def check_one(n, amps):
    """Return (ok, ncases, reason) for a single distribution.

    Counts one semantic case for the full-vector L2 check, one for the CX
    budget check, one for the gate-alphabet check, and one per basis
    amplitude verified against the target.
    """
    text = emit(n, amps)
    if text is None:
        return False, 0, "no output"
    nq, gates = parse(text)
    if nq is None:
        return False, 0, "no qubit declaration"
    if nq != n:
        return False, 0, "wrong qubit count"
    cases = 0
    if not only_allowed(gates):
        return False, cases, "illegal gate present"
    cases += 1
    b = bcx_of(n)
    if cx_count(gates) > b:
        return False, cases, "cx budget exceeded"
    cases += 1
    sv = simulate(gates, n)
    target = np.asarray(amps, dtype=np.complex128)
    dist = phase_aligned_distance(sv, target)
    if dist > TOL:
        return False, cases, "state distance %g" % dist
    cases += 1
    mags = np.abs(sv)
    for j in range(1 << n):
        if abs(mags[j] - abs(target[j])) > TOL:
            return False, cases, "amplitude mismatch at %d" % j
        cases += 1
    return True, cases, "ok"


def check_metamorphic_reverse():
    """A distribution and its reverse must both prepare correctly, and the
    reversed target must equal the bit-flip (X on all qubits) of the first.
    Verified through the emitted circuits. Returns (ok, ncases, reason)."""
    n = 4
    a = _gaussian(n, 3.0, 1.5)
    ar = a[::-1].copy()
    ta = emit(n, a)
    tr = emit(n, ar)
    if ta is None or tr is None:
        return False, 0, "no output"
    _, ga = parse(ta)
    _, gr = parse(tr)
    sva = simulate(ga, n)
    svr = simulate(gr, n)
    cases = 0
    if phase_aligned_distance(sva, a.astype(np.complex128)) > TOL:
        return False, cases, "forward prep wrong"
    cases += 1
    if phase_aligned_distance(svr, ar.astype(np.complex128)) > TOL:
        return False, cases, "reverse prep wrong"
    cases += 1
    flipped = sva[::-1].copy()
    if phase_aligned_distance(flipped, ar.astype(np.complex128)) > TOL:
        return False, cases, "X-relation broken"
    cases += 1
    return True, cases, "ok"


def evaluate():
    total = 0
    for label, n, amps in all_specs():
        ok, c, reason = check_one(n, amps)
        total += c
        if not ok:
            return 0, total, "%s: %s" % (label, reason)
    ok, c, reason = check_metamorphic_reverse()
    total += c
    if not ok:
        return 0, total, "metamorphic: %s" % reason
    return 1, total, "all pass"
