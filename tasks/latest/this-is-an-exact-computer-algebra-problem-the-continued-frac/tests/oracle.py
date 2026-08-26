"""Independent exact oracle + hidden case inventory for
algebraic-real-continued-fraction-exact.

This module is imported by the verifier ONCE, at module load, and is then
DELETED from disk by test_outputs.py before any candidate program runs, so a
candidate cannot read, import, parse, or delegate to it. It carries the full
answer path (squarefree factorization, Sturm real-root isolation and r-th root
selection, certified algebraic floors, the Mobius transform with re-isolation,
big-integer convergents, and gcd-based periodicity) and the generated cases.
"""

import math
import random
from fractions import Fraction


def pnorm(p):
    q = [Fraction(x) for x in p]
    while len(q) > 1 and q[-1] == 0:
        q.pop()
    return q


def is_zero(p):
    return len(p) == 1 and p[0] == 0


def pderiv(p):
    if len(p) <= 1:
        return [Fraction(0)]
    return [p[i] * i for i in range(1, len(p))]


def pdivmod(a, b):
    a = pnorm(a)
    b = pnorm(b)
    if is_zero(b):
        raise ZeroDivisionError
    if is_zero(a) or len(a) < len(b):
        return [Fraction(0)], a
    q = [Fraction(0)] * (len(a) - len(b) + 1)
    r = a[:]
    while not is_zero(pnorm(r)) and len(pnorm(r)) >= len(b):
        r = pnorm(r)
        d = len(r) - len(b)
        coef = r[-1] / b[-1]
        q[d] = coef
        for i in range(len(b)):
            r[d + i] -= coef * b[i]
        r = pnorm(r)
    return pnorm(q), pnorm(r)


def pgcd(a, b):
    a = pnorm(a)
    b = pnorm(b)
    while not is_zero(b):
        _, r = pdivmod(a, b)
        a, b = b, pnorm(r)
    if a[-1] != 0:
        a = [x / a[-1] for x in a]
    return pnorm(a)


def to_int_primitive(p):
    p = pnorm(p)
    lcm = 1
    for c in p:
        lcm = lcm * c.denominator // math.gcd(lcm, c.denominator)
    ints = [int(c * lcm) for c in p]
    g = 0
    for v in ints:
        g = math.gcd(g, abs(v))
    if g == 0:
        return [0]
    ints = [v // g for v in ints]
    if ints[-1] < 0:
        ints = [-v for v in ints]
    return ints


def squarefree(P):
    P = pnorm(P)
    g = pgcd(P, pderiv(P))
    S, _ = pdivmod(P, g)
    return to_int_primitive(S)


def poly_eval_sign(p, x):
    val = Fraction(0)
    xp = Fraction(1)
    for c in p:
        val += c * xp
        xp *= x
    return (val > 0) - (val < 0)


def gcd_int_poly(a, b):
    return to_int_primitive(pgcd([Fraction(v) for v in a], [Fraction(v) for v in b]))


def poly_deg(p):
    return len(pnorm(p)) - 1


def sturm_chain(S):
    seq = [pnorm(S), pnorm(pderiv(S))]
    while not is_zero(seq[-1]):
        _, r = pdivmod(seq[-2], seq[-1])
        r = pnorm(r)
        if is_zero(r):
            break
        seq.append(pnorm([-x for x in r]))
    return seq


def sign_changes(vals):
    prev = 0
    ch = 0
    for v in vals:
        s = (v > 0) - (v < 0)
        if s != 0:
            if prev != 0 and s != prev:
                ch += 1
            prev = s
    return ch


def make_V(seq):
    def V(x):
        return sign_changes([sum(c * x**i for i, c in enumerate(p)) for p in seq])

    return V


def cauchy_bound(S):
    S = pnorm(S)
    lead = abs(S[-1])
    m = max((abs(c) for c in S[:-1]), default=Fraction(0))
    return 1 + Fraction(m, lead)


def rational_roots(S):
    ints = to_int_primitive(pnorm(S))
    roots = set()
    if ints[0] == 0:
        roots.add(Fraction(0))
        k = 0
        while ints[k] == 0:
            k += 1
        ints = ints[k:]
    c0, cd = ints[0], ints[-1]

    def divisors(n):
        n = abs(n)
        if n > 4000000000000000000:
            return set()
        ds = set()
        i = 1
        while i * i <= n:
            if n % i == 0:
                ds.add(i)
                ds.add(n // i)
            i += 1
        return ds

    for p in divisors(c0):
        for q in divisors(cd):
            for cand in (Fraction(p, q), Fraction(-p, q)):
                if poly_eval_sign(ints, cand) == 0:
                    roots.add(cand)
    return roots


def isolate_roots(S):
    S = pnorm(S)
    ints = to_int_primitive(S)
    seq = sturm_chain(S)
    V = make_V(seq)
    Bi = math.ceil(cauchy_bound(S)) + 1
    lo0, hi0 = Fraction(-Bi), Fraction(Bi)
    rroots = rational_roots(ints)

    def nonroot_mid(a, b):
        m = (a + b) / 2
        if poly_eval_sign(ints, m) != 0:
            return m
        step = (b - a) / 4
        for _ in range(80):
            m2 = m - step
            if a < m2 < b and poly_eval_sign(ints, m2) != 0:
                return m2
            step /= 2
        return m

    descs = []
    stack = [(lo0, hi0, V(lo0) - V(hi0))]
    while stack:
        a, b, cnt = stack.pop()
        if cnt == 0:
            continue
        if cnt == 1:
            rr = [r for r in rroots if a < r < b]
            descs.append(("rat", rr[0]) if rr else ("irr", a, b))
            continue
        m = nonroot_mid(a, b)
        stack.append((a, m, V(a) - V(m)))
        stack.append((m, b, V(m) - V(b)))

    def keyf(d):
        return d[1] if d[0] == "rat" else (d[1] + d[2]) / 2

    descs.sort(key=keyf)
    return descs


def floor_and_refine(ints, lo, hi):
    while math.floor(lo) != math.floor(hi):
        m = (lo + hi) / 2
        if poly_eval_sign(ints, lo) * poly_eval_sign(ints, m) < 0:
            hi = m
        else:
            lo = m
    a = math.floor(lo)
    while not (lo > a and hi < a + 1):
        m = (lo + hi) / 2
        if poly_eval_sign(ints, lo) * poly_eval_sign(ints, m) < 0:
            hi = m
        else:
            lo = m
    return a, lo, hi


def taylor_shift(ints, a):
    work = ints[:]
    out = []
    while work:
        m = len(work) - 1
        tmp = [0] * len(work)
        tmp[m] = work[m]
        for i in range(m - 1, -1, -1):
            tmp[i] = work[i] + a * tmp[i + 1]
        out.append(tmp[0])
        work = tmp[1:]
    return out


def reverse_poly(ints):
    r = ints[::-1]
    while len(r) > 1 and r[-1] == 0:
        r.pop()
    return r


def reisolate_select(Q1, nlo, nhi):
    for d in isolate_roots(Q1):
        if d[0] == "rat":
            if nlo < d[1] < nhi:
                return d[1], d[1]
            continue
        _, clo, chi = d
        while True:
            if clo >= nlo and chi <= nhi:
                return clo, chi
            if chi <= nlo or clo >= nhi:
                break
            m = (clo + chi) / 2
            if poly_eval_sign(Q1, clo) * poly_eval_sign(Q1, m) < 0:
                chi = m
            else:
                clo = m
    return nlo, nhi


def eq_complete(A, B):
    QA, loA, hiA = A
    QB, loB, hiB = B
    jlo, jhi = max(loA, loB), min(hiA, hiB)
    if jlo >= jhi:
        return False
    G = gcd_int_poly(QA, QB)
    if poly_deg(G) < 1:
        return False
    sa, sb = poly_eval_sign(G, jlo), poly_eval_sign(G, jhi)
    if sa == 0 or sb == 0:
        return False
    return sa * sb < 0


def continued_fraction(coeffs, r, k):
    S = squarefree(pnorm(coeffs))
    descs = isolate_roots(S)
    if r > len(descs):
        raise ValueError("r exceeds number of real roots")
    alpha = descs[r - 1]

    quotients = []
    completes = []
    if alpha[0] == "rat":
        x = alpha[1]
        terminated = False
        for _ in range(k):
            completes.append(("rat", x))
            a = math.floor(x)
            quotients.append(a)
            frac = x - a
            if frac == 0:
                terminated = True
                break
            x = 1 / frac
        term_flag = 1 if terminated else 0
    else:
        _, lo, hi = alpha
        Q = S[:]
        for _ in range(k):
            completes.append(("irr", Q[:], lo, hi))
            a, lo, hi = floor_and_refine(Q, lo, hi)
            quotients.append(a)
            Qs = taylor_shift(Q, a)
            ylo, yhi = lo - a, hi - a
            Q = to_int_primitive([Fraction(v) for v in reverse_poly(Qs)])
            nlo, nhi = Fraction(1) / yhi, Fraction(1) / ylo
            lo, hi = reisolate_select(Q, nlo, nhi)
        term_flag = 0

    m = len(quotients)
    H, K = [], []
    h2, h1, k2, k1 = 0, 1, 1, 0
    for a in quotients:
        h = a * h1 + h2
        kk = a * k1 + k2
        H.append(h)
        K.append(kk)
        h2, h1, k2, k1 = h1, h, k1, kk

    period = 0
    found = False
    for i in range(m):
        for j in range(i):
            ci, cj = completes[i], completes[j]
            if ci[0] == "rat" and cj[0] == "rat":
                eq = ci[1] == cj[1]
            elif ci[0] == "irr" and cj[0] == "irr":
                eq = eq_complete(ci[1:], cj[1:])
            else:
                eq = False
            if eq:
                period, found = i - j, True
                break
        if found:
            break

    return {
        "count": [m],
        "quotients": quotients,
        "numerators": H,
        "denominators": K,
        "terminated": [term_flag],
        "period": [period],
    }


def approx_root(ints, lo, hi, bits):
    lo, hi = Fraction(lo), Fraction(hi)
    slo = poly_eval_sign(ints, lo)
    for _ in range(bits):
        m = (lo + hi) / 2
        sm = poly_eval_sign(ints, m)
        if sm == 0:
            return m
        if slo * sm < 0:
            hi = m
        else:
            lo, slo = m, sm
    return (lo + hi) / 2


def cf_of_fraction(x, n):
    out = []
    for _ in range(n):
        a = math.floor(x)
        out.append(a)
        frac = x - a
        if frac == 0:
            break
        x = 1 / frac
    return out


def self_check(coeffs, r, res):
    """Independently re-derive the partial quotients and check invariants."""
    quotients = res["quotients"]
    H, K = res["numerators"], res["denominators"]
    # determinant identity of consecutive convergents
    ph, pk = 1, 0
    for i in range(len(quotients)):
        assert abs(H[i] * pk - ph * K[i]) == 1, f"convergent determinant broken at {i}"
        ph, pk = H[i], K[i]
    # numeric re-derivation of the quotient prefix for irrational alpha
    S = to_int_primitive(squarefree(pnorm(coeffs)))
    d = isolate_roots(squarefree(pnorm(coeffs)))[r - 1]
    if d[0] == "irr" and quotients:
        need = max(K[-1].bit_length() * 2 + 128, 200)
        q = approx_root(S, d[1], d[2], need)
        approx = cf_of_fraction(q, len(quotients))
        assert approx == quotients, (
            f"numeric oracle disagreement: {approx} vs {quotients}"
        )


def nreal(coeffs):
    try:
        return len(isolate_roots(squarefree(pnorm(coeffs))))
    except Exception:
        return 0


def curated():
    out = []
    # quadratic irrationals with assorted periods
    out += [
        ([-2, 0, 1], 2, 18),
        ([-2, 0, 1], 1, 12),
        ([-3, 0, 1], 2, 16),
        ([-7, 0, 1], 2, 16),
        ([-13, 0, 1], 2, 20),
        ([-1, -1, 1], 2, 15),
        ([-1, -1, 1], 1, 15),
        ([-2, -3, 1], 1, 12),
        ([-11, 0, 1], 2, 18),
        ([-2000000, 0, 1000000], 2, 10),
        ([-6, 0, 3], 2, 12),
    ]
    # quadratics with larger period lengths
    out += [
        ([-19, 0, 1], 2, 22),
        ([-21, 0, 1], 2, 22),
        ([-29, 0, 1], 2, 24),
        ([-46, 0, 1], 2, 24),
        ([-31, 0, 1], 2, 24),
    ]
    # near-integer roots -> deep refinement, large partial quotients
    out += [
        ([-10001, 0, 1], 2, 6),
        ([-9999, 0, 1], 2, 6),
        ([-1000001, 0, 1], 2, 5),
        ([-40001, 0, 200], 2, 6),
    ]
    # cubic / quartic / quintic irrationals
    out += [
        ([-2, 0, 0, 1], 1, 10),
        ([-5, 0, 0, 1], 1, 10),
        ([3, -3, 0, 1], 1, 10),
        ([-1, -1, 0, 1], 1, 10),
        ([-7, 0, 1, 1], 1, 10),
        ([-5, 3, 2, -4, 1], 2, 10),
    ]
    # Two reducible mixed-degree inputs -- (x-1)*(irreducible cubic) and
    # (x-1)(x+1)(x^3-x+1) -- were dropped from this set. Their difficulty came
    # from detecting and ordering a rational root that coexists with irrational
    # roots across a mixed-degree factorization, which the instruction does not
    # disclose, rather than from the disclosed continued-fraction and period core.
    # several real roots -> index selection over the same polynomial
    for rr in (1, 2, 3):
        out.append(([1, -3, 0, 1], rr, 10))  # x^3 - 3x + 1, three real irrationals
    for rr in (1, 2, 3):
        out.append(([1, -4, 0, 1], rr, 10))  # x^3 - 4x + 1
    for rr in (1, 2, 3, 4):
        out.append(([1, 0, -10, 0, 1], rr, 9))  # x^4 - 10x^2 + 1, four real roots
    # rational / integer alpha (terminating), incl. long rational CF truncated
    out += [
        ([-6, 11, -6, 1], 1, 8),
        ([-6, 11, -6, 1], 2, 8),
        ([-6, 11, -6, 1], 3, 8),
        ([-7, 1], 1, 4),
        ([-355, 113], 1, 6),
        ([-355, 113], 1, 3),
        ([2, -3, 1], 1, 5),
        ([2, -3, 1], 2, 5),
        ([-1, 0, 0, 0, 1], 2, 6),
        ([-2, 5, -4, 1], 1, 5),
        ([-2, 5, -4, 1], 2, 5),
    ]
    # reflection p(x) -> p(-x) and constant rescale copies (fresh, not deduplicated)
    out += [([-1, 1, 1], 2, 14), ([-14, 0, 2], 2, 16), ([-21, 0, 3], 2, 16)]
    return out


def random_cases(n):
    rng = random.Random(20260714)
    out = []
    while len(out) < n:
        deg = rng.choice([2, 2, 3, 3, 4])
        coeffs = [rng.randint(-7, 7) for _ in range(deg)] + [rng.choice([-2, -1, 1, 2])]
        nr = nreal(coeffs)
        if nr <= 0:
            continue
        r = rng.randint(1, nr)
        k = rng.randint(2, 25 if deg == 2 else 10)
        # Skip a reducible input (degree > 2) whose selected root is a detected
        # quadratic irrational (period > 0): the transform carries a defining
        # polynomial that never structurally repeats even though the root values
        # recur, so a fair graded period is only reachable when the input itself
        # is the minimal (degree <= 2) polynomial of the root.
        if deg > 2 and continued_fraction(coeffs, r, k)["period"][0] > 0:
            continue
        out.append((coeffs, r, k))
    return out


def cases():
    return curated() + random_cases(40)


KNOWN_QUAD = {
    (-2, 0, 1): (2, [1, 2, 2, 2, 2, 2], 1),
    (-3, 0, 1): (2, [1, 1, 2, 1, 2, 1], 2),
    (-7, 0, 1): (2, [2, 1, 1, 1, 4, 1], 4),
    (-1, -1, 1): (2, [1, 1, 1, 1, 1, 1], 1),
}


QUAD_CASES = [(list(c), r, 6) for c, (r, _q, _p) in KNOWN_QUAD.items()]


META_CASES = [([-2, 0, 1], 2, 10), ([23, -10, 1], 2, 10), ([-6, 0, 3], 2, 10)]
