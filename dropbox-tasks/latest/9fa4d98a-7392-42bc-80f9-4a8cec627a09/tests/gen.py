"""Deterministic challenge generator for the LCG keystream-recovery task.

Verifier-only. Each instance plants a secret linear congruential generator
(secret modulus, multiplier, increment and seed), publishes a run of consecutive
outputs, draws the keystream from the outputs that come after the published run,
and XOR-encrypts a planted FLAG message. Every instance is validated against the
independent reference before it is emitted, so only cleanly recoverable
challenges are graded, and the whole battery is byte-identical across runs. Never
shipped in the agent image.
"""

import importlib.util
import os
import random

_ALPH = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"


def _load_oracle():
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "oracle_lcg", os.path.join(here, "oracle_lcg.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


oracle = _load_oracle()


def _is_probable_prime(n, rng, rounds=24):
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
            x = (x * x) % n
            if x == n - 1:
                break
        else:
            return False
    return True


def _gen_prime(rng, bits):
    while True:
        cand = rng.getrandbits(bits) | (1 << (bits - 1)) | 1
        if _is_probable_prime(cand, rng):
            return cand


def _gen_modulus(rng, width, modtype):
    lo, hi = 1 << (width - 1), 1 << width
    if modtype == "prime":
        while True:
            cand = rng.randrange(lo, hi) | 1
            if _is_probable_prime(cand, rng):
                return cand
    while True:
        p = _gen_prime(rng, width // 2)
        q = _gen_prime(rng, width - width // 2)
        m = p * q
        if lo <= m < hi and p != q:
            return m


def _flag(rng, total):
    body = "".join(rng.choice(_ALPH) for _ in range(total - 6))
    return ("FLAG{" + body + "}").encode()


def _simulate(m, a, c, x0, n):
    xs = [x0]
    for _ in range(n - 1):
        xs.append((a * xs[-1] + c) % m)
    return xs


def _encrypt(width, w, m, a, c, last_state, flag):
    sb = width // 8
    x = (a * last_state + c) % m
    ks = bytearray()
    while len(ks) < len(flag):
        ks += x.to_bytes(sb, "big")[:w]
        x = (a * x + c) % m
    return bytes(p ^ k for p, k in zip(flag, ks))


def _challenge_text(width, w, xs, ct):
    return "width=%d\nkeystream_high_bytes=%d\noutputs=%s\nciphertext=%s\n" % (
        width,
        w,
        ",".join(str(x) for x in xs),
        ct.hex(),
    )


def _core(rng, width, modtype, cmode, w):
    while True:
        m = _gen_modulus(rng, width, modtype)
        a = rng.randrange(2, m)
        c = 0 if cmode == "zero" else rng.randrange(1, m)
        x0 = rng.randrange(0, m)
        k = rng.choice([7, 8, 10, 12, 14, 16])
        flen = rng.choice([24, 28, 32, 40, 48, 56])
        flag = _flag(rng, flen)
        xs = _simulate(m, a, c, x0, k + 2)
        base_xs = xs[:k]
        ct = _encrypt(width, w, m, a, c, base_xs[-1], flag)
        text = _challenge_text(width, w, base_xs, ct)
        try:
            if oracle.recover_params(base_xs) != (m, a, c):
                continue
            if oracle.solve_text(text) != flag:
                continue
        except Exception:
            continue
        ext_ct = _encrypt(width, w, m, a, c, xs[k + 1], flag)
        ext_text = _challenge_text(width, w, xs[: k + 2], ext_ct)
        try:
            if oracle.solve_text(ext_text) != flag:
                continue
        except Exception:
            continue
        return text, ext_text, flag


def _combos():
    out = []
    for width in (48, 56):
        for modtype in ("prime", "composite"):
            for cmode in ("zero", "nonzero"):
                for w in (1, 2, 3):
                    out.append((width, modtype, cmode, w))
    return out


def instances(seed=20260719):
    rng = random.Random(seed)
    out = []
    for width, modtype, cmode, w in _combos():
        for rep in range(3):
            text, _ext, flag = _core(rng, width, modtype, cmode, w)
            name = "w%d_%s_%s_ks%d_%d" % (width, modtype, cmode[0], w, rep)
            out.append((name, text, flag))
    return out


def metamorphic_pairs(seed=20260720):
    rng = random.Random(seed)
    schedule = [
        (48, "prime", "nonzero", 2),
        (48, "composite", "zero", 1),
        (48, "prime", "zero", 3),
        (56, "prime", "zero", 2),
        (56, "composite", "nonzero", 3),
        (56, "prime", "nonzero", 1),
        (48, "composite", "nonzero", 2),
        (56, "composite", "zero", 2),
    ]
    out = []
    for i, (width, modtype, cmode, w) in enumerate(schedule):
        base_text, ext_text, flag = _core(rng, width, modtype, cmode, w)
        out.append(("meta%02d" % i, base_text, ext_text, flag))
    return out
