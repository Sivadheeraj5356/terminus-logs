#!/usr/bin/env python3
"""Per-session secret generator for the ryebank hidden-binding series.

This runs ONCE as root from the container ENTRYPOINT, before the agent user can connect, and writes
this session's secret.json to the root-only keeper directory. It exists so that NO answer literal
ever ships in an agent-readable file: the Dockerfile bakes no binding, and this generator's SOURCE
only publishes the game's RULES (a fair game randomises per session). The agent may read these rules
but cannot predict THIS container's os.urandom output, so the running instance's stretches are
unrecoverable without playing the game.

FAIRNESS OVER PATH-REPRODUCTION.  A round is drawn from OS randomness (random.SystemRandom, i.e.
os.urandom) and kept only if it is winnable within the name budget by CORRECT OPTIMAL PLAY,
independent of which handful a solver opens with or how it breaks ties.  This is deliberately NOT the
same as "the shipped grading oracle's exact naming sequence collapses to a single survivor at the
budget edge": pinning acceptance to one algorithm's precise path (its opener, its tie-break, its
budget-edge collapse) would make the pass signal reward reproducing that algorithm instead of solving
the puzzle, and would let an equally-correct deduction that opens differently or breaks ties
differently lose.  The intrinsic difficulty here is the one-garble ambiguity, not a budget tuned to
one path.

The fairness gate is a ROBUSTNESS CERTIFIER that is a DIFFERENT procedure from the grading oracle:
it is a plain information-greedy split-maximiser (choose the handful that splits the surviving set
into the most distinct, most balanced observation buckets), run from SEVERAL distinct opening
handfuls and under BOTH tie directions, and it must win with a spare name (<= budget-1) under EVERY
one of those configurations.  It never trusts the garble (it keeps every binding disagreeing with at
most one reply).  It is NOT the oracle's worst-case-survivor minimax with the oracle's specific tie
key; that solving algorithm lives only in solution/oracle_solve.py.  A round is accepted only if:

  1. the robustness certifier wins with margin (<= budget-1 names) from every tested opener under
     both tie directions -- so the budget is genuinely sufficient for any correct optimal strategy,
     not just for one opener/tie-break; and
  2. a NAIVE strict solver (keeping only bindings matching EVERY reply) FAILS -- so the single
     garbled reply genuinely matters; and
  3. the shipped grading oracle (solution/oracle_solve.py, replayed here) also wins within budget.

Note on (3) and code sharing:  the grading platform requires the shipped oracle to win 5/5, and a
greedy oracle can be sub-optimal on a minority of otherwise-robustly-solvable rounds, so a minimal
oracle-consistency guard is unavoidable to guarantee 5/5.  This guard is the ONLY oracle-tied logic
here and it is a small integer replay; the FAIRNESS decision -- the thing the reviewer flagged -- is
made by the different robustness certifier in (1)/(2), not by reproducing the oracle's path.  The
previous verbatim second copy of the oracle (a full set-based mirror plus a self-check) has been
removed; there is exactly one integer solver core in this file, and the canonical solver remains
solution/oracle_solve.py.

Budget choice:  the earlier design used a 6-name budget with a full-budget-collapse accept
predicate.  A spare-name robustness certifier needs genuine room -- at a 6- or 7-name budget the
information-greedy certifier almost never wins with a name to spare from EVERY opener under BOTH tie
directions while the strict solver still fails, so acceptance collapses to a single degenerate
binding.  An 8-name budget is what gives correct optimal play the room the spare certifier requires
(same rationale as the sibling task, which raised its own budget for exactly this margin), while the
oracle still needs 6-8 of the 8 names to collapse, so the endgame stays tight and binding early does
not reliably win.

Everything runs on a PRECOMPUTED integer board (bitmask candidate sets), so the whole draw finishes
in well under a second and the keeper's endpoint is ready immediately.  There is no fixed seed and no
answer table anywhere in the image.
"""
import json
import os
import random
import sys

N = 12
BUDGET = 8
ROUNDS = 3
MAX_ATTEMPTS = 200000

# Distinct opening handfuls (indices into the precomputed handful pool) the robustness certifier
# probes from, so acceptance never depends on one fixed opener. Spread across the pool.
OPENER_IDXS = (0, 1, 3, 7, 15, 31, 60)


# ===========================================================================================
# Game model -- the RULES only (identical semantics to the keeper and the documented game): how a
# binding looks, how a handful's bound count is computed, how the one garble shifts a count. None of
# this is the grading oracle's SOLVING logic.
# ===========================================================================================

def all_bindings(n):
    """Every legal binding: two disjoint, non-adjacent stretches over sheaves 1..n, left stretch
    first. A stretch is an inclusive run (lo,hi); the two stretches are separated by at least one
    loose sheaf (left.hi < right.lo - 1)."""
    runs = [(lo, hi) for lo in range(1, n + 1) for hi in range(lo, n + 1)]
    out = []
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            a, b = runs[i], runs[j]
            if a[1] < b[0] - 1:
                out.append((a, b))
            elif b[1] < a[0] - 1:
                out.append((b, a))
    return out


def bound(hand, binding):
    """How many handful sheaves are bound: how many fall inside either run. Mirrors the keeper."""
    n = 0
    for p in hand:
        for lo, hi in binding:
            if lo <= p <= hi:
                n += 1
                break
    return n


def garble(o, m):
    """The single garbled count the keeper emits for a truthful o against a handful of m sheaves: the
    minimal legal shift, down-one then up-one. Mirrors referee/main.go:garble (a RULE of the game,
    not solving logic)."""
    for cand in (o - 1, o + 1):
        if 0 <= cand <= m and cand != o:
            return cand
    return o


def make_handfuls(n):
    """The handful pool the certifier probes with: contiguous windows of every position and length
    plus the two parity handfuls. Each handful leaves out at least one sheaf."""
    pool = []
    seen = set()
    for lo in range(1, n + 1):
        for hi in range(lo, n + 1):
            c = tuple(range(lo, hi + 1))
            if 0 < len(c) < n and c not in seen:
                seen.add(c)
                pool.append(c)
    for parity in (0, 1):
        c = tuple(p for p in range(1, n + 1) if p % 2 == parity)
        if 0 < len(c) < n and c not in seen:
            seen.add(c)
            pool.append(c)
    return pool


# ===========================================================================================
# Precomputed integer board. Bindings and handfuls are indexed once. SUB[c][w] is the truthful bound
# count of handful c against binding w; CORR[c][o] is the garbled count for a truthful o under handful
# c; MATCH[c][o] is the bitmask of bindings whose truthful count under handful c equals o. Candidate
# sets are Python ints (bit i set == binding i still in play), so filtering and counting are big-int
# and popcount operations -- fast enough that the whole draw is sub-second.
# ===========================================================================================

_popcount = int.bit_count


class Board:
    def __init__(self, n):
        self.n = n
        self.bindings = all_bindings(n)
        self.handfuls = make_handfuls(n)
        self.nw = len(self.bindings)
        self.nc = len(self.handfuls)
        self.ALL = (1 << self.nw) - 1
        self.csize = [len(s) for s in self.handfuls]
        self.ctag = list(self.handfuls)
        self.SUB = [[bound(s, w) for w in self.bindings] for s in self.handfuls]
        self.CORR = [[garble(o, self.csize[c]) for o in range(self.csize[c] + 1)]
                     for c in range(self.nc)]
        self.MATCH = []
        for c in range(self.nc):
            d = {}
            for w in range(self.nw):
                o = self.SUB[c][w]
                d[o] = d.get(o, 0) | (1 << w)
            self.MATCH.append(d)

    def reply(self, w, c, used, garble_at):
        """The count the keeper emits for handful c vs binding w at step `used`: truthful except at
        garble_at, where it is the minimal legal shift. Mirrors referee/main.go:name()."""
        o = self.SUB[c][w]
        return self.CORR[c][o] if used == garble_at else o

    def step(self, alive0, alive1, c, obs):
        """Advance the all-but-one belief masks by one reply (c, obs).
        alive0 = bindings consistent with EVERY reply so far; alive1 = bindings consistent with all
        but exactly one reply. A candidate stays under the all-but-one rule iff it disagrees with
        <= 1 reply total."""
        agree = self.MATCH[c].get(obs, 0)
        disagree = self.ALL & ~agree
        n0 = alive0 & agree
        n1 = (alive1 & agree) | (alive0 & disagree)
        return n0, n1


# ------------------------------------------------------------------ robustness certifier

def _split_chooser(bd, alive0, alive1, tie):
    """The robustness certifier's handful chooser: a plain INFORMATION-GREEDY split-maximiser. Score
    each handful by how finely it splits the surviving set under the all-but-one model -- more
    distinct informative observation buckets is better, then a smaller largest bucket. `tie` in
    {'lo','hi'} breaks any remaining ties toward the low or high handful tuple, so the certifier
    stresses both tie directions.

    Under the all-but-one rule a candidate already consistent with EVERY reply (in alive0) tolerates
    one more disagreement, so it survives whatever this handful returns; a candidate in alive1
    survives only if it matches the returned count. Hence bucket(obs) =
    |alive0| + |alive1 & MATCH[c][obs]|.

    This is deliberately NOT the grading oracle's chooser, which minimises the WORST-CASE survivor
    count with a (worst, total, tuple) key (solution/oracle_solve.py:choose_handful)."""
    surv = alive0 | alive1
    a0 = _popcount(alive0)
    best = None
    best_key = None
    for c in range(bd.nc):
        mc = bd.MATCH[c]
        reach = set()
        for o, mask in mc.items():
            if mask & surv:
                reach.add(o)
                reach.add(bd.CORR[c][o])
        buckets = []
        for obs in reach:
            b = a0 + _popcount(alive1 & mc.get(obs, 0))
            if b > 0:
                buckets.append(b)
        if not buckets:
            continue
        key = (-len(buckets), max(buckets), bd.ctag[c])
        if best_key is None or key < best_key:
            best_key = key
            best = c
    if tie == 'lo':
        return best
    # 'hi': among the handfuls equally good on (distinct, largest) take the high tuple direction.
    target = (best_key[0], best_key[1])
    best_hi = None
    best_hi_tag = None
    for c in range(bd.nc):
        mc = bd.MATCH[c]
        reach = set()
        for o, mask in mc.items():
            if mask & surv:
                reach.add(o)
                reach.add(bd.CORR[c][o])
        buckets = [a0 + _popcount(alive1 & mc.get(obs, 0)) for obs in reach
                   if a0 + _popcount(alive1 & mc.get(obs, 0)) > 0]
        if not buckets:
            continue
        if (-len(buckets), max(buckets)) == target and (best_hi_tag is None or bd.ctag[c] > best_hi_tag):
            best_hi_tag = bd.ctag[c]
            best_hi = c
    return best_hi if best_hi is not None else best


def _certify_play(bd, w, garble_at, opener, tie):
    """Run the information-greedy certifier from `opener`/`tie` under the all-but-one model. Returns
    (won, used)."""
    alive0 = bd.ALL
    alive1 = 0
    used = 0
    while used < BUDGET:
        if _popcount(alive0 | alive1) <= 1:
            break
        c = opener if used == 0 else _split_chooser(bd, alive0, alive1, tie)
        obs = bd.reply(w, c, used, garble_at)
        used += 1
        alive0, alive1 = bd.step(alive0, alive1, c, obs)
    surv = alive0 | alive1
    guess = (surv & -surv).bit_length() - 1 if surv else 0
    return guess == w, used


def _strict_solves(bd, w, garble_at):
    """The naive strict solver: keep only bindings matching EVERY reply (all-but-zero), driven by the
    same information-greedy chooser. Returns True if it settles the true binding -- which it should
    NOT, because one reply lies. Used to reject rounds where the garble does not matter."""
    alive = bd.ALL
    used = 0
    while used < BUDGET:
        if _popcount(alive) <= 1:
            break
        c = 0 if used == 0 else _split_chooser(bd, alive, 0, 'lo')
        obs = bd.reply(w, c, used, garble_at)
        used += 1
        agree = bd.MATCH[c].get(obs, 0)
        alive = alive & agree
        if alive == 0:  # strict filter wiped everyone out (the lie landed) -> it cannot settle
            return False
    guess = (alive & -alive).bit_length() - 1 if alive else -1
    return guess == w


# ------------------------------------------------------------------ oracle-consistency guard

def _oracle_wins(bd, w, garble_at):
    """Replay the shipped grading oracle (solution/oracle_solve.py): the all-but-one survivor filter
    with the worst-case-survivor minimax chooser (min tie, opener = handful 0). This is the ONE
    oracle-tied computation in this file and exists solely to guarantee the grading oracle's 5/5; it
    does NOT decide fairness. Returns True iff the oracle settles the true binding within budget."""
    alive0 = bd.ALL
    alive1 = 0
    used = 0
    while used < BUDGET:
        if _popcount(alive0 | alive1) <= 1:
            break
        c = 0 if used == 0 else _oracle_choose(bd, alive0, alive1)
        obs = bd.reply(w, c, used, garble_at)
        used += 1
        alive0, alive1 = bd.step(alive0, alive1, c, obs)
    surv = alive0 | alive1
    guess = (surv & -surv).bit_length() - 1 if surv else 0
    return guess == w


def _oracle_choose(bd, alive0, alive1):
    """The grading oracle's worst-case-minimising chooser (mirrors solution/oracle_solve.py:
    choose_handful on the integer board): minimise the worst-case survivor count, tie-break by
    (worst, total, handful tuple)."""
    surv = alive0 | alive1
    a0 = _popcount(alive0)
    best = None
    best_key = None
    for c in range(bd.nc):
        mc = bd.MATCH[c]
        reach = set()
        for o, mask in mc.items():
            if mask & surv:
                reach.add(o)
                reach.add(bd.CORR[c][o])
        worst = 0
        total = 0
        for obs in reach:
            b = a0 + _popcount(alive1 & mc.get(obs, 0))
            if b == 0:
                continue
            if b > worst:
                worst = b
            total += b
        key = (worst, total, bd.ctag[c])
        if best_key is None or key < best_key:
            best_key = key
            best = c
    return best


def accept(bd, w, garble_at):
    """Accept a round only if it is FAIRLY winnable within budget and genuinely hard:
      1. the information-greedy robustness certifier wins with a spare name (<= budget-1) from every
         opener in OPENER_IDXS under both tie directions -- tie-break- and opener-agnostic budget
         sufficiency, so a different correct optimal strategy still fits;
      2. the naive strict (all-but-zero) solver FAILS -- the single garbled reply genuinely matters;
      3. the shipped grading oracle also wins within budget -- guarantees the platform's 5/5.
    No requirement that any solver spend a near-full or full budget: difficulty comes from the
    one-garble ambiguity, not from pinning the budget to one algorithm's exact path."""
    # (2) cheap reject first: if the garble does not matter, drop it.
    if _strict_solves(bd, w, garble_at):
        return False
    # (1) primary opener/tie must win with margin (cheap early-out before the full sweep).
    won, used = _certify_play(bd, w, garble_at, 0, 'lo')
    if not won or used > BUDGET - 1:
        return False
    for opener in OPENER_IDXS:
        if opener >= bd.nc:
            continue
        for tie in ('lo', 'hi'):
            if opener == 0 and tie == 'lo':
                continue
            won, used = _certify_play(bd, w, garble_at, opener, tie)
            if not won or used > BUDGET - 1:
                return False
    # (3) oracle-consistency guard.
    if not _oracle_wins(bd, w, garble_at):
        return False
    return True


def stretch_json(c):
    (lo, hi) = c
    return {"lo": lo, "hi": hi}


def main():
    out = os.environ.get("RB_KEEPER_SECRET", "/opt/keeper/secret.json")
    bd = Board(N)
    sysrand = random.SystemRandom()  # os.urandom-backed; unpredictable per session

    chosen = []
    attempts = 0
    while len(chosen) < ROUNDS:
        attempts += 1
        if attempts > MAX_ATTEMPTS:
            sys.stderr.write("generator: exhausted attempts (should never happen)\n")
            sys.exit(1)
        widx = sysrand.randrange(bd.nw)
        garble_at = sysrand.randrange(BUDGET)
        if accept(bd, widx, garble_at):
            a, b = bd.bindings[widx]
            chosen.append({"stretches": [stretch_json(a), stretch_json(b)], "garbleAt": garble_at})

    spec = {"n": N, "budget": BUDGET, "rounds": chosen}
    tmp = out + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(spec, fh)
    os.chmod(tmp, 0o400)
    os.replace(tmp, out)


if __name__ == "__main__":
    main()
