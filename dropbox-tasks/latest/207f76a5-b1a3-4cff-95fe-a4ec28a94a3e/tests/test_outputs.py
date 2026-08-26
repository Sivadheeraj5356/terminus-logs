"""Verifier for exact-join-count-statistics.

Runs the agent's R program at /app/join_count.R on many county-map and synthetic
fixtures and requires its stdout to equal an independent exact oracle. Every
quantity is exact rational (fractions.Fraction); the program uses gmp. Three
spatial-autocorrelation diagnostics share one weight geometry:

  * Join counts BB/WW/BW of the binary label, with Cliff-Ord expectation,
    variance and a two-sided verdict under the free-sampling (binomial) null and
    the nonfree conditional (permutation) null, on both the first-order
    contiguity W1 and the derived second-order (lag-2) contiguity W2.
  * Moran's I and Geary's C of a disclosed numeric attribute, with exact
    randomization expectation and variance (Cliff-Ord, carrying the sample
    kurtosis b2) and a two-sided verdict, on W1 and W2.
  * Moran's I under the row-standardized W1, whose asymmetric rational weights
    give S0 = (non-isolated count) rather than 2m, exercising the general
    S1/S2 assembly.

All three read S0/S1/S2 from the same weight matrix, so a single weight-sum or
W2 error propagates across statistics. Independence is enforced three ways.
(1) W2 is built by a set-based common-neighbour route and cross-checked against
an adjacency-matrix common-neighbour count route. (2) The closed-form join-count
moments are cross-checked, on every small fixture and for W1 and W2, against a
full exact enumeration over black-sets/colourings; the Moran/Geary closed-form
randomization moments are cross-checked against a full permutation enumeration of
the numeric attribute over locations. Neither enumeration reuses the closed-form
algebra. (3) The oracle never trusts the program's own output.
"""

import os
import subprocess
import tempfile
from fractions import Fraction as F
from itertools import combinations, permutations
from math import comb

CANDIDATE = "/app/join_count.R"
REAL_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "real")

# ---------------------------------------------------------------------------
# Weight geometry (shared)
# ---------------------------------------------------------------------------


def second_order_edges(n, edges):
    """W2 as a set-based boolean 2-hop closure minus W1 minus the diagonal.

    {i, j} is a second-order edge iff i != j, {i, j} is not a first-order edge,
    and i and j share at least one common first-order neighbour. The weight is
    strictly 0/1: the number of distinct 2-paths is never used as a weight.
    """
    adj = [set() for _ in range(n)]
    for i, j in edges:
        adj[i].add(j)
        adj[j].add(i)
    w2 = set()
    for i in range(n):
        two = set()
        for k in adj[i]:
            two |= adj[k]
        two -= {i}
        two -= adj[i]
        for j in two:
            w2.add(tuple(sorted((i, j))))
    return sorted(w2)


def second_order_edges_matrix(n, edges):
    """Independent W2 route: adjacency-matrix common-neighbour count > 0."""
    a = [[0] * n for _ in range(n)]
    for i, j in edges:
        a[i][j] = 1
        a[j][i] = 1
    w2 = set()
    for i in range(n):
        for j in range(i + 1, n):
            if a[i][j] == 0:
                common = sum(a[i][k] & a[k][j] for k in range(n))
                if common > 0:
                    w2.add((i, j))
    return sorted(w2)


def wmat_binary(n, edges):
    """Symmetric 0/1 weight matrix from an undirected edge list."""
    w = [[F(0)] * n for _ in range(n)]
    for i, j in edges:
        w[i][j] = F(1)
        w[j][i] = F(1)
    return w


def wmat_rowstd(n, edges):
    """Row-standardized weight matrix: each non-isolated row sums to 1.

    Isolated units (degree zero) keep an all-zero row. The matrix is asymmetric.
    """
    a = wmat_binary(n, edges)
    w = [[F(0)] * n for _ in range(n)]
    for i in range(n):
        rs = sum(a[i])
        if rs != 0:
            for j in range(n):
                w[i][j] = a[i][j] / rs
    return w


def weight_sums_mat(n, w):
    s0 = sum(w[i][j] for i in range(n) for j in range(n))
    s1 = F(1, 2) * sum((w[i][j] + w[j][i]) ** 2 for i in range(n) for j in range(n))
    rowsum = [sum(w[i]) for i in range(n)]
    colsum = [sum(w[r][i] for r in range(n)) for i in range(n)]
    s2 = sum((rowsum[i] + colsum[i]) ** 2 for i in range(n))
    return s0, s1, s2


def weight_sums(n, edges):
    """Integer Cliff-Ord sums for the symmetric binary W (fast edge-list route)."""
    deg = [0] * n
    for i, j in edges:
        deg[i] += 1
        deg[j] += 1
    m = len(edges)
    return 2 * m, 4 * m, 4 * sum(d * d for d in deg)


# ---------------------------------------------------------------------------
# Join counts and their Cliff-Ord moments
# ---------------------------------------------------------------------------


def observed(labels, edges):
    bb = ww = bw = 0
    for i, j in edges:
        a, b = labels[i], labels[j]
        if a == 1 and b == 1:
            bb += 1
        elif a == 0 and b == 0:
            ww += 1
        else:
            bw += 1
    return bb, ww, bw


def falling(a, k):
    r = 1
    for t in range(k):
        r *= a - t
    return r


def probs_free(n, n1):
    p = F(n1, n)
    q = 1 - p
    return {
        "BB": (p * p, p**3, p**4),
        "WW": (q * q, q**3, q**4),
        "BW": (2 * p * q, p * q, 4 * p * p * q * q),
    }


def probs_nonfree(n, n1):
    n0 = n - n1
    f2, f3, f4 = falling(n, 2), falling(n, 3), falling(n, 4)

    def d2(num):
        return F(num, f2) if f2 else F(0)

    def d3(num):
        return F(num, f3) if f3 else F(0)

    def d4(num):
        return F(num, f4) if f4 else F(0)

    return {
        "BB": (d2(falling(n1, 2)), d3(falling(n1, 3)), d4(falling(n1, 4))),
        "WW": (d2(falling(n0, 2)), d3(falling(n0, 3)), d4(falling(n0, 4))),
        "BW": (
            d2(2 * n1 * n0),
            d3(n1 * n0 * (n - 2)),
            d4(4 * falling(n1, 2) * falling(n0, 2)),
        ),
    }


def closed_moments(n, edges, labels):
    s0, s1, s2 = weight_sums(n, edges)
    n1 = sum(1 for x in labels if x == 1)
    coef4 = s0 * s0 - s2 + s1
    out = {}
    for null, probs in (("FREE", probs_free(n, n1)), ("NONFREE", probs_nonfree(n, n1))):
        for join in ("BB", "WW", "BW"):
            m2, m3, m4 = probs[join]
            e = F(s0, 2) * m2
            var = F(1, 4) * (s1 * m2 + (s2 - 2 * s1) * m3 + coef4 * m4) - e * e
            out[(null, join)] = (e, var)
    return out


def enum_moments(n, edges, labels, do_free):
    n1 = sum(1 for x in labels if x == 1)
    out = {}
    tot = comb(n, n1)
    s = {"BB": 0, "WW": 0, "BW": 0}
    s2 = {"BB": 0, "WW": 0, "BW": 0}
    for black in combinations(range(n), n1):
        bs = set(black)
        bb = ww = bw = 0
        for i, j in edges:
            a, b = i in bs, j in bs
            if a and b:
                bb += 1
            elif not a and not b:
                ww += 1
            else:
                bw += 1
        for k, v in (("BB", bb), ("WW", ww), ("BW", bw)):
            s[k] += v
            s2[k] += v * v
    for k in ("BB", "WW", "BW"):
        e = F(s[k], tot)
        out[("NONFREE", k)] = (e, F(s2[k], tot) - e * e)
    if do_free:
        p = F(n1, n)
        q = 1 - p
        e = {"BB": F(0), "WW": F(0), "BW": F(0)}
        e2 = {"BB": F(0), "WW": F(0), "BW": F(0)}
        for mask in range(1 << n):
            w = p ** bin(mask).count("1") * q ** (n - bin(mask).count("1"))
            bb = ww = bw = 0
            for i, j in edges:
                a, b = (mask >> i) & 1, (mask >> j) & 1
                if a and b:
                    bb += 1
                elif not a and not b:
                    ww += 1
                else:
                    bw += 1
            for k, v in (("BB", bb), ("WW", ww), ("BW", bw)):
                e[k] += w * v
                e2[k] += w * v * v
        for k in ("BB", "WW", "BW"):
            out[("FREE", k)] = (e[k], e2[k] - e[k] * e[k])
    return out


# ---------------------------------------------------------------------------
# Moran's I and Geary's C of a numeric attribute
# ---------------------------------------------------------------------------


def moran_from_dev(n, w, d, s0, m2):
    num = sum(w[i][j] * d[i] * d[j] for i in range(n) for j in range(n))
    return F(n, 1) / s0 * num / m2


def geary_from_val(n, w, z, s0, m2):
    num = sum(w[i][j] * (z[i] - z[j]) ** 2 for i in range(n) for j in range(n))
    return F(n - 1, 1) / (2 * s0) * num / m2


def num_moments(n, w, z):
    """Observed I and C and their exact randomization E/Var for weight matrix w.

    Returns a dict with I, C and (EI, VI, EC, VC). VI/VC are None when n < 4
    (the (n-2)(n-3) denominator is undefined). Returns None when the statistics
    are undefined: constant attribute (m2 = 0) or empty weight matrix (S0 = 0).
    """
    s0, s1, s2 = weight_sums_mat(n, w)
    zbar = F(sum(z), n)
    d = [F(v) - zbar for v in z]
    m2 = sum(x * x for x in d)
    m4 = sum(x**4 for x in d)
    if m2 == 0 or s0 == 0:
        return None
    b2 = F(n, 1) * m4 / (m2 * m2)
    i_stat = moran_from_dev(n, w, d, s0, m2)
    c_stat = geary_from_val(n, w, z, s0, m2)
    ei = F(-1, n - 1)
    ec = F(1)
    vi = vc = None
    if n >= 4:
        s0sq = s0 * s0
        ei2 = (
            n * ((n * n - 3 * n + 3) * s1 - n * s2 + 3 * s0sq)
            - b2 * ((n * n - n) * s1 - 2 * n * s2 + 6 * s0sq)
        ) / (F((n - 1) * (n - 2) * (n - 3)) * s0sq)
        vi = ei2 - ei * ei
        vc = (
            (n - 1) * s1 * (n * n - 3 * n + 3 - (n - 1) * b2)
            - F(1, 4) * (n - 1) * s2 * (n * n + 3 * n - 6 - (n * n - n + 2) * b2)
            + s0sq * (n * n - 3 - (n - 1) * (n - 1) * b2)
        ) / (F(n * (n - 2) * (n - 3)) * s0sq)
    return dict(I=i_stat, C=c_stat, EI=ei, VI=vi, EC=ec, VC=vc)


def num_enum(n, w, z):
    """Independent permutation enumeration of the randomization moments of I, C."""
    s0, _, _ = weight_sums_mat(n, w)
    zbar = F(sum(z), n)
    m2 = sum((F(v) - zbar) ** 2 for v in z)
    if m2 == 0 or s0 == 0:
        return None
    is_, cs = [], []
    for perm in permutations(range(n)):
        zz = [z[perm[i]] for i in range(n)]
        d = [F(v) - zbar for v in zz]
        is_.append(moran_from_dev(n, w, d, s0, m2))
        cs.append(geary_from_val(n, w, zz, s0, m2))
    tot = len(is_)
    mi = sum(is_) / tot
    mc = sum(cs) / tot
    vi = sum(x * x for x in is_) / tot - mi * mi
    vc = sum(x * x for x in cs) / tot - mc * mc
    return dict(EI=mi, VI=vi, EC=mc, VC=vc)


# ---------------------------------------------------------------------------
# Formatting and labels
# ---------------------------------------------------------------------------


def fmtq(x):
    return f"{x.numerator}/{x.denominator}"


def label(obs, e, var):
    """Two-sided verdict from the standardized deviate; NA when var is zero."""
    if var == 0:
        return "NA"
    dev = F(obs) - e
    if dev == 0:
        return "NS"
    if dev * dev > 4 * var:
        return "HIGH" if dev > 0 else "LOW"
    return "NS"


def num_line(stat):
    """Format 'I E Var verdict' (or C) for a Moran/Geary quantity.

    stat is (value, E, Var) with Var possibly None, or None when undefined.
    Undefined statistics print 'NA NA NA NA'; a defined value with no variance
    (n < 4) prints 'value E NA NA'.
    """
    if stat is None:
        return "NA NA NA NA"
    value, e, var = stat
    if var is None:
        return f"{fmtq(value)} {fmtq(e)} NA NA"
    return f"{fmtq(value)} {fmtq(e)} {fmtq(var)} {label(value, e, var)}"


# ---------------------------------------------------------------------------
# Full oracle report
# ---------------------------------------------------------------------------


PVAL_CAP = 20000


def perm_pvalues(n, edges, labels):
    """Exact two-sided conditional-permutation p-values for the BB, WW, BW join counts.

    With the number of black units held fixed, enumerate every labelling and, for each
    join count, form the exact rational two-sided p-value as the share of labellings whose
    count deviates from the exact permutation mean by at least the observed deviation. The
    value is NA when the enumeration would exceed the disclosed cap or when the count is
    constant across all labellings (zero permutation variance).
    """
    n1 = sum(1 for x in labels if x == 1)
    tot = comb(n, n1)
    obs = dict(zip(("BB", "WW", "BW"), observed(labels, edges)))
    if tot > PVAL_CAP:
        return {"BB": None, "WW": None, "BW": None}
    hist = {"BB": {}, "WW": {}, "BW": {}}
    ssum = {"BB": 0, "WW": 0, "BW": 0}
    for black in combinations(range(n), n1):
        bs = set(black)
        bb = ww = bw = 0
        for i, j in edges:
            a, b = i in bs, j in bs
            if a and b:
                bb += 1
            elif not a and not b:
                ww += 1
            else:
                bw += 1
        for k, v in (("BB", bb), ("WW", ww), ("BW", bw)):
            hist[k][v] = hist[k].get(v, 0) + 1
            ssum[k] += v
    out = {}
    for k in ("BB", "WW", "BW"):
        vals = hist[k]
        if len(vals) <= 1:
            out[k] = None
            continue
        mu = F(ssum[k], tot)
        thr = abs(F(obs[k]) - mu)
        cnt = sum(freq for v, freq in vals.items() if abs(F(v) - mu) >= thr)
        out[k] = F(cnt, tot)
    return out


def oracle_block(n, edges, labels, prefix):
    s0, s1, s2 = weight_sums(n, edges)
    bb, ww, bw = observed(labels, edges)
    cm = closed_moments(n, edges, labels)
    obs = {"BB": bb, "WW": ww, "BW": bw}
    lines = [
        f"{prefix}S0 = {s0}",
        f"{prefix}S1 = {s1}",
        f"{prefix}S2 = {s2}",
        f"{prefix}BB = {bb}",
        f"{prefix}WW = {ww}",
        f"{prefix}BW = {bw}",
    ]
    for null in ("FREE", "NONFREE"):
        for join in ("BB", "WW", "BW"):
            e, var = cm[(null, join)]
            lines.append(
                f"{prefix}{null}_{join} = {fmtq(e)} {fmtq(var)} {label(obs[join], e, var)}"
            )
    return lines


def moran_of(mom, key):
    if mom is None:
        return None
    return (mom["I"], mom["EI"], mom["VI"])


def geary_of(mom, key):
    if mom is None:
        return None
    return (mom["C"], mom["EC"], mom["VC"])


def numeric_block(n, edges, w2edges, z):
    w1 = wmat_binary(n, edges)
    w2 = wmat_binary(n, w2edges)
    wstd = wmat_rowstd(n, edges)
    m1 = num_moments(n, w1, z)
    m2m = num_moments(n, w2, z)
    mstd = num_moments(n, wstd, z)
    zbar = F(sum(z), n)
    ss = sum((F(v) - zbar) ** 2 for v in z)
    return [
        f"Z_MEAN = {fmtq(zbar)}",
        f"Z_SS = {fmtq(ss)}",
        f"MORAN = {num_line(moran_of(m1, 'W1'))}",
        f"GEARY = {num_line(geary_of(m1, 'W1'))}",
        f"W2_MORAN = {num_line(moran_of(m2m, 'W2'))}",
        f"W2_GEARY = {num_line(geary_of(m2m, 'W2'))}",
        f"STD_MORAN = {num_line(moran_of(mstd, 'STD'))}",
    ]


def oracle_report(n, edges, labels, values):
    w2 = second_order_edges(n, edges)
    pv = perm_pvalues(n, edges, labels)
    pval_lines = [
        f"PVAL_{k} = {fmtq(pv[k]) if pv[k] is not None else 'NA'}"
        for k in ("BB", "WW", "BW")
    ]
    lines = (
        oracle_block(n, edges, labels, "")
        + oracle_block(n, w2, labels, "W2_")
        + numeric_block(n, edges, w2, values)
        + pval_lines
    )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Fixture construction
# ---------------------------------------------------------------------------


class Fx:
    def __init__(self, name, ids, labels, edges, values):
        self.name = name
        self.ids = ids
        self.labels = labels
        self.values = values
        self.edges = sorted(set(tuple(sorted(e)) for e in edges))
        self.n = len(ids)

    def units_csv(self):
        rows = ["unit_id,label,value"] + [
            f"{u},{lab},{val}"
            for u, lab, val in zip(self.ids, self.labels, self.values)
        ]
        return "\n".join(rows) + "\n"

    def edges_csv(self):
        rows = ["unit_i,unit_j"] + [
            f"{self.ids[i]},{self.ids[j]}" for i, j in self.edges
        ]
        return "\n".join(rows) + "\n"


def load_real(slug):
    d = os.path.join(REAL_DIR, slug)
    with open(os.path.join(d, "units.csv")) as fh:
        ul = fh.read().splitlines()
    with open(os.path.join(d, "edges.csv")) as fh:
        el = fh.read().splitlines()
    ids, labs = [], []
    for ln in ul[1:]:
        parts = ln.split(",")
        ids.append(parts[0])
        labs.append(int(parts[1]))
    import random

    rng = random.Random("val-" + slug)
    vals = [rng.randint(0, 12) for _ in ids]
    pos = {u: i for i, u in enumerate(ids)}
    edges = [(pos[a], pos[b]) for a, b in (ln.split(",") for ln in el[1:])]
    return Fx("real_" + slug, ids, labs, edges, vals)


def rand_graph(rng, n, dens):
    return [(i, j) for i in range(n) for j in range(i + 1, n) if rng.random() < dens]


def build_fixtures():
    import random

    fx = []
    rng = random.Random(20260716)

    def vals(n, spread=9):
        return [rng.randint(0, spread) for _ in range(n)]

    # 44 random synthetic graphs with random numeric attributes
    for k in range(44):
        n = rng.randint(2, 12)
        edges = rand_graph(rng, n, rng.choice([0.15, 0.35, 0.55, 0.8]))
        labels = [rng.randint(0, 1) for _ in range(n)]
        fx.append(
            Fx(f"rand{k:02d}", [f"u{i}" for i in range(n)], labels, edges, vals(n))
        )

    def path(n):
        return [(i, i + 1) for i in range(n - 1)]

    def cycle(n):
        return path(n) + [(0, n - 1)]

    def complete(n):
        return [(i, j) for i in range(n) for j in range(i + 1, n)]

    def star(n):
        return [(0, i) for i in range(1, n)]

    ids = lambda n: [f"u{i}" for i in range(n)]  # noqa: E731
    alt = lambda n: [i % 2 for i in range(n)]  # noqa: E731

    fx += [
        Fx("path6", ids(6), alt(6), path(6), [3, 1, 4, 1, 5, 9]),
        Fx("cycle6", ids(6), alt(6), cycle(6), [2, 7, 1, 8, 2, 8]),
        Fx("cycle7", ids(7), [1, 0, 1, 0, 1, 0, 0], cycle(7), [1, 2, 3, 4, 5, 6, 7]),
        Fx("complete5", ids(5), [1, 1, 0, 0, 0], complete(5), [5, 3, 9, 1, 4]),
        Fx("complete6", ids(6), [1, 1, 1, 0, 0, 0], complete(6), [1, 1, 2, 3, 5, 8]),
        Fx(
            "star8", ids(8), [1, 0, 0, 0, 0, 1, 1, 0], star(8), [9, 0, 1, 2, 3, 4, 5, 6]
        ),
        Fx("checker10", ids(10), alt(10), path(10), [i % 3 for i in range(10)]),
        Fx("nearmono1", ids(9), [0, 0, 0, 0, 1, 0, 0, 0, 0], cycle(9), vals(9)),
        Fx("nearmono2", ids(9), [1, 1, 1, 1, 0, 1, 1, 1, 1], cycle(9), vals(9)),
        # constant numeric attribute -> Moran/Geary undefined (m2 = 0 -> NA)
        Fx("flatval", ids(7), [1, 0, 1, 0, 1, 0, 1], cycle(7), [4] * 7),
        Fx("flatval_path", ids(6), alt(6), path(6), [2] * 6),
        Fx(
            "two_tri",
            ids(6),
            [1, 1, 0, 0, 1, 0],
            [(0, 1), (1, 2), (0, 2), (3, 4), (4, 5), (3, 5)],
            [6, 6, 2, 2, 9, 9],
        ),
        Fx("island", ids(6), [1, 0, 1, 0, 1, 1], [(0, 1), (1, 2), (2, 3)], vals(6)),
        Fx("noedge5", ids(5), [0, 1, 0, 1, 1], [], [1, 2, 3, 4, 5]),
        Fx("single", ["x"], [1], [], [7]),
        Fx("single0", ["x"], [0], [], [0]),
        Fx("mono1", ids(6), [1] * 6, path(6), [1, 2, 3, 4, 5, 6]),
        Fx("mono0", ids(6), [0] * 6, path(6), [6, 5, 4, 3, 2, 1]),
        Fx("mono1_cycle", ids(7), [1] * 7, cycle(7), vals(7)),
        Fx(
            "named",
            ["alpha", "beta", "gamma", "delta"],
            [1, 0, 1, 0],
            [(0, 1), (1, 2), (2, 3)],
            [10, 20, 30, 40],
        ),
    ]

    # W2 degeneracies and W2-focused structure.
    fx += [
        Fx("single_edge", ids(2), [1, 0], [(0, 1)], [3, 8]),
        Fx("single_edge_mono", ids(2), [1, 1], [(0, 1)], [4, 4]),
        Fx("triangle", ids(3), [1, 1, 0], complete(3), [2, 5, 8]),
        Fx("complete4", ids(4), [1, 1, 0, 0], complete(4), [1, 2, 4, 8]),
        Fx(
            "matching3",
            ids(6),
            [1, 0, 1, 0, 1, 0],
            [(0, 1), (2, 3), (4, 5)],
            [1, 9, 2, 8, 3, 7],
        ),
        Fx("path4", ids(4), [1, 0, 0, 1], path(4), [4, 1, 1, 4]),
        Fx("path5", ids(5), [1, 1, 0, 0, 1], path(5), [2, 4, 6, 8, 10]),
        Fx(
            "star6_leaves_black",
            ids(6),
            [0, 1, 1, 1, 1, 1],
            star(6),
            [0, 5, 5, 5, 5, 5],
        ),
        Fx(
            "star7_mixed", ids(7), [0, 1, 0, 1, 0, 1, 0], star(7), [7, 1, 6, 2, 5, 3, 4]
        ),
        Fx(
            "two_c4",
            ids(8),
            [1, 0, 1, 0, 0, 1, 0, 1],
            [(0, 1), (1, 2), (2, 3), (0, 3), (4, 5), (5, 6), (6, 7), (4, 7)],
            [1, 2, 3, 4, 5, 6, 7, 8],
        ),
        Fx("wheel6", ids(6), [1, 0, 1, 0, 1, 0], star(6) + cycle(6)[:5], vals(6)),
    ]

    # rook vs queen vs distance-band on the same 3x3 grid of units
    grid = [(r, c) for r in range(3) for c in range(3)]
    glabels = [(r + c) % 2 for (r, c) in grid]
    gvals = [r * 3 + c for (r, c) in grid]

    def band(pred):
        e = []
        for a in range(9):
            for b in range(a + 1, 9):
                if pred(grid[a], grid[b]):
                    e.append((a, b))
        return e

    rook = band(lambda p, q: abs(p[0] - q[0]) + abs(p[1] - q[1]) == 1)
    queen = band(lambda p, q: max(abs(p[0] - q[0]), abs(p[1] - q[1])) == 1)
    dist2 = band(lambda p, q: (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 <= 2)
    gids = [f"g{i}" for i in range(9)]
    fx += [
        Fx("grid_rook", gids, glabels, rook, gvals),
        Fx("grid_queen", gids, glabels, queen, gvals),
        Fx("grid_dist2", gids, glabels, dist2, gvals),
    ]

    for slug in [
        "RhodeIsland",
        "Hawaii",
        "Delaware",
        "Connecticut",
        "DistrictofColumbia",
        "Vermont",
        "Maine",
        "NewHampshire",
        "Massachusetts",
        "NewJersey",
        "Maryland",
        "Virginia",
        "Georgia",
        "Texas",
    ]:
        fx.append(load_real(slug))

    return fx


FIXTURES = build_fixtures()


# ---------------------------------------------------------------------------
# Candidate execution
# ---------------------------------------------------------------------------


def run_candidate_dir(dirpath):
    r = subprocess.run(
        ["Rscript", CANDIDATE, dirpath],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
    )
    assert r.returncode == 0, f"Rscript failed: {r.stderr}"
    return r.stdout


def run_candidate_fx(fx):
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "units.csv"), "w") as fh:
            fh.write(fx.units_csv())
        with open(os.path.join(d, "edges.csv"), "w") as fh:
            fh.write(fx.edges_csv())
        return run_candidate_dir(d)


def run_candidate_raw(units, edges):
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "units.csv"), "w") as fh:
            fh.write(units)
        with open(os.path.join(d, "edges.csv"), "w") as fh:
            fh.write(edges)
        return run_candidate_dir(d)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_fixture_count():
    """The behavioral suite exercises at least 60 distinct scored inputs."""
    assert len(FIXTURES) >= 60, len(FIXTURES)


def test_oracle_w2_construction():
    """The set-based W2 equals the adjacency-matrix common-neighbour W2 everywhere,
    is symmetric, has no diagonal, and is disjoint from W1."""
    for fx in FIXTURES:
        a = second_order_edges(fx.n, fx.edges)
        b = second_order_edges_matrix(fx.n, fx.edges)
        assert a == b, f"{fx.name}: set {a} != matrix {b}"
        w1 = set(fx.edges)
        for i, j in a:
            assert i < j and i != j, (fx.name, i, j)
            assert (i, j) not in w1, f"{fx.name}: {(i, j)} is both W1 and W2"


def test_oracle_selfcheck_enumeration():
    """Closed-form join-count moments equal a full independent enumeration on every
    small fixture, for both the W1 and the W2 weight matrix."""
    checked = 0
    for fx in FIXTURES:
        n1 = sum(fx.labels)
        if fx.n > 16 or n1 in (0, fx.n):
            continue
        do_free = fx.n <= 14
        for edges in (fx.edges, second_order_edges(fx.n, fx.edges)):
            em = enum_moments(fx.n, edges, fx.labels, do_free)
            cm = closed_moments(fx.n, edges, fx.labels)
            for key, val in em.items():
                assert cm[key] == val, f"{fx.name} {key}: closed {cm[key]} enum {val}"
        checked += 1
    assert checked >= 12, checked


def test_oracle_numeric_enumeration():
    """Closed-form Moran/Geary randomization moments equal a full permutation
    enumeration of the numeric attribute over locations, for the binary W1, the
    binary W2 and the row-standardized W1, on every small fixture."""
    checked = 0
    for fx in FIXTURES:
        if fx.n < 4 or fx.n > 7:
            continue
        w2 = second_order_edges(fx.n, fx.edges)
        mats = {
            "W1": wmat_binary(fx.n, fx.edges),
            "W2": wmat_binary(fx.n, w2),
            "STD": wmat_rowstd(fx.n, fx.edges),
        }
        for name, w in mats.items():
            cm = num_moments(fx.n, w, fx.values)
            en = num_enum(fx.n, w, fx.values)
            if cm is None or en is None:
                assert cm is None and en is None, (fx.name, name)
                continue
            assert cm["EI"] == en["EI"], (fx.name, name, "EI")
            assert cm["VI"] == en["VI"], (fx.name, name, "VI")
            assert cm["EC"] == en["EC"], (fx.name, name, "EC")
            assert cm["VC"] == en["VC"], (fx.name, name, "VC")
            checked += 1
    assert checked >= 12, checked


def test_candidate_matches_oracle():
    """The agent's program reproduces the exact oracle report on every fixture."""
    for fx in FIXTURES:
        got = run_candidate_fx(fx)
        want = oracle_report(fx.n, fx.edges, fx.labels, fx.values)
        assert got == want, f"{fx.name}\n--- got ---\n{got}\n--- want ---\n{want}"


def test_metamorphic_colour_swap():
    """Swapping the binary label swaps BB<->WW and their join-count moments in both
    weight blocks and leaves BW fixed; the numeric Moran/Geary lines, which depend
    only on the numeric attribute, are unchanged."""
    for fx in [f for f in FIXTURES if 0 < sum(f.labels) < f.n][:12]:
        swapped = Fx(
            fx.name + "_swap", fx.ids, [1 - x for x in fx.labels], fx.edges, fx.values
        )
        a = run_candidate_fx(fx).splitlines()
        b = run_candidate_fx(swapped).splitlines()
        da = dict(ln.split(" = ", 1) for ln in a)
        db = dict(ln.split(" = ", 1) for ln in b)
        for pre in ("", "W2_"):
            assert db[pre + "BB"] == da[pre + "WW"]
            assert db[pre + "WW"] == da[pre + "BB"]
            assert db[pre + "BW"] == da[pre + "BW"]
            for null in ("FREE", "NONFREE"):
                assert db[f"{pre}{null}_BB"] == da[f"{pre}{null}_WW"]
                assert db[f"{pre}{null}_WW"] == da[f"{pre}{null}_BB"]
                assert db[f"{pre}{null}_BW"] == da[f"{pre}{null}_BW"]
        for key in (
            "MORAN",
            "GEARY",
            "W2_MORAN",
            "W2_GEARY",
            "STD_MORAN",
            "Z_MEAN",
            "Z_SS",
        ):
            assert db[key] == da[key], (fx.name, key)


def test_metamorphic_relabel_invariance():
    """Permuting unit identifiers and reordering edges leaves the whole report fixed."""
    import random

    rng = random.Random(99)
    for fx in [f for f in FIXTURES if f.n >= 3][:12]:
        perm = list(range(fx.n))
        rng.shuffle(perm)
        new_ids = [None] * fx.n
        new_labels = [None] * fx.n
        new_values = [None] * fx.n
        for i in range(fx.n):
            new_ids[perm[i]] = fx.ids[i]
            new_labels[perm[i]] = fx.labels[i]
            new_values[perm[i]] = fx.values[i]
        new_edges = [(perm[i], perm[j]) for i, j in fx.edges]
        rng.shuffle(new_edges)
        relab = Fx(fx.name + "_relab", new_ids, new_labels, new_edges, new_values)
        assert run_candidate_fx(relab) == run_candidate_fx(fx)


def test_metamorphic_disjoint_double():
    """Two disjoint copies double S0/S1/S2 and every observed join count. The observed
    Moran's I (its n/S0 factor scaling cleanly) is unchanged on W1, W2 and the
    row-standardized W1; Geary's C, whose (n-1) factor does not, is not asserted."""
    for fx in [f for f in FIXTURES if 2 <= f.n <= 9 and f.edges][:10]:
        z0 = sum((F(v) - F(sum(fx.values), fx.n)) ** 2 for v in fx.values)
        if z0 == 0:
            continue
        ids2 = list(fx.ids) + [u + "_b" for u in fx.ids]
        labels2 = list(fx.labels) + list(fx.labels)
        values2 = list(fx.values) + list(fx.values)
        edges2 = list(fx.edges) + [(i + fx.n, j + fx.n) for i, j in fx.edges]
        dbl = Fx(fx.name + "_dbl", ids2, labels2, edges2, values2)
        base = dict(ln.split(" = ", 1) for ln in run_candidate_fx(fx).splitlines())
        got = dict(ln.split(" = ", 1) for ln in run_candidate_fx(dbl).splitlines())
        for pre in ("", "W2_"):
            for key in ("S0", "S1", "S2", "BB", "WW", "BW"):
                assert int(got[pre + key]) == 2 * int(base[pre + key]), (
                    fx.name,
                    pre + key,
                )
        for key in ("MORAN", "W2_MORAN", "STD_MORAN"):
            assert got[key].split()[0] == base[key].split()[0], (fx.name, key)


def test_error_inputs():
    """Malformed inputs each yield exactly one line, ERROR."""
    good_u = "unit_id,label,value\na,0,3\nb,1,5\nc,1,2\n"
    good_e = "unit_i,unit_j\na,b\nb,c\n"
    cases = [
        ("unit_id,label\na,0\n", good_e),  # missing value column in header
        ("uid,label,value\na,0,1\n", good_e),  # bad units header
        (good_u, "i,j\na,b\n"),  # bad edges header
        (
            "unit_id,label,value\na,2,1\nb,1,2\n",
            "unit_i,unit_j\na,b\n",
        ),  # label not 0/1
        (
            "unit_id,label,value\na,0,x\nb,1,2\n",
            "unit_i,unit_j\na,b\n",
        ),  # non-integer value
        ("unit_id,label,value\na,0,1\na,1,2\n", "unit_i,unit_j\na,a\n"),  # duplicate id
        (good_u, "unit_i,unit_j\na,z\n"),  # unknown endpoint
        (good_u, "unit_i,unit_j\na,a\n"),  # self edge
        (good_u, "unit_i,unit_j\na,b\nb,a\n"),  # repeated edge
        ("unit_id,label,value\na,0,1\nb,,2\n", good_e),  # empty label field
        ("unit_id,label,value\na,0,\nb,1,2\n", good_e),  # empty value field
        (
            "unit_id,label,value\na,0,1,x\nb,1,2\n",
            "unit_i,unit_j\na,b\n",
        ),  # four columns
        ("unit_id,label,value\n", "unit_i,unit_j\n"),  # no units
        ("unit_id,label,value\n,0,1\nb,1,2\n", "unit_i,unit_j\nb,b\n"),  # empty id
    ]
    for units, edges in cases:
        out = run_candidate_raw(units, edges)
        assert out == "ERROR\n", f"units={units!r} edges={edges!r} -> {out!r}"


def test_determinism_second_run():
    """Re-running the program on the same inputs yields byte-identical output."""
    sample = FIXTURES[:8] + [f for f in FIXTURES if f.name.startswith("real_")][:4]
    first = [run_candidate_fx(fx) for fx in sample]
    second = [run_candidate_fx(fx) for fx in sample]
    assert first == second
