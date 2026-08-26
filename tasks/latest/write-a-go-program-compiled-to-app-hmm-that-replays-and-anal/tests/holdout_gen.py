"""Deterministic grade-time case generator for the recording-replay task
(verifier-only).

Produces fresh cases (model parameters plus a 64-bit SEED, no recording) from
a generator seed, spanning probe-sized sequences, medium sequences, long
sequences, and corner classes: duration distributions concentrated far from
geometric, states with a minimum duration, dwell caps of 1, all-zero
missingness, heavy missingness, and single-step recordings. The recording
itself is derived by the reference sampler from each case's SEED, so the
grader can adjudicate the solver on inputs that are not present in the
shipped data and cannot be pre-baked. The long cases use many symbols and
thousands of steps so evaluating the log-likelihood by multiplying raw
probabilities underflows to zero while a correct log-domain implementation
stays finite.
"""
import random

MISSING = -1


def _norm(vals):
    s = sum(vals)
    return [v / s for v in vals]


def _rand_row(rng, n, floor):
    return _norm([rng.random() + floor for _ in range(n)])


def _jump_matrix(rng, n):
    A = []
    for i in range(n):
        row = [rng.random() + 0.05 for _ in range(n)]
        row[i] = 0.0
        A.append(_norm(row))
    return A


def _duration_row(rng, dmax, style):
    """A duration pmf on 1..dmax, deliberately far from geometric."""
    if dmax == 1:
        return [1.0]
    if style == "peak":
        d0 = rng.randint(max(2, dmax // 2), dmax)
        w = 1.0 + rng.random()
        vals = [pow(2.718281828459045, -((d - d0) / w) ** 2) + 1e-4
                for d in range(1, dmax + 1)]
        return _norm(vals)
    if style == "bimodal":
        vals = [1e-3] * dmax
        vals[0] = 1.0 + rng.random()
        vals[dmax - 1] = 1.0 + rng.random()
        return _norm(vals)
    if style == "minlen":
        cut = rng.randint(2, max(2, dmax - 1))
        vals = [0.0] * dmax
        for d in range(cut, dmax + 1):
            vals[d - 1] = rng.random() + 0.2
        return _norm(vals)
    return _rand_row(rng, dmax, 0.05)


def make_case(rng, cid, N, K, T, Dmax, styles=None, m_lo=0.05, m_hi=0.35,
              m_zero=False, emit_floor=1e-4, seed=None):
    """Build one case: model parameters plus a 64-bit SEED."""
    if styles is None:
        styles = [rng.choice(("peak", "bimodal", "flat")) for _ in range(N)]
    pi = _rand_row(rng, N, 1e-3)
    A = _jump_matrix(rng, N)
    B = [_rand_row(rng, K, emit_floor) for _ in range(N)]
    D = [_duration_row(rng, Dmax, styles[i]) for i in range(N)]
    M = ([0.0] * N if m_zero
         else [rng.uniform(m_lo, m_hi) for _ in range(N)])
    if seed is None:
        seed = rng.getrandbits(64)
    return {"id": cid, "N": N, "K": K, "T": T, "Dmax": Dmax, "seed": seed,
            "pi": pi, "A": A, "B": B, "D": D, "M": M}


def gen_cases(seed):
    """Return a list of fresh cases for the given generator seed."""
    rng = random.Random(seed)
    cases = []
    idx = 0

    def add(kind, **kw):
        nonlocal idx
        cases.append(make_case(rng, f"h{seed}_{kind}{idx:02d}", **kw))
        idx += 1

    # probe-sized sequences, incl. dwell cap 1, T=1, M=0, heavy missingness
    add("short", N=rng.randint(2, 4), K=rng.randint(3, 5),
        T=rng.randint(4, 12), Dmax=rng.randint(2, 5))
    add("short", N=rng.randint(2, 4), K=rng.randint(3, 5),
        T=rng.randint(4, 12), Dmax=rng.randint(2, 5), m_lo=0.3, m_hi=0.6)
    add("short", N=rng.randint(2, 3), K=rng.randint(3, 5),
        T=rng.randint(4, 12), Dmax=1)
    add("short", N=rng.randint(2, 4), K=rng.randint(3, 6),
        T=1, Dmax=rng.randint(2, 5))
    add("short", N=rng.randint(2, 3), K=rng.randint(3, 5),
        T=rng.randint(4, 10), Dmax=rng.randint(2, 4), m_zero=True)

    # medium: concentrated durations, minimum-duration states
    add("med", N=rng.randint(2, 4), K=rng.randint(4, 8),
        T=rng.randint(80, 250), Dmax=rng.randint(6, 10))
    add("med", N=rng.randint(2, 4), K=rng.randint(4, 8),
        T=rng.randint(80, 250), Dmax=rng.randint(6, 10), m_lo=0.15, m_hi=0.4)
    N = rng.randint(2, 3)
    add("med", N=N, K=rng.randint(4, 8), T=rng.randint(40, 90),
        Dmax=rng.randint(8, 12), styles=["minlen"] * N)

    # long: thousands of steps, many symbols, underflow-prone likelihoods
    add("long", N=rng.randint(2, 4), K=rng.randint(8, 14),
        T=rng.randint(1800, 3200), Dmax=rng.randint(6, 12))
    add("long", N=rng.randint(2, 4), K=rng.randint(8, 14),
        T=rng.randint(1800, 3200), Dmax=rng.randint(6, 12),
        m_lo=0.1, m_hi=0.3)
    N = rng.randint(2, 3)
    add("long", N=N, K=rng.randint(8, 14), T=rng.randint(1800, 3200),
        Dmax=rng.randint(8, 12), styles=[rng.choice(("peak", "bimodal"))
                                         for _ in range(N)])
    return cases


def _fmt_row(prefix, row):
    return prefix + " " + " ".join(repr(x) for x in row)


def to_text(cases):
    """Serialise cases to the shipped plain-text case format."""
    out = []
    for c in cases:
        out.append(f"CASE {c['id']}")
        out.append(f"N {c['N']} K {c['K']} T {c['T']} D {c['Dmax']}")
        out.append(f"SEED {c['seed']}")
        out.append(_fmt_row("PI", c["pi"]))
        for row in c["A"]:
            out.append(_fmt_row("A", row))
        for row in c["B"]:
            out.append(_fmt_row("B", row))
        for row in c["D"]:
            out.append(_fmt_row("D", row))
        out.append(_fmt_row("M", c["M"]))
        out.append("END")
        out.append("")
    return "\n".join(out) + "\n"
