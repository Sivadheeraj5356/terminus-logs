"""Regenerates the committed instance, the hidden instances and their optima.

Ground truth is computed here in CP-SAT, independently of any MiniZinc model.

Readings that the data and the accounting deliberately make wrong:

* Passengers are not dispatched. A flow that has a comfortable connection open
  to it rides one that leaves as soon as any of them does, and it cannot be held
  back to free seats for somebody heavier. So the boarding is a FUNCTION of the
  offsets, not a choice. Letting the planner pick who boards what is a strict
  relaxation on both counts, and the plans it likes overload a bus.
* WK lists only the passages that run DIRECTLY between two platforms, and the
  concourse is not metric. What a passenger actually spends is the min-plus
  closure of that table. A model that indexes WK mistimes its connections.
* A bus has seats, so the only way to keep one from overloading is to choose
  offsets that make a connection uncomfortable in the first place.

A seed is only accepted when every wrong reading is beaten under the pin trick:
pin the wrong model at its own optimum, then maximise the TRUE score across its
entire optimal set. Even the wrong model's most favourable plan must still lose.
"""

import os
import random

from ortools.sat.python import cp_model

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.normpath(os.path.join(HERE, "..", "..", "environment"))

MINW = 1
MAXW = 3
P = 6
HUB_A, HUB_B = 0, 1
NEAR = {HUB_A: [2, 3], HUB_B: [4, 5]}


def closure(WK):
    D = [row[:] for row in WK]
    for k in range(P):
        for i in range(P):
            for j in range(P):
                if D[i][k] + D[k][j] < D[i][j]:
                    D[i][j] = D[i][k] + D[k][j]
    return D


def make_instance(seed, L, H, F, groups, gap, direct, hub, fat, seatfrac, trunk):
    rng = random.Random(seed)
    WK = [[0] * P for _ in range(P)]
    for i in range(P):
        for j in range(i + 1, P):
            WK[i][j] = WK[j][i] = rng.randint(*direct)

    def setw(i, j, v):
        WK[i][j] = WK[j][i] = v

    setw(HUB_A, HUB_B, rng.randint(*hub))
    for h in (HUB_A, HUB_B):
        for p in NEAR[h]:
            setw(h, p, rng.randint(*hub))
    D = closure(WK)

    side = [rng.random() < 0.5 for _ in range(L)]
    arr = [rng.randint(0, H - 1) for _ in range(L)]
    dep = [rng.randint(0, H - 1) for _ in range(L)]
    ap, dp = [], []
    for line in range(L):
        ap.append(rng.choice(NEAR[HUB_A] if side[line] else NEAR[HUB_B]))
        if rng.random() < 0.8:
            dp.append(rng.choice(NEAR[HUB_B] if side[line] else NEAR[HUB_A]))
        else:
            dp.append(rng.randrange(P))

    pull = [trunk if line < 2 else 1 for line in range(L)]
    fline, cline, w, flow = [], [], [], []
    for g in range(1, F + 1):
        a = rng.randint(1, L)
        gw = rng.randint(10, 14) if rng.random() < fat else rng.randint(2, 8)
        picked = set()
        for _ in range(min(rng.randint(2, 3), L - 1)):
            cand = [b for b in range(1, L + 1) if b != a and b not in picked]
            b = rng.choices(cand, weights=[pull[c - 1] for c in cand])[0]
            picked.add(b)
            fline.append(a)
            cline.append(b)
            w.append(gw)
            flow.append(g)

    demand = [0] * L
    for t in range(len(w)):
        demand[cline[t] - 1] += w[t]
    seats = [max(6, min(24, round(seatfrac * demand[b]))) for b in range(L)]

    terminus = [0] * L
    for gi, grp in enumerate(groups):
        for ln in grp:
            terminus[ln - 1] = gi + 1

    return dict(
        L=L,
        H=H,
        F=F,
        T=len(w),
        GAP=gap,
        terminus=terminus,
        fline=fline,
        cline=cline,
        w=w,
        flow=flow,
        arr=arr,
        ap=ap,
        dep=dep,
        dp=dp,
        seats=seats,
        WK=WK,
        D=D,
    )


def cyclic_dist(a, b, H):
    d = abs(a - b) % H
    return min(d, H - d)


def sep_ok(x, inst):
    for i in range(inst["L"]):
        for j in range(i + 1, inst["L"]):
            if inst["terminus"][i] == inst["terminus"][j]:
                if cyclic_dist(x[i], x[j], inst["H"]) < inst["GAP"]:
                    return False
    return True


def waits_of(x, inst, table):
    """The cyclic wait each row leaves its passengers, given the offsets."""
    H = inst["H"]
    out = []
    for t in range(inst["T"]):
        a, b = inst["fline"][t] - 1, inst["cline"][t] - 1
        out.append(
            (
                x[b]
                + inst["dep"][b]
                - x[a]
                - inst["arr"][a]
                - table[inst["ap"][a]][inst["dp"][b]]
            )
            % H
        )
    return out


def score(x, board, inst):
    """The verifier's own rule, in pure Python. The offsets must be spaced. A
    flow with a comfortable connection open to it rides exactly one of them, and
    the one it rides must leave as soon as any of them does; a flow with none
    rides nothing. No bus lifts more than its seats. None for an illegal plan."""
    if not sep_ok(x, inst):
        return None
    wait = waits_of(x, inst, inst["D"])
    ok = [MINW <= wt <= MAXW for wt in wait]
    for t in range(inst["T"]):
        if board[t] and not ok[t]:
            return None
    for g in range(1, inst["F"] + 1):
        idx = [t for t in range(inst["T"]) if inst["flow"][t] == g]
        usable = [t for t in idx if ok[t]]
        taken = [t for t in idx if board[t]]
        if not usable:
            if taken:
                return None
            continue
        if len(taken) != 1:
            return None
        if wait[taken[0]] != min(wait[t] for t in usable):
            return None
    seated = [0] * inst["L"]
    for t in range(inst["T"]):
        if board[t]:
            seated[inst["cline"][t] - 1] += inst["w"][t]
    if any(seated[b] > inst["seats"][b] for b in range(inst["L"])):
        return None
    return sum(inst["w"][t] for t in range(inst["T"]) if board[t])


def _sep(m, x, inst):
    H = inst["H"]
    for i in range(inst["L"]):
        for j in range(i + 1, inst["L"]):
            if inst["terminus"][i] != inst["terminus"][j]:
                continue
            d = m.NewIntVar(0, H - 1, "")
            k = m.NewIntVar(-1, 1, "")
            m.Add(x[i] - x[j] == d + k * H)
            c = m.NewIntVar(0, H, "")
            m.AddMinEquality(c, [d, H - d])
            m.Add(c >= inst["GAP"])


def _comfort(m, x, inst, table, wrap=True):
    H = inst["H"]
    out, waits = [], []
    for t in range(inst["T"]):
        a, b = inst["fline"][t] - 1, inst["cline"][t] - 1
        diff = (
            x[b]
            + inst["dep"][b]
            - x[a]
            - inst["arr"][a]
            - table[inst["ap"][a]][inst["dp"][b]]
        )
        s = m.NewBoolVar("")
        if wrap:
            wait = m.NewIntVar(0, H - 1, "")
            k = m.NewIntVar(-4, 4, "")
            m.Add(diff == wait + k * H)
        else:
            wait = diff
        m.Add(wait >= MINW).OnlyEnforceIf(s)
        m.Add(wait <= MAXW).OnlyEnforceIf(s)
        lo, hi = m.NewBoolVar(""), m.NewBoolVar("")
        m.Add(wait <= MINW - 1).OnlyEnforceIf(lo)
        m.Add(wait >= MAXW + 1).OnlyEnforceIf(hi)
        m.AddBoolOr([s, lo, hi])
        m.AddImplication(s, lo.Not())
        m.AddImplication(s, hi.Not())
        out.append(s)
        waits.append(wait)
    return out, waits


def _boarding(m, inst, ok, wait, seats=True, once=True, forced=True):
    """`forced` is the real rule: passengers are not dispatched, so a flow with a
    comfortable option rides one that leaves as soon as any of them, and cannot
    be held back. Without it the boarding becomes a free choice for the planner,
    which is a strict relaxation on both counts."""
    board = [m.NewBoolVar("") for _ in range(inst["T"])]
    for t in range(inst["T"]):
        m.AddImplication(board[t], ok[t])
    if forced:
        for g in range(1, inst["F"] + 1):
            idx = [t for t in range(inst["T"]) if inst["flow"][t] == g]
            if not idx:
                continue
            served = m.NewBoolVar("")
            m.AddMaxEquality(served, [ok[t] for t in idx])
            m.Add(sum(board[t] for t in idx) == 1).OnlyEnforceIf(served)
            m.Add(sum(board[t] for t in idx) == 0).OnlyEnforceIf(served.Not())
            for t in idx:
                for u in idx:
                    if u != t:
                        m.Add(wait[t] <= wait[u]).OnlyEnforceIf([board[t], ok[u]])
    elif once:
        for g in range(1, inst["F"] + 1):
            idx = [t for t in range(inst["T"]) if inst["flow"][t] == g]
            m.Add(sum(board[t] for t in idx) <= 1)
    if seats:
        for b in range(1, inst["L"] + 1):
            idx = [t for t in range(inst["T"]) if inst["cline"][t] == b]
            if idx:
                m.Add(sum(inst["w"][t] * board[t] for t in idx) <= inst["seats"][b - 1])
    return board, sum(inst["w"][t] * board[t] for t in range(inst["T"]))


# Each reading below is a whole model an agent could plausibly write: it decides
# the offsets AND who boards what, under its own belief about the concourse.
READINGS = {
    "true": dict(direct=False, wrap=True, seats=True, once=True, forced=True),
    "free": dict(direct=False, wrap=True, seats=True, once=True, forced=False),
    "walk": dict(direct=True, wrap=True, seats=True, once=True, forced=True),
    "nocap": dict(direct=False, wrap=True, seats=False, once=True, forced=True),
    "sum": dict(direct=False, wrap=True, seats=False, once=False, forced=False),
    "nowrap": dict(direct=False, wrap=False, seats=True, once=True, forced=True),
}


def _build(m, inst, reading):
    cfg = READINGS[reading]
    x = [m.NewIntVar(0, inst["H"] - 1, "") for _ in range(inst["L"])]
    _sep(m, x, inst)
    table = inst["WK"] if cfg["direct"] else inst["D"]
    ok, wait = _comfort(m, x, inst, table, wrap=cfg["wrap"])
    board, obj = _boarding(
        m, inst, ok, wait, seats=cfg["seats"], once=cfg["once"], forced=cfg["forced"]
    )
    return x, board, obj


def solve(inst, reading, tl=60):
    m = cp_model.CpModel()
    x, board, obj = _build(m, inst, reading)
    m.Maximize(obj)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = tl
    s.parameters.num_workers = 8
    if s.Solve(m) != cp_model.OPTIMAL:
        return None
    return (
        [int(s.Value(v)) for v in x],
        [int(s.Value(v)) for v in board],
        int(round(s.ObjectiveValue())),
    )


def pin_best_true(inst, reading, wrong_opt, tl=60):
    """Pin the wrong model at its own optimum, then maximise the TRUE score over
    its whole optimal set: the most favourable plan it could possibly return.
    "REJECT" means no plan in that set is even legal — the strongest outcome."""
    m = cp_model.CpModel()
    x, _, wrong = _build(m, inst, reading)
    m.Add(wrong == wrong_opt)
    ok, wait = _comfort(m, x, inst, inst["D"], wrap=True)
    _, true_obj = _boarding(m, inst, ok, wait, seats=True, once=True, forced=True)
    m.Maximize(true_obj)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = tl
    s.parameters.num_workers = 8
    st = s.Solve(m)
    if st == cp_model.INFEASIBLE:
        return "REJECT"
    if st != cp_model.OPTIMAL:
        return None
    return int(round(s.ObjectiveValue()))


def evaluate(seed, margin, **cfg):
    """A seed qualifies only if every wrong reading loses by `margin` even when
    pinned at its own optimum, and its own emitted plan is rejected outright."""
    inst = make_instance(seed, **cfg)
    got = solve(inst, "true")
    if got is None:
        return None
    tx, tboard, topt = got
    if topt <= 0 or score(tx, tboard, inst) != topt:
        return None

    gaps = {}
    for reading in ("free", "walk", "nocap", "sum", "nowrap"):
        wrong = solve(inst, reading)
        if wrong is None:
            return None
        wx, wboard, wopt = wrong
        # the plan it actually emits must not reach the optimum
        got_score = score(wx, wboard, inst)
        if got_score is not None and got_score >= topt:
            return None
        # the levers must also survive the pin trick: even the most favourable
        # plan in the wrong model's optimal set has to lose
        if reading in ("free", "walk", "nocap"):
            best = pin_best_true(inst, reading, wopt)
            if best is None:
                return None
            if best == "REJECT":
                gaps[reading] = "REJECT"
                continue
            if topt - best < margin:
                return None
            gaps[reading] = topt - best

    return inst, tx, tboard, topt, gaps


def find_seed(lo, hi, margin, **cfg):
    for seed in range(lo, hi):
        got = evaluate(seed, margin=margin, **cfg)
        if got is not None:
            return (seed,) + got
    raise RuntimeError("no separating seed found")


def write_dzn(path, inst):
    def vec(name):
        return f"{name} = [{', '.join(str(v) for v in inst[name])}];"

    def vec1(name):
        return f"{name} = [{', '.join(str(v + 1) for v in inst[name])}];"

    wk_rows = "\n  ".join(
        "| " + ", ".join(str(v) for v in inst["WK"][i]) for i in range(P)
    )
    lines = [
        f"L = {inst['L']};",
        f"H = {inst['H']};",
        f"MINW = {MINW};",
        f"MAXW = {MAXW};",
        f"T = {inst['T']};",
        f"F = {inst['F']};",
        f"P = {P};",
        vec("arr"),
        vec1("ap"),
        vec("dep"),
        vec1("dp"),
        vec("seats"),
        vec("terminus"),
        f"GAP = {inst['GAP']};",
        vec("fline"),
        vec("cline"),
        vec("flow"),
        vec("w"),
        "WK = [" + wk_rows + " |];",
        "",
    ]
    with open(path, "w") as fh:
        fh.write("\n".join(lines))


def write_hardcoded(path, x, board):
    """Passes on the committed instance, must fail on the hidden ones."""
    body = [
        "% Adversarial fixture: bakes in the committed answer and ignores the",
        "% instance entirely.",
        'include "globals.mzn";',
        "",
        "int: L;",
        "int: H;",
        "int: MINW;",
        "int: MAXW;",
        "int: T;",
        "int: F;",
        "int: P;",
        "array[1..L] of int: arr;",
        "array[1..L] of int: ap;",
        "array[1..L] of int: dep;",
        "array[1..L] of int: dp;",
        "array[1..L] of int: seats;",
        "array[1..L] of int: terminus;",
        "int: GAP;",
        "array[1..T] of int: fline;",
        "array[1..T] of int: cline;",
        "array[1..T] of int: flow;",
        "array[1..T] of int: w;",
        "array[1..P, 1..P] of int: WK;",
        "",
        "array[1..L] of var 0..H - 1: x;",
        "array[1..T] of var 0..1: board;",
        "",
        "array[int] of int: XS = [" + ", ".join(str(v) for v in x) + "];",
        "array[int] of int: BS = [" + ", ".join(str(v) for v in board) + "];",
        "constraint forall(l in 1..L where l <= length(XS))(x[l] = XS[l]);",
        "constraint forall(t in 1..T where t <= length(BS))(board[t] = BS[t]);",
        "",
        "var 0..1: total = 1;",
        "solve maximize total;",
        "",
        'output ["x=", show(x), "\\nboard=", show(board), "\\n"];',
        "",
    ]
    with open(path, "w") as fh:
        fh.write("\n".join(body))


COMMITTED = dict(
    L=7,
    H=15,
    F=12,
    groups=[(1, 2, 3), (4, 5), (6, 7)],
    gap=4,
    direct=(10, 13),
    hub=(1, 2),
    fat=0.5,
    seatfrac=0.30,
    trunk=3,
)
HIDDEN_1 = dict(COMMITTED, H=16, direct=(11, 14))
HIDDEN_2 = dict(COMMITTED, L=8, groups=[(1, 2, 3), (4, 5), (6, 7, 8)])


def main():
    seed, inst, x, board, opt, gaps = find_seed(1, 6000, 5, **COMMITTED)
    write_dzn(os.path.join(ENV, "instance.dzn"), inst)
    open(os.path.join(HERE, "optimum.txt"), "w").write(f"{opt}\n")
    write_hardcoded(os.path.join(HERE, "hardcoded.mzn"), x, board)
    print(f"committed: seed={seed} opt={opt} pins={gaps}")

    optima = {opt}
    for tag, cfg, lo, hi in (
        ("hidden", HIDDEN_1, 6000, 12000),
        ("hidden2", HIDDEN_2, 12000, 18000),
    ):
        for start in range(lo, hi):
            got = evaluate(start, margin=4, **cfg)
            if got is None:
                continue
            hinst, _, _, hopt, hgaps = got
            if hopt in optima:  # optima must be pairwise distinct
                continue
            optima.add(hopt)
            write_dzn(os.path.join(HERE, f"instance_{tag}.dzn"), hinst)
            open(os.path.join(HERE, f"optimum_{tag}.txt"), "w").write(f"{hopt}\n")
            print(f"{tag}: seed={start} opt={hopt} pins={hgaps}")
            break
        else:
            raise RuntimeError(f"no separating seed for {tag}")


if __name__ == "__main__":
    main()
