"""Deterministic masked-exponent challenges with fused recovery obligations.

Every challenge plants a modulus ``n = p*q``, a message ``m`` whose fixed-width
encoding starts with the disclosed header, and a mask base ``s``. An authentic
row ``(e, f, c)`` publishes ``c = m^e * s^f (mod n)``. Nothing about the split
between authentic and inauthentic rows, the mask, the message, or the factors is
published.

The latent parameters are redrawn for every challenge: the modulus size, the row
count, how many rows are authentic, whether the mask base or the message is a
unit, and the root order ``G`` reachable from the authentic rows (drawn from the
small odd primes, with the field orders arranged so that ``G`` really divides
them, sometimes to multiplicity two). Nothing here is a fixed recipe a solver
can carry in from another instance.

Families, by which obligations they fuse:

* ``clear`` / ``wide`` -- mask cancellation alone: the reachable order is one and
  every value is a unit, so the fold has to run in ``Z/n`` with coefficients that
  zero the mask column.
* ``masked`` -- mask cancellation and an untrusted row list.
* ``rooted`` -- a factor falls out of the rows, the fold only pins ``m^G`` over
  the co-factor, and the header picks one of ``G`` lifts.
* ``rooted_masked`` -- the above plus an untrusted row list, so the subset choice
  moves the reachable order, which moves the root set, which moves which lift
  carries the header.
* ``crossed`` -- the message is a unit and the factor is leaked only by an
  inauthentic row, so the same row must be used for factoring and excluded from
  the fold; roots are then needed in both fields, giving ``G*G`` lifts.
"""

import random

import rsa_common as rc

HEADER_HI = int.from_bytes(rc.MAGIC, "big") + 1
ROOT_ORDERS = (3, 5, 7, 11, 13)
FAMILIES = ("clear", "wide", "masked", "rooted", "rooted_masked", "crossed")


def _byte_len(n):
    return n.bit_length() // 8


def _usable_modulus(n, bits):
    """The width has to be an exact byte count, and the top of the modulus has
    to leave room for a header-carrying residue, so that every lift a solver can
    form is representable and the header alone separates them."""
    if n.bit_length() != 2 * bits or (2 * bits) % 8 != 0:
        return False
    L = _byte_len(n)
    return (n >> (8 * (L - 2))) >= HEADER_HI


def _gen_modulus(rng, bits, root, both):
    for _ in range(80):
        if both:
            p = rc.gen_prime_congruent(rng, bits, root, 1)
        else:
            p = rc.gen_prime(rng, bits)
        qmod = root * root if (root > 1 and rng.random() < 0.5) else root
        q = (
            rc.gen_prime_congruent(rng, bits, qmod, 1)
            if root > 1
            else rc.gen_prime(rng, bits)
        )
        if p == q:
            continue
        n = p * q
        if _usable_modulus(n, bits):
            return p, q, n
    return None


def _header_unit(rng, n, L):
    prefix = int.from_bytes(rc.MAGIC, "big") << (8 * (L - 2))
    span = 1 << (8 * (L - 2))
    for _ in range(400):
        m = prefix + rng.randrange(span)
        if 0 < m < n and rc.gcd(m, n) == 1:
            return m
    return None


def _header_multiple(rng, n, p, L):
    """A header-carrying message divisible by ``p`` but not by the co-factor."""
    prefix = int.from_bytes(rc.MAGIC, "big") << (8 * (L - 2))
    span = 1 << (8 * (L - 2))
    lo, hi = prefix // p + 1, (prefix + span) // p
    if hi <= lo:
        return None
    q = n // p
    for _ in range(400):
        k = rng.randrange(lo, hi)
        m = p * k
        if 0 < m < n and rc.gcd(k, q) == 1 and m % q != 0 and rc.has_magic(m, L):
            return m
    return None


def _authentic_rows(rng, n, m, s, count, root):
    es, fs = [], []
    for _ in range(count):
        es.append(root * rng.randrange(1 << 30, 1 << 50))
        fs.append(rng.randrange(1, 1 << 20))
    if rc.gcd_list(fs) != 1:
        return None
    sol = rc.lattice_solve(es, fs)
    if sol is None or sol[0] != root:
        return None
    rows = []
    for e, f in zip(es, fs):
        rows.append((e, f, pow(m, e, n) * pow(s, f, n) % n))
    return rows


def _forged_rows(rng, n, p, root, count, kind):
    rows = []
    for _ in range(count):
        e = root * rng.randrange(1 << 30, 1 << 50)
        f = rng.randrange(1, 1 << 20)
        if kind == "unit":
            while True:
                c = rng.randrange(2, n)
                if rc.gcd(c, n) == 1:
                    break
        else:
            q = n // p
            while True:
                k = rng.randrange(1, q)
                if rc.gcd(k, q) == 1:
                    c = p * k % n
                    if c != 0:
                        break
        rows.append((e, f, c))
    return rows


def _present(rng, rows, n):
    """Some challenges publish values in a non-canonical residue class."""
    if rng.random() < 0.35:
        return [(e, f, c + rng.randrange(1, 6) * n) for e, f, c in rows]
    return list(rows)


def _build(rng, cid, bits, family):
    root = 1 if family in ("clear", "wide", "masked") else rng.choice(ROOT_ORDERS)
    made = _gen_modulus(rng, bits, root, family == "crossed")
    if made is None:
        return None
    p, q, n = made
    L = _byte_len(n)

    if family in ("rooted", "rooted_masked"):
        m = _header_multiple(rng, n, p, L)
    else:
        m = _header_unit(rng, n, L)
    if m is None:
        return None

    s = rng.randrange(2, n)
    if rc.gcd(s, n) != 1:
        return None

    if family == "clear":
        n_auth, forged = 3, []
    elif family == "wide":
        n_auth, forged = rng.choice((4, 5)), []
    elif family == "masked":
        n_auth, forged = 3, [("unit", 2)]
    elif family == "rooted":
        n_auth, forged = rng.choice((3, 4)), []
    elif family == "rooted_masked":
        n_auth, forged = 3, [("factor", 1)]
    else:
        n_auth, forged = 3, [("factor", 1), ("unit", 1)]

    auth = _authentic_rows(rng, n, m, s, n_auth, root)
    if auth is None:
        return None
    rows = list(auth)
    for kind, count in forged:
        rows += _forged_rows(rng, n, p, root, count, kind)
    rng.shuffle(rows)
    rows = _present(rng, rows, n)

    if rc.recover_general(n, rows, L) != m:
        return None
    return {
        "id": cid,
        "family": family,
        "bits": bits,
        "root": root,
        "authentic": n_auth,
        "n": str(n),
        "L": L,
        "rows": [(str(e), str(f), str(c)) for e, f, c in rows],
        "m_hex": m.to_bytes(L, "big").hex(),
        # Verifier-only. The published line never carries these.
        "p": str(p),
        "q": str(q),
    }


def _plan():
    plan = []
    for bits in (128, 160, 192, 224, 256):
        plan += [(bits, "clear")]
        plan += [(bits, "wide")]
        plan += [(bits, "masked")] * 3
        plan += [(bits, "rooted")] * 3
        plan += [(bits, "rooted_masked")] * 4
        plan += [(bits, "crossed")] * 4
    return plan


def build_suite(seed):
    rng = random.Random(seed)
    out = []
    cid = 0
    for bits, family in _plan():
        for _ in range(600):
            c = _build(rng, cid, bits, family)
            if c is not None:
                out.append(c)
                cid += 1
                break
    return out


def rows_of(c):
    return [(int(e), int(f), int(cc)) for e, f, cc in c["rows"]]


def public_line(c):
    body = " ".join(f"{e} {f} {cc}" for e, f, cc in c["rows"])
    return f"{c['id']} {c['n']} {c['L']} {len(c['rows'])} {body}"
