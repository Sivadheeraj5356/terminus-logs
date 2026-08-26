"""Verifier-owned reference eigensolver (not part of the agent environment).

Computes the k lowest eigenvalues of  -1/2 psi'' + V psi = E psi  for a well
given as fixed grid samples, using a fourth-order [-1,16,-30,16,-1]/(12 h^2)
kinetic stencil (symmetric pentadiagonal H, out-of-range psi = 0) and inertia
counting (the number of eigenvalues below a shift sigma equals the number of
negative pivots of an LDL^T factorisation of H - sigma*I) plus bisection.

The verifier calls this at run time to derive the reference spectra, so no
precomputed answers are stored anywhere the solver-under-test could read.
"""


def _count_below(diag_h, e1, e2, sigma):
    """Number of eigenvalues below sigma via LDL^T pivot signs of H - sigma*I."""
    n = len(diag_h)
    d = [0.0] * n
    l1 = [0.0] * n
    l2 = [0.0] * n
    neg = 0
    for i in range(n):
        if i - 2 >= 0:
            l2[i] = e2 / d[i - 2]
        if i - 1 >= 0:
            num = e1
            if i - 2 >= 0:
                num -= d[i - 2] * l2[i] * l1[i - 1]
            l1[i] = num / d[i - 1]
        di = diag_h[i] - sigma
        if i - 1 >= 0:
            di -= d[i - 1] * l1[i] * l1[i]
        if i - 2 >= 0:
            di -= d[i - 2] * l2[i] * l2[i]
        d[i] = di
        if di < 0.0:
            neg += 1
    return neg


def _lowest_k(diag_h, e1, e2, k, lo):
    """The k lowest eigenvalues via inertia counting and bisection."""
    hi = lo + 12.0
    while _count_below(diag_h, e1, e2, hi) < k:
        hi += (hi - lo)
    out = []
    for m in range(1, k + 1):
        a, b = lo, hi
        for _ in range(200):
            mid = 0.5 * (a + b)
            if _count_below(diag_h, e1, e2, mid) >= m:
                b = mid
            else:
                a = mid
            if b - a < 1e-13 * (abs(b) if abs(b) > 1.0 else 1.0):
                break
        out.append(0.5 * (a + b))
    return out


def reference_spectrum(instance):
    """Reference k lowest energies for one well instance dict."""
    xmin = float(instance["xmin"])
    xmax = float(instance["xmax"])
    n = int(instance["n"])
    k = int(instance["k"])
    v = [float(x) for x in instance["V"]]
    h = (xmax - xmin) / (n - 1)
    c = -0.5 / (12.0 * h * h)
    d0 = -30.0 * c
    e1 = 16.0 * c
    e2 = -1.0 * c
    diag_h = [d0 + v[i] for i in range(n)]
    vmin = min(v)
    return _lowest_k(diag_h, e1, e2, k, vmin - 2.0)
