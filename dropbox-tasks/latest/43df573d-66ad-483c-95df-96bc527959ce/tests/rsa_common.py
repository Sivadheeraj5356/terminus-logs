"""Verifier-owned number theory for the masked-exponent recovery challenges.

Every published row of a challenge is a triple ``(e, f, c)``. An *authentic* row
satisfies ``c = m^e * s^f (mod n)`` for the challenge's secret message ``m`` and
its secret mask base ``s``. Both ``m`` and ``s`` stay verifier-side; only ``n``
and the rows ship.

Two independent recoveries exist here:

* ``recover_general`` sees exactly what the candidate sees. It reduces the rows,
  looks for a row whose value shares a factor with the modulus, and for every
  subset of rows solves the integer lattice ``sum a_i e_i = G``,
  ``sum a_i f_i = 0`` with ``G`` minimal positive. Folding the subset with those
  coefficients cancels the mask and leaves ``m^G``. When ``G`` shares a factor
  with a field order the fold only pins a power of the message, so every root is
  taken and lifted; the disclosed plaintext header selects the intended lift.
* ``recover_via_factors`` is handed the secret primes and never touches the ring
  ``Z/n``. Inside each prime field it eliminates the mask pairwise -- row ``i``
  raised to ``f_j`` against row ``j`` raised to ``-f_i`` leaves
  ``m^(e_i f_j - e_j f_i)`` -- then folds those determinant exponents. It shares
  no lattice step and no ring with the public route.

Ground truth is always the planted message. Python's arbitrary-precision
integers are the reference, independent of the candidate's Julia.
"""

# First two bytes of every planted message's fixed-width big-endian encoding.
MAGIC = b"\xca\xfe"

# The reference declines a subset whose root order is not a small prime, and
# declines a subset that would produce an unreasonable number of lifts. Both
# bounds are properties of the reference, not of the challenges: every planted
# challenge is reachable well inside them.
ROOT_ORDER_LIMIT = 100
LIFT_LIMIT = 512


def _is_probable_prime(n, rng, rounds=40):
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d = n - 1
    s = 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for _ in range(rounds):
        a = rng.randrange(2, n - 1)
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def gen_prime(rng, bits):
    while True:
        cand = rng.getrandbits(bits) | (1 << (bits - 1)) | 1
        if _is_probable_prime(cand, rng):
            return cand


def gen_prime_congruent(rng, bits, mod, res):
    """A ``bits``-bit prime congruent to ``res`` modulo ``mod``."""
    while True:
        cand = rng.getrandbits(bits) | (1 << (bits - 1))
        cand += (res - cand) % mod
        if cand % 2 == 0:
            cand += mod
        if cand.bit_length() != bits or cand % mod != res:
            continue
        if _is_probable_prime(cand, rng):
            return cand


def egcd(a, b):
    old_r, r = a, b
    old_x, x = 1, 0
    old_y, y = 0, 1
    while r:
        quot = old_r // r
        old_r, r = r, old_r - quot * r
        old_x, x = x, old_x - quot * x
        old_y, y = y, old_y - quot * y
    return old_r, old_x, old_y


def gcd(a, b):
    while b:
        a, b = b, a % b
    return abs(a)


def gcd_list(xs):
    g = 0
    for x in xs:
        g = gcd(g, x)
    return g


def multi_bezout(vals):
    """Integer coefficients ``a`` with ``sum(a_i * vals_i) == gcd(vals)``."""
    g = vals[0]
    coeffs = [1]
    for v in vals[1:]:
        g2, x, y = egcd(g, v)
        coeffs = [c * x for c in coeffs] + [y]
        g = g2
    return g, coeffs


def signed_powmod(base, k, mod):
    if k >= 0:
        return pow(base, k, mod)
    return pow(pow(base, -1, mod), -k, mod)


def fold(mod, cs, a):
    acc = 1
    for c, k in zip(cs, a):
        acc = acc * signed_powmod(c, k, mod) % mod
    return acc


def lattice_solve(es, fs):
    """Minimal positive ``G`` and integer coefficients ``a`` with
    ``sum a_i e_i == G`` and ``sum a_i f_i == 0``.

    The rows ``(f_i, e_i)`` generate a subgroup of ``Z^2``. Eliminating the
    ``f`` column with the extended Euclid leaves a set of rows whose ``f`` part
    is zero and which spans exactly the intersection of that subgroup with the
    ``e`` axis; the gcd of their ``e`` entries is the minimal reachable ``G``.
    Returns ``None`` when the intersection is trivial.
    """
    t = len(es)
    pivot = None
    zeros = []
    for i in range(t):
        u = [0] * t
        u[i] = 1
        f, e = fs[i], es[i]
        if f == 0:
            zeros.append((e, u))
            continue
        if pivot is None:
            pivot = (f, e, u)
            continue
        pf, pe, pu = pivot
        g, x, y = egcd(pf, f)
        ka, kb = pf // g, f // g
        pivot = (g, x * pe + y * e, [x * s + y * w for s, w in zip(pu, u)])
        zeros.append(
            (-kb * pe + ka * e, [-kb * s + ka * w for s, w in zip(pu, u)]),
        )
    if not zeros:
        return None
    g, coeffs = multi_bezout([z[0] for z in zeros])
    if g == 0:
        return None
    a = [0] * t
    for k, (_, u) in zip(coeffs, zeros):
        for j in range(t):
            a[j] += k * u[j]
    if g < 0:
        g, a = -g, [-v for v in a]
    return g, a


def _small_dlog(base, target, order, mod):
    cur = 1
    for x in range(order):
        if cur == target:
            return x
        cur = cur * base % mod
    raise ValueError("no discrete log")


def _nonresidue(r, q):
    z = 2
    while pow(z, (q - 1) // r, q) == 1:
        z += 1
    return z


def amm_root(o, r, q):
    """One ``r``-th root of ``o`` modulo the prime ``q``, for prime ``r``
    dividing ``q - 1`` to any multiplicity (Adleman-Manders-Miller)."""
    n = q - 1
    s, t = n, 0
    while s % r == 0:
        s //= r
        t += 1
    z = _nonresidue(r, q)
    k = 1
    while (k * s + 1) % r != 0:
        k += 1
    alp = (k * s + 1) // r
    a = pow(z, r ** (t - 1) * s, q)
    b = pow(o, r * alp - 1, q)
    c = pow(z, s, q)
    h = 1
    for i in range(1, t):
        d = pow(b, r ** (t - 1 - i), q)
        j = 0 if d == 1 else -_small_dlog(a, d, r, q)
        b = b * signed_powmod(pow(c, r, q), j, q) % q
        h = h * signed_powmod(c, j, q) % q
        c = pow(c, r, q)
    return pow(o, alp, q) * h % q


def _is_small_prime(d):
    if d < 2:
        return False
    i = 2
    while i * i <= d:
        if d % i == 0:
            return False
        i += 1
    return True


def field_roots(val, g, F):
    """Every ``x`` in ``GF(F)`` with ``x**g == val``.

    ``None`` means the reference declines the case (a root order that is not a
    small prime); the empty list means no root exists.
    """
    val %= F
    if val == 0:
        return [0]
    n = F - 1
    d = gcd(g, n)
    if d == 1:
        return [pow(val, pow(g % n, -1, n), F)]
    if d > ROOT_ORDER_LIMIT or not _is_small_prime(d):
        return None
    if pow(val, n // d, F) != 1:
        return []
    _, x, _ = egcd(g, n)
    w = pow(val, x % n, F)
    x0 = amm_root(w, d, F)
    zeta = pow(_nonresidue(d, F), n // d, F)
    out = []
    cur = x0
    for _ in range(d):
        out.append(cur)
        cur = cur * zeta % F
    return sorted(set(out))


def crt(r1, m1, r2, m2):
    _, s, _ = egcd(m1, m2)
    return (r1 + m1 * ((r2 - r1) * s % m2)) % (m1 * m2)


def has_magic(x, L, magic=MAGIC):
    if x < 0 or x >= (1 << (8 * L)):
        return False
    return x.to_bytes(L, "big")[: len(magic)] == magic


def _select(counts, L):
    """Keep the header-carrying candidates and return the best supported one."""
    keyed = [x for x in counts if has_magic(x, L)]
    if not keyed:
        return None
    return max(keyed, key=lambda x: (counts[x], -x))


def _find_factor(n, cs):
    for c in cs:
        if c == 0:
            continue
        g = gcd(c, n)
        if 1 < g < n:
            return g
    return None


# --------------------------------------------------------------------------- #
# Public route: modulus and rows only.                                         #
# --------------------------------------------------------------------------- #


def _subset_roots(F, cs, a, g):
    vals = [c % F for c in cs]
    if all(v == 0 for v in vals):
        return [0]
    if any(v == 0 for v in vals):
        return None
    return field_roots(fold(F, vals, a), g, F)


def _subsets(t, low=2):
    for mask in range(1, 1 << t):
        idx = [i for i in range(t) if mask & (1 << i)]
        if len(idx) >= low:
            yield idx


def recover_general(n, rows, L):
    es = [int(e) for e, _, _ in rows]
    fs = [int(f) for _, f, _ in rows]
    cs = [int(c) % n for _, _, c in rows]
    p = _find_factor(n, cs)
    counts = {}

    def bump(x):
        counts[x] = counts.get(x, 0) + 1

    for idx in _subsets(len(es)):
        sol = lattice_solve([es[i] for i in idx], [fs[i] for i in idx])
        if sol is None:
            continue
        g, a = sol
        sub_c = [cs[i] for i in idx]
        if p is None:
            if g != 1 or any(gcd(c, n) != 1 for c in sub_c):
                continue
            bump(fold(n, sub_c, a))
            continue
        q = n // p
        rp = _subset_roots(p, sub_c, a, g)
        rq = _subset_roots(q, sub_c, a, g)
        if rp is None or rq is None or not rp or not rq:
            continue
        if len(rp) * len(rq) > LIFT_LIMIT:
            continue
        for u in rp:
            for v in rq:
                bump(crt(u, p, v, q))
    return _select(counts, L)


# --------------------------------------------------------------------------- #
# Private route: the secret primes, pairwise mask elimination, never Z/n.      #
# --------------------------------------------------------------------------- #


def _field_candidates(F, es, fs, cs, idx):
    """Message residues mod the prime ``F`` implied by the rows in ``idx``,
    eliminating the mask through pairwise determinants inside ``GF(F)``."""
    vals = [cs[i] % F for i in idx]
    if all(v == 0 for v in vals):
        return [0]
    if any(v == 0 for v in vals):
        return None
    dets = []
    bases = []
    for a in range(len(idx)):
        for b in range(a + 1, len(idx)):
            i, j = idx[a], idx[b]
            det = es[i] * fs[j] - es[j] * fs[i]
            if det == 0:
                continue
            base = (
                signed_powmod(vals[a], fs[j], F) * signed_powmod(vals[b], -fs[i], F) % F
            )
            dets.append(det)
            bases.append(base)
    if not dets:
        return None
    g, coeffs = multi_bezout(dets)
    if g == 0:
        return None
    val = fold(F, bases, coeffs)
    if g < 0:
        g, val = -g, pow(val, -1, F)
    return field_roots(val, g, F)


def recover_via_factors(p, q, rows, L):
    n = p * q
    es = [int(e) for e, _, _ in rows]
    fs = [int(f) for _, f, _ in rows]
    cs = [int(c) % n for _, _, c in rows]
    counts = {}
    for idx in _subsets(len(es)):
        rp = _field_candidates(p, es, fs, cs, idx)
        rq = _field_candidates(q, es, fs, cs, idx)
        if not rp or not rq:
            continue
        if len(rp) * len(rq) > LIFT_LIMIT:
            continue
        for u in rp:
            for v in rq:
                x = crt(u, p, v, q)
                counts[x] = counts.get(x, 0) + 1
    return _select(counts, L)
