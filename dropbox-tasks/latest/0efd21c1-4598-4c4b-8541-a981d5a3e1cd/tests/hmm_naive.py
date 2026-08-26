"""Plausible-but-wrong solvers the verifier discriminates against.

Two families of mistakes exist in this task, and the verifier exercises both.

Wrong SAMPLER conventions -- consumption-order mistakes that desync the whole
recording stream from the first point of divergence:

  sample_miss_first       -- takes the missingness draw before the symbol draw
                             (both still consumed every step).
  sample_miss_first_lazy  -- missingness draw first, symbol drawn only when
                             the entry is shown; every masked entry shifts the
                             rest of the stream.
  sample_fresh_start      -- no window-opening draws beyond the state: the
                             first visit starts at step 1 with a plain
                             duration draw.
  sample_no_lag           -- generates each entry from the state at its own
                             step.
  sample_per_step_hazard  -- redraws a hazard uniform at every occupied step
                             instead of drawing each visit's total duration
                             once.

Wrong LIKELIHOOD models -- the v3 family, evaluated on the true reference
recording:

  solve_case_fresh_start / solve_case_ignore_m / solve_case_no_lag /
  solve_case_textbook     -- textbook conventions instead of the reference's
                             (fresh start, MAR, no lag, and their composite).
  solve_case_memoryless   -- ordinary HMM forward-backward ignoring D.
  solve_obs_linear        -- the correct recursion carried in the raw
                             probability domain; underflows to -inf / NaN on
                             long recordings.

All share hmmref's parsing and machinery so the only differences are the
deliberate mistakes.
"""
import math

import hmmref
from hmmref import MISSING, NEG_INF, logsumexp2


# ---------------------------------------------------------- sampler ablations
def sample_miss_first(case):
    return hmmref.sample_recording(case, mode="miss_first")


def sample_miss_first_lazy(case):
    return hmmref.sample_recording(case, mode="miss_first_lazy")


def sample_fresh_start(case):
    return hmmref.sample_recording(case, residual_start=False)


def sample_no_lag(case):
    return hmmref.sample_recording(case, lag=False)


def sample_per_step_hazard(case):
    return hmmref.sample_recording(case, per_step_hazard=True)


# ------------------------------------------------------- likelihood ablations
def solve_case_fresh_start(case):
    return hmmref.solve_case(case, residual_start=False)


def solve_case_ignore_m(case):
    return hmmref.solve_case(case, use_m=False)


def solve_case_no_lag(case):
    return hmmref.solve_case(case, lag=False)


def solve_case_textbook(case):
    return hmmref.solve_case(case, residual_start=False, lag=False,
                             use_m=False)


def solve_case_memoryless(case):
    """Ordinary log-space HMM forward-backward that ignores D (and the
    recording quirks), on the case's reference recording."""
    N = case["N"]
    obs = hmmref.reference_obs(case)
    T = len(obs)
    log_pi = [hmmref._safe_log(p) for p in case["pi"]]
    log_A = [[hmmref._safe_log(x) for x in row] for row in case["A"]]
    log_B = [[hmmref._safe_log(x) for x in row] for row in case["B"]]

    def emis(t, i):
        return 0.0 if obs[t] == MISSING else log_B[i][obs[t]]

    la = [[NEG_INF] * N for _ in range(T)]
    for i in range(N):
        la[0][i] = log_pi[i] + emis(0, i)
    for t in range(1, T):
        for j in range(N):
            acc = NEG_INF
            for i in range(N):
                if la[t - 1][i] != NEG_INF and log_A[i][j] != NEG_INF:
                    acc = logsumexp2(acc, la[t - 1][i] + log_A[i][j])
            la[t][j] = acc + emis(t, j) if acc != NEG_INF else NEG_INF
    loglik = hmmref.logsumexp(la[T - 1])
    lb = [[NEG_INF] * N for _ in range(T)]
    for i in range(N):
        lb[T - 1][i] = 0.0
    for t in range(T - 2, -1, -1):
        for i in range(N):
            acc = NEG_INF
            for j in range(N):
                if log_A[i][j] != NEG_INF and lb[t + 1][j] != NEG_INF:
                    acc = logsumexp2(
                        acc, log_A[i][j] + emis(t + 1, j) + lb[t + 1][j])
            lb[t][i] = acc
    gamma = [[0.0] * N for _ in range(T)]
    for t in range(T):
        for i in range(N):
            v = la[t][i] + lb[t][i]
            gamma[t][i] = math.exp(v - loglik) if v != NEG_INF else 0.0
    # A's zero diagonal forces a change every step under this model
    nseg = float(T)
    return loglik, gamma, nseg


def solve_obs_linear(case, obs):
    """The correct reference semantics carried in the raw probability domain:
    the reference window opening, one-step lag, MNAR missingness, censoring --
    everything right except the arithmetic underflows on long recordings."""
    N, Dmax = case["N"], case["Dmax"]
    pi, A, B, D, M = (case["pi"], case["A"], case["B"], case["D"], case["M"])
    T = len(obs)
    surv = []
    mean = []
    for i in range(N):
        s = [0.0] * (Dmax + 2)
        acc = 0.0
        for d in range(Dmax, 0, -1):
            acc += D[i][d - 1]
            s[d] = acc
        surv.append(s)
        mean.append(sum(d * D[i][d - 1] for d in range(1, Dmax + 1)))
    h = [[0.0] * (Dmax + 1) for _ in range(N)]
    one_m_h = [[0.0] * (Dmax + 1) for _ in range(N)]
    for i in range(N):
        for u in range(1, Dmax + 1):
            if surv[i][u] > 0.0:
                h[i][u] = D[i][u - 1] / surv[i][u]
                one_m_h[i][u] = surv[i][u + 1] / surv[i][u]

    def rec(t, s):
        if obs[t] == MISSING:
            return M[s]
        return (1.0 - M[s]) * B[s][obs[t]]

    la = [[[0.0] * Dmax for _ in range(N)] for _ in range(T)]
    for i in range(N):
        e0 = rec(0, i)
        for u in range(1, Dmax + 1):
            la[0][i][u - 1] = pi[i] * surv[i][u] / mean[i] * e0
    for t in range(1, T):
        prev, cur = la[t - 1], la[t]
        ex = [rec(t, i) * sum(prev[i][u - 1] * h[i][u]
                              for u in range(1, Dmax + 1))
              for i in range(N)]
        for j in range(N):
            cur[j][0] = sum(ex[i] * A[i][j] for i in range(N))
            e_stay = rec(t, j)
            for u in range(1, Dmax):
                cur[j][u] = prev[j][u - 1] * one_m_h[j][u] * e_stay
    likelihood = sum(la[T - 1][i][u] for i in range(N) for u in range(Dmax))
    loglik = math.log(likelihood) if likelihood > 0.0 else NEG_INF

    lb = [[[0.0] * Dmax for _ in range(N)] for _ in range(T)]
    for i in range(N):
        for u in range(Dmax):
            lb[T - 1][i][u] = 1.0
    for t in range(T - 2, -1, -1):
        nxt, cur = lb[t + 1], lb[t]
        jumpc = [sum(A[i][j] * nxt[j][0] for j in range(N)) for i in range(N)]
        for i in range(N):
            e_i = rec(t + 1, i)
            for u in range(1, Dmax + 1):
                stay = (one_m_h[i][u] * e_i * nxt[i][u]
                        if u < Dmax else 0.0)
                cur[i][u - 1] = stay + h[i][u] * e_i * jumpc[i]

    gamma = [[0.0] * N for _ in range(T)]
    nseg = 1.0
    for t in range(T):
        denom = sum(la[t][i][u] * lb[t][i][u]
                    for i in range(N) for u in range(Dmax))
        for i in range(N):
            num = sum(la[t][i][u] * lb[t][i][u] for u in range(Dmax))
            gamma[t][i] = num / denom if denom > 0.0 else float("nan")
    for t in range(T - 1):
        ends = 0.0
        for i in range(N):
            ex = rec(t + 1, i) * sum(la[t][i][u - 1] * h[i][u]
                                     for u in range(1, Dmax + 1))
            ends += ex * sum(A[i][j] * lb[t + 1][j][0] for j in range(N))
        nseg += ends / likelihood if likelihood > 0.0 else float("nan")
    return loglik, gamma, nseg
