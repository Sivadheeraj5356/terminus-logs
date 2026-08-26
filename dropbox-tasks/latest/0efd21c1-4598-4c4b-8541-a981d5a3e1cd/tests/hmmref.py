"""Independent, standard-library-only reference for the duration-explicit
(semi-Markov) recording-replay task.

This module is not visible to the agent. It parses the case format used by the
task (model parameters plus a SEED, no recording), then computes, for each
case, the exact recording the reference process emits for that seed, the
log-likelihood of that recording, the smoothed posteriors, and the expected
number of visits the window intersects, exactly under the reference semantics
that the agent-visible probe binary /app/ref implements.

The sampler consumes uniforms from the documented splitmix64 stream, seeded
per case from the SEED value. What consumes a draw, and in what order, is the
hidden part of the contract; the reference conventions are:

  - window open: one draw picks the opening state from pi (categorical scan in
    index order, first i with u < cumulative sum); one draw picks the elapsed
    dwell u of the visit already in progress from the residual-life law
    P(u | i) = S_i(u) / mean_i with S_i(u) = sum_{d>=u} D_i(d); one draw picks
    that visit's total duration d from the conditional law D_i(d) / S_i(u) on
    d = u..Dmax;
  - dwell: no draws while a visit runs; at each visit end one draw picks the
    next state from the A row, then one draw picks the new visit's total
    duration from the D row;
  - recording at each step: the symbol draw is taken FIRST and ALWAYS, from
    the B row of the generating state (the state at t-1 for t >= 2, the state
    at step 1 for t = 1 -- the apparatus lags one step); THEN the missingness
    draw is taken, and the entry is '?' iff that uniform is < m_s of the same
    generating state. A masked entry still consumed its symbol draw; the
    symbol is discarded.

The distribution over recordings this induces is exactly the model the
likelihood machinery below evaluates: residual-life window opening, one-step
recording lag, state-dependent missingness ('?' contributes m_s, a recorded
symbol k contributes (1-m_s) * B_s(k)), and right censoring at T. The
likelihood computation runs on the dwell-augmented chain (state,
steps-spent-so-far) with the per-dwell exit hazard h_i(u) = D_i(u) / S_i(u);
the recording factor of step t+1 attaches to the source state of the
transition from t to t+1, which realises the lag exactly. All accumulation is
in log space with a hand-written log-sum-exp so it stays finite for
arbitrarily long recordings. Correctness of the likelihood was cross-checked
during authoring against a direct brute-force enumeration over all augmented
state paths on small cases (loglik, every gamma, and the expected visit count
agree to < 1e-10); the Go oracle, the probe binary, and this sampler were
cross-checked draw-for-draw and byte-for-byte.
"""
import math

NEG_INF = float("-inf")
MISSING = -1

MASK64 = (1 << 64) - 1


class SplitMix64:
    """The documented uniform stream: splitmix64, u = (x >> 11) * 2**-53."""

    def __init__(self, seed):
        self.z = seed & MASK64

    def next_u64(self):
        self.z = (self.z + 0x9E3779B97F4A7C15) & MASK64
        x = self.z
        x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & MASK64
        return x ^ (x >> 31)

    def uniform(self):
        return (self.next_u64() >> 11) * (2.0 ** -53)


def _pick(u, weights):
    """Categorical scan in index order: first i with u < cumulative sum."""
    acc = 0.0
    for i, w in enumerate(weights):
        acc += w
        if u < acc:
            return i
    return len(weights) - 1


def _survivor(D_row, Dmax):
    s = [0.0] * (Dmax + 2)
    acc = 0.0
    for d in range(Dmax, 0, -1):
        acc += D_row[d - 1]
        s[d] = acc
    return s


def sample_recording(case, mode="ref", residual_start=True, lag=True,
                     per_step_hazard=False):
    """Emit the exact recording the reference process produces for the case's
    SEED. `mode` and the flags exist only so the verifier can realise
    plausible-but-wrong consumption conventions; the defaults are the
    reference semantics.

    mode: "ref"             symbol draw first and always, then missing draw
          "miss_first"      missing draw first, symbol draw still always taken
          "miss_first_lazy" missing draw first, symbol drawn only when shown
    """
    N, Dmax, T = case["N"], case["Dmax"], case["T"]
    pi, A, B, D, M = case["pi"], case["A"], case["B"], case["D"], case["M"]
    rng = SplitMix64(case["seed"])
    surv = [_survivor(D[i], Dmax) for i in range(N)]
    mean = [sum(d * D[i][d - 1] for d in range(1, Dmax + 1))
            for i in range(N)]

    state = _pick(rng.uniform(), pi)
    remaining = 0
    if per_step_hazard:
        pass  # the naive per-step sampler takes no duration draws at all
    elif residual_start:
        offw = [surv[state][u] / mean[state] for u in range(1, Dmax + 1)]
        elapsed = _pick(rng.uniform(), offw) + 1
        condw = [0.0] * Dmax
        for d in range(elapsed, Dmax + 1):
            condw[d - 1] = D[state][d - 1] / surv[state][elapsed]
        total = _pick(rng.uniform(), condw) + 1
        remaining = total - elapsed + 1
    else:
        remaining = _pick(rng.uniform(), D[state]) + 1

    states = []
    if per_step_hazard:
        dwell = 1
        for _ in range(T):
            states.append(state)
            h = (D[state][dwell - 1] / surv[state][dwell]
                 if surv[state][dwell] > 0 else 1.0)
            if rng.uniform() < h:
                state = _pick(rng.uniform(), A[state])
                dwell = 1
            else:
                dwell += 1
    else:
        for _ in range(T):
            states.append(state)
            remaining -= 1
            if remaining == 0:
                state = _pick(rng.uniform(), A[state])
                remaining = _pick(rng.uniform(), D[state]) + 1

    obs = []
    for t in range(T):
        s = states[t - 1] if (lag and t >= 1) else states[t]
        if mode == "ref":
            k = _pick(rng.uniform(), B[s])
            miss = rng.uniform() < M[s]
            obs.append(MISSING if miss else k)
        elif mode == "miss_first":
            miss = rng.uniform() < M[s]
            k = _pick(rng.uniform(), B[s])
            obs.append(MISSING if miss else k)
        else:  # miss_first_lazy
            miss = rng.uniform() < M[s]
            if miss:
                obs.append(MISSING)
            else:
                obs.append(_pick(rng.uniform(), B[s]))
    return obs


def logsumexp2(a, b):
    if a == NEG_INF:
        return b
    if b == NEG_INF:
        return a
    if a < b:
        a, b = b, a
    return a + math.log1p(math.exp(b - a))


def logsumexp(xs):
    xs = list(xs)
    m = NEG_INF
    for x in xs:
        if x > m:
            m = x
    if m == NEG_INF:
        return NEG_INF
    s = 0.0
    for x in xs:
        s += math.exp(x - m)
    return m + math.log(s)


def _safe_log(x):
    if x <= 0.0:
        return NEG_INF
    return math.log(x)


class RecordingModel:
    """Exact smoothing under the reference recording semantics."""

    def __init__(self, N, K, Dmax, pi, A, B, D, M,
                 residual_start=True, lag=True, use_m=True):
        self.N = N
        self.K = K
        self.Dmax = Dmax
        self.log_A = [[_safe_log(A[i][j]) for j in range(N)] for i in range(N)]
        self.log_B = [[_safe_log(B[i][k]) for k in range(K)] for i in range(N)]
        self.M = list(M)
        self.use_m = use_m
        self.lag = lag
        # survivor mass S_i(u), hazards, and the start distribution over the
        # augmented states (i, u)
        self.log_h = [[NEG_INF] * (Dmax + 1) for _ in range(N)]
        self.log_1mh = [[NEG_INF] * (Dmax + 1) for _ in range(N)]
        self.log_start = [[NEG_INF] * Dmax for _ in range(N)]
        for i in range(N):
            surv = 0.0
            svals = [0.0] * (Dmax + 2)
            for d in range(Dmax, 0, -1):
                surv += D[i][d - 1]
                svals[d] = surv
            mean_i = 0.0
            for d in range(1, Dmax + 1):
                mean_i += d * D[i][d - 1]
            for u in range(1, Dmax + 1):
                s_u = svals[u]
                if s_u <= 0.0:
                    continue
                self.log_h[i][u] = _safe_log(D[i][u - 1] / s_u)
                self.log_1mh[i][u] = _safe_log(svals[u + 1] / s_u)
            lp = _safe_log(pi[i])
            if residual_start:
                for u in range(1, Dmax + 1):
                    if svals[u] > 0.0:
                        self.log_start[i][u - 1] = lp + _safe_log(
                            svals[u] / mean_i)
            else:
                self.log_start[i][0] = lp

    def _rec(self, sym, s):
        """Log factor of one recorded entry generated by state s."""
        m = self.M[s] if self.use_m else 0.0
        if sym == MISSING:
            return _safe_log(m) if self.use_m else 0.0
        base = self.log_B[s][sym]
        if self.use_m:
            return _safe_log(1.0 - m) + base
        return base

    def _src(self, obs, t):
        """Index of the step whose state generates the entry recorded at t."""
        if self.lag and t >= 1:
            return t - 1
        return t

    def solve(self, obs):
        """Return (loglik, gamma, nseg) under the reference semantics."""
        N, Dmax = self.N, self.Dmax
        T = len(obs)
        # forward over augmented states (i, dwell u); the factor of the entry
        # recorded at step t+1 attaches to the state at self._src(obs, t+1),
        # which is the transition's source state when the lag is on
        la = [[[NEG_INF] * Dmax for _ in range(N)] for _ in range(T)]
        for i in range(N):
            e0 = self._rec(obs[0], i)
            for u in range(Dmax):
                v = self.log_start[i][u]
                if v != NEG_INF:
                    la[0][i][u] = v + e0
        for t in range(1, T):
            prev = la[t - 1]
            cur = la[t]
            # fold the step-t recording factor onto the transition; under the
            # lag it depends on the source state, otherwise on the target
            exit_i = [NEG_INF] * N
            for i in range(N):
                lh = self.log_h[i]
                row = prev[i]
                e_src = self._rec(obs[t], i) if self.lag else 0.0
                acc = NEG_INF
                for u in range(1, Dmax + 1):
                    v = row[u - 1]
                    if v != NEG_INF and lh[u] != NEG_INF:
                        acc = logsumexp2(acc, v + lh[u])
                if acc != NEG_INF:
                    exit_i[i] = acc + e_src
            for j in range(N):
                e_tgt = 0.0 if self.lag else self._rec(obs[t], j)
                acc = NEG_INF
                for i in range(N):
                    if exit_i[i] != NEG_INF and self.log_A[i][j] != NEG_INF:
                        acc = logsumexp2(acc, exit_i[i] + self.log_A[i][j])
                if acc != NEG_INF:
                    cur[j][0] = acc + e_tgt
                l1mh = self.log_1mh[j]
                row = prev[j]
                e_stay = self._rec(obs[t], j)
                for u in range(1, Dmax):
                    v = row[u - 1]
                    if v != NEG_INF and l1mh[u] != NEG_INF:
                        cur[j][u] = v + l1mh[u] + e_stay
        loglik = logsumexp(
            la[T - 1][i][u] for i in range(N) for u in range(Dmax))

        # backward: lb[t][(i,u)] = log P(recording after t | state (i,u) at t)
        lb = [[[NEG_INF] * Dmax for _ in range(N)] for _ in range(T)]
        for i in range(N):
            for u in range(Dmax):
                lb[T - 1][i][u] = 0.0
        for t in range(T - 2, -1, -1):
            nxt = lb[t + 1]
            cur = lb[t]
            # value of entering a fresh visit to j at t+1
            entry = [NEG_INF] * N
            for j in range(N):
                v = nxt[j][0]
                if v == NEG_INF:
                    continue
                entry[j] = v if self.lag else v + self._rec(obs[t + 1], j)
            jumpc = [NEG_INF] * N
            for i in range(N):
                acc = NEG_INF
                for j in range(N):
                    if entry[j] != NEG_INF and self.log_A[i][j] != NEG_INF:
                        acc = logsumexp2(acc, self.log_A[i][j] + entry[j])
                jumpc[i] = acc
            for i in range(N):
                lh = self.log_h[i]
                l1mh = self.log_1mh[i]
                e_i = self._rec(obs[t + 1], i)
                for u in range(1, Dmax + 1):
                    stay = NEG_INF
                    if u < Dmax and l1mh[u] != NEG_INF:
                        v = nxt[i][u]
                        if v != NEG_INF:
                            stay = l1mh[u] + e_i + v
                    jump = NEG_INF
                    if lh[u] != NEG_INF and jumpc[i] != NEG_INF:
                        jump = lh[u] + jumpc[i]
                        if self.lag:
                            jump += e_i
                    cur[i][u - 1] = logsumexp2(stay, jump)

        gamma = [[0.0] * N for _ in range(T)]
        for t in range(T):
            for i in range(N):
                acc = NEG_INF
                for u in range(Dmax):
                    va = la[t][i][u]
                    vb = lb[t][i][u]
                    if va != NEG_INF and vb != NEG_INF:
                        acc = logsumexp2(acc, va + vb)
                gamma[t][i] = math.exp(acc - loglik) if acc != NEG_INF else 0.0

        # expected visits intersecting the window: 1 + expected boundaries
        nseg = 1.0
        for t in range(T - 1):
            nxt = lb[t + 1]
            entry = [NEG_INF] * N
            for j in range(N):
                v = nxt[j][0]
                if v == NEG_INF:
                    continue
                entry[j] = v if self.lag else v + self._rec(obs[t + 1], j)
            acc = NEG_INF
            for i in range(N):
                lh = self.log_h[i]
                row = la[t][i]
                e_src = self._rec(obs[t + 1], i) if self.lag else 0.0
                ex = NEG_INF
                for u in range(1, self.Dmax + 1):
                    v = row[u - 1]
                    if v != NEG_INF and lh[u] != NEG_INF:
                        ex = logsumexp2(ex, v + lh[u])
                if ex == NEG_INF:
                    continue
                ex += e_src
                for j in range(N):
                    if entry[j] != NEG_INF and self.log_A[i][j] != NEG_INF:
                        acc = logsumexp2(acc, ex + self.log_A[i][j] + entry[j])
            if acc != NEG_INF:
                nseg += math.exp(acc - loglik)
        return loglik, gamma, nseg




# ------------------------------------------------------------------ case format
def parse_cases(path):
    with open(path, encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f]
    return parse_cases_lines(lines)


def parse_cases_lines(lines):
    """Parse the plain-text case format.

    Format (blank lines and lines starting with '#' are ignored):

        CASE <id>
        N <n> K <k> T <t> D <dmax>
        SEED <u64>
        PI <p0> ... <p_{N-1}>
        A <n rows of n values, one row per line, prefixed 'A'>
        B <n rows of k values, one row per line, prefixed 'B'>
        D <n rows of dmax values, one row per line, prefixed 'D'>
        M <n values>
        END
    """
    cases = []
    i = 0
    n = len(lines)

    def skip_blank(i):
        while lines[i].strip() == "" or lines[i].strip().startswith("#"):
            i += 1
        return i

    while i < n:
        line = lines[i].strip()
        if not line or line.startswith("#"):
            i += 1
            continue
        if not line.startswith("CASE"):
            raise ValueError(f"expected CASE header, got {line!r}")
        cid = line.split(None, 1)[1].strip()
        i = skip_blank(i + 1)
        dims = lines[i].split()
        assert dims[0] == "N" and dims[2] == "K" and dims[4] == "T" \
            and dims[6] == "D", f"bad dims line {lines[i]!r}"
        N = int(dims[1])
        K = int(dims[3])
        T = int(dims[5])
        Dmax = int(dims[7])
        i = skip_blank(i + 1)
        s_toks = lines[i].split()
        assert s_toks[0] == "SEED", f"expected SEED, got {lines[i]!r}"
        seed = int(s_toks[1])
        i = skip_blank(i + 1)
        pi_toks = lines[i].split()
        assert pi_toks[0] == "PI"
        pi = [float(x) for x in pi_toks[1:]]
        assert len(pi) == N
        i += 1
        A = []
        while len(A) < N:
            i = skip_blank(i)
            toks = lines[i].split()
            assert toks[0] == "A", f"expected A row, got {lines[i]!r}"
            row = [float(x) for x in toks[1:]]
            assert len(row) == N
            A.append(row)
            i += 1
        B = []
        while len(B) < N:
            i = skip_blank(i)
            toks = lines[i].split()
            assert toks[0] == "B", f"expected B row, got {lines[i]!r}"
            row = [float(x) for x in toks[1:]]
            assert len(row) == K
            B.append(row)
            i += 1
        D = []
        while len(D) < N:
            i = skip_blank(i)
            toks = lines[i].split()
            assert toks[0] == "D", f"expected D row, got {lines[i]!r}"
            row = [float(x) for x in toks[1:]]
            assert len(row) == Dmax
            D.append(row)
            i += 1
        i = skip_blank(i)
        m_toks = lines[i].split()
        assert m_toks[0] == "M", f"expected M row, got {lines[i]!r}"
        M = [float(x) for x in m_toks[1:]]
        assert len(M) == N
        i = skip_blank(i + 1)
        assert lines[i].strip() == "END", f"expected END, got {lines[i]!r}"
        i += 1
        cases.append({"id": cid, "N": N, "K": K, "T": T, "Dmax": Dmax,
                      "seed": seed, "pi": pi, "A": A, "B": B, "D": D, "M": M})
    return cases


_OBS_CACHE = {}
_CACHE = {}


def reference_obs(case):
    """Memoised exact recording for the case's seed."""
    key = (case["id"], case["seed"])
    hit = _OBS_CACHE.get(key)
    if hit is None:
        hit = sample_recording(case)
        _OBS_CACHE[key] = hit
    return hit


def solve_obs(case, obs, **kw):
    """Memoised exact (loglik, gamma, nseg) for an explicit recording."""
    key = (case["id"], tuple(obs), tuple(sorted(kw.items())))
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    m = RecordingModel(case["N"], case["K"], case["Dmax"], case["pi"],
                       case["A"], case["B"], case["D"], case["M"], **kw)
    res = m.solve(obs)
    _CACHE[key] = res
    return res


def solve_case(case, **kw):
    """Exact (loglik, gamma, nseg) of the case's own reference recording."""
    return solve_obs(case, reference_obs(case), **kw)
