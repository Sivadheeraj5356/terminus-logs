"""Verifier-owned wrong recoveries.

Each entry is a plausible attack that drops exactly one obligation of the
contract while keeping the rest intact, so a family it misses isolates the
obligation it dropped. ``_solve`` is a switchboard copy of the public reference:
turning one switch off is the mutation, which keeps the mutants honest instead of
strawmen. None of this ships to the agent.

Two bars apply to every baseline:

* ``EXPECT_FAIL[name]`` -- families where the baseline must score zero across the
  whole family;
* ``MAX_TOTAL[name]`` -- a ceiling on its score over the entire suite, so a
  baseline cannot quietly collect the families nobody thought to name.
"""

import rsa_common as rc

FULL = {
    "mask_column": True,
    "factor": True,
    "roots": True,
    "principal_only": False,
    "header": True,
    "subsets": True,
}


def _bump(counts, x):
    counts[x] = counts.get(x, 0) + 1


def _roots(F, cs, a, g, opts):
    vals = [c % F for c in cs]
    if all(v == 0 for v in vals):
        return [0]
    if any(v == 0 for v in vals):
        return None
    val = rc.fold(F, vals, a)
    if not opts["roots"]:
        return [val]
    out = rc.field_roots(val, g, F)
    if out and opts["principal_only"]:
        return [out[-1] if len(out) > 1 else out[0]]
    return out


def _combine(es, fs, opts):
    if opts["mask_column"]:
        return rc.lattice_solve(es, fs)
    g, a = rc.multi_bezout(es)
    if g == 0:
        return None
    if g < 0:
        g, a = -g, [-v for v in a]
    return g, a


def _solve(n, rows, L, opts):
    es = [int(e) for e, _, _ in rows]
    fs = [int(f) for _, f, _ in rows]
    cs = [int(c) % n for _, _, c in rows]
    p = rc._find_factor(n, cs) if opts["factor"] else None
    counts = {}
    groups = list(rc._subsets(len(es))) if opts["subsets"] else [list(range(len(es)))]
    for idx in groups:
        sol = _combine([es[i] for i in idx], [fs[i] for i in idx], opts)
        if sol is None:
            continue
        g, a = sol
        sub_c = [cs[i] for i in idx]
        if p is None:
            if g != 1 or any(rc.gcd(c, n) != 1 for c in sub_c):
                continue
            _bump(counts, rc.fold(n, sub_c, a))
            continue
        q = n // p
        rp = _roots(p, sub_c, a, g, opts)
        rq = _roots(q, sub_c, a, g, opts)
        if not rp or not rq or len(rp) * len(rq) > rc.LIFT_LIMIT:
            continue
        for u in rp:
            for v in rq:
                _bump(counts, rc.crt(u, p, v, q))
    if not counts:
        return None
    if opts["header"]:
        return rc._select(counts, L)
    return max(counts, key=lambda x: (counts[x], -x))


def _mutant(**off):
    opts = dict(FULL)
    opts.update(off)
    return lambda n, rows, L: _solve(n, rows, L, opts)


def textbook_bezout(n, rows, L):
    """Fold the exponents with the extended Euclid straight in ``Z/n``, ignoring
    the mask column entirely. This is the memorised move for a shared modulus and
    it recovers ``m * s^k`` for a mask exponent ``k`` nobody cancelled."""
    es = [int(e) for e, _, _ in rows]
    cs = [int(c) % n for _, _, c in rows]
    g, coeffs = rc.multi_bezout(es)
    if g != 1:
        return None
    try:
        return rc.fold(n, cs, coeffs)
    except ValueError:
        return None


def hardcoded(n, rows, L):
    return int.from_bytes(rc.MAGIC + b"\x00" * 4, "big")


ALL = {
    # The memorised shared-modulus fold, unassisted.
    "textbook_bezout": textbook_bezout,
    # The full solver, but the fold never zeroes the mask column.
    "no_mask_column": _mutant(mask_column=False),
    # The full solver, but the header never selects among the lifts.
    "headerless": _mutant(header=False),
    # Takes a fixed non-principal root and never reads the header.
    "always_nonprincipal_no_header": _mutant(header=False, principal_only=True),
    # Never questions the row list.
    "trust_all_rows": _mutant(subsets=False),
    # Never notices that a value shares a factor with the modulus.
    "no_factor": _mutant(factor=False),
    # Factors and folds, but hands back the reachable power unrooted.
    "skip_root": _mutant(roots=False),
    "hardcoded": hardcoded,
}

ALL_FAMILIES = {"clear", "wide", "masked", "rooted", "rooted_masked", "crossed"}

# Families where the dropped obligation makes the baseline fail by construction,
# so it must score zero across the whole family.
EXPECT_FAIL = {
    "textbook_bezout": ALL_FAMILIES,
    "no_mask_column": ALL_FAMILIES,
    # Folding in Z/n cannot survive a value that shares a factor with n, and it
    # cannot reach a message whose fold only pins a proper power.
    "no_factor": {"rooted", "rooted_masked", "crossed"},
    # Handing back the reachable power is never the message.
    "skip_root": {"rooted", "rooted_masked", "crossed"},
    # The row that leaks the factor is not authentic, so the whole-list fold is
    # always mixed over the leaked prime and never resolves.
    "trust_all_rows": {"crossed"},
    "headerless": set(),
    "always_nonprincipal_no_header": set(),
    "hardcoded": ALL_FAMILIES,
}

# Dropping the header leaves a guess among the lifts, which is not a structural
# zero but must stay far off the pace on every family that offers a choice.
MAX_FAMILY = {
    "headerless": {"masked": 5, "rooted": 5, "rooted_masked": 7, "crossed": 7},
    "always_nonprincipal_no_header": {
        "masked": 5,
        "rooted": 7,
        "rooted_masked": 7,
        "crossed": 7,
    },
    "trust_all_rows": {"masked": 5, "rooted_masked": 7},
}

# Ceiling on the baseline's score over the entire suite. Reward is conjunctive,
# so any of these already earns nothing; the ceilings assert that no obligation
# has quietly become decorative.
MAX_TOTAL = {
    "textbook_bezout": 0,
    "no_mask_column": 0,
    "hardcoded": 0,
    "headerless": 26,
    "always_nonprincipal_no_header": 30,
    "trust_all_rows": 34,
    "no_factor": 30,
    "skip_root": 30,
}
