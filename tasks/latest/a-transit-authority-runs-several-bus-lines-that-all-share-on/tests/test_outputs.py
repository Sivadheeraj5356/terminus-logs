import os
import re
import subprocess

APP = "/app"
MODEL = os.path.join(APP, "model.mzn")
INST = os.path.join(APP, "instance.dzn")
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

HIDDEN = [
    (os.path.join(FIX, "instance_hidden.dzn"), os.path.join(FIX, "optimum_hidden.txt")),
    (
        os.path.join(FIX, "instance_hidden2.dzn"),
        os.path.join(FIX, "optimum_hidden2.txt"),
    ),
]
NAIVE_FREE = os.path.join(FIX, "naive_free.mzn")
NAIVE_WALK = os.path.join(FIX, "naive_walk.mzn")
NAIVE_NOCAP = os.path.join(FIX, "naive_nocap.mzn")
NAIVE_SUM = os.path.join(FIX, "naive_sum.mzn")
NAIVE_NOWRAP = os.path.join(FIX, "naive_nowrap.mzn")
HARDCODED = os.path.join(FIX, "hardcoded.mzn")

REFERENCE_OPTIMUM = int(open(os.path.join(FIX, "optimum.txt")).read().strip())


def _parse_instance(path):
    text = open(path).read()

    def scalar(name):
        return int(re.search(rf"\b{name}\s*=\s*(\d+)\s*;", text).group(1))

    def vec(name):
        body = re.search(rf"\b{name}\s*=\s*\[([^\]]*)\]\s*;", text).group(1)
        return [int(v) for v in re.findall(r"-?\d+", body)]

    P = scalar("P")
    wk_body = re.search(r"\bWK\s*=\s*\[(.*?)\|\s*\]\s*;", text, re.S).group(1)
    flat = [int(v) for v in re.findall(r"-?\d+", wk_body)]
    assert len(flat) == P * P, f"WK is not {P}x{P}: {len(flat)} entries"
    WK = [flat[i * P : (i + 1) * P] for i in range(P)]

    return {
        "L": scalar("L"),
        "H": scalar("H"),
        "MINW": scalar("MINW"),
        "MAXW": scalar("MAXW"),
        "T": scalar("T"),
        "F": scalar("F"),
        "P": P,
        "arr": vec("arr"),
        "ap": vec("ap"),
        "dep": vec("dep"),
        "dp": vec("dp"),
        "seats": vec("seats"),
        "terminus": vec("terminus"),
        "GAP": scalar("GAP"),
        "fline": vec("fline"),
        "cline": vec("cline"),
        "flow": vec("flow"),
        "w": vec("w"),
        "WK": WK,
    }


def _walk_table(d):
    """The time a passenger really spends: cheapest chain of direct passages."""
    P = d["P"]
    D = [row[:] for row in d["WK"]]
    for k in range(P):
        for i in range(P):
            for j in range(P):
                if D[i][k] + D[k][j] < D[i][j]:
                    D[i][j] = D[i][k] + D[k][j]
    return D


def _ints(body):
    """A printed 0/1 array, however the model spelled its booleans."""
    out = []
    for tok in re.findall(r"-?\d+|true|false", body):
        if tok == "true":
            out.append(1)
        elif tok == "false":
            out.append(0)
        else:
            out.append(int(tok))
    return out


def _solve(model, inst, timeout=900):
    r = subprocess.run(
        ["minizinc", "--solver", "chuffed", model, inst],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    blocks = [b for b in r.stdout.split("----------") if "x=" in b]
    assert blocks, "model emitted no solution: " + r.stdout
    last = blocks[-1]
    mx = re.search(r"x=\s*\[([^\]]*)\]", last)
    mb = re.search(r"board=\s*\[([^\]]*)\]", last)
    assert mx, "could not parse the offsets: " + last
    assert mb, "could not parse the boarding plan: " + last
    return _ints(mx.group(1)), _ints(mb.group(1))


def _cyclic_dist(a, b, H):
    diff = abs(a - b) % H
    return min(diff, H - diff)


def _waits(x, d, walk):
    """The interval each row leaves its passengers, taken around the cycle."""
    H = d["H"]
    out = []
    for t in range(d["T"]):
        a, b = d["fline"][t] - 1, d["cline"][t] - 1
        out.append(
            (
                x[b]
                + d["dep"][b]
                - x[a]
                - d["arr"][a]
                - walk[d["ap"][a] - 1][d["dp"][b] - 1]
            )
            % H
        )
    return out


def _score(x, board, inst):
    """Recomputed from the raw instance: the walk relaxed to its cheapest chain,
    the interval taken around the cycle, and the boarding as the passengers
    themselves settle it -- a body with a comfortable connection open to it rides
    one that leaves as soon as any of them does, a body with none rides nothing,
    and no bus lifts more than its seats. None if the plan is not a legal one."""
    d = _parse_instance(inst)
    if len(x) != d["L"] or len(board) != d["T"]:
        return None
    if not all(0 <= v < d["H"] for v in x):
        return None
    if not all(v in (0, 1) for v in board):
        return None
    for i in range(d["L"]):
        for j in range(i + 1, d["L"]):
            if d["terminus"][i] == d["terminus"][j]:
                if _cyclic_dist(x[i], x[j], d["H"]) < d["GAP"]:
                    return None

    wait = _waits(x, d, _walk_table(d))
    ok = [d["MINW"] <= wt <= d["MAXW"] for wt in wait]
    for t in range(d["T"]):
        if board[t] and not ok[t]:
            return None
    for g in range(1, d["F"] + 1):
        idx = [t for t in range(d["T"]) if d["flow"][t] == g]
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
    seated = [0] * d["L"]
    for t in range(d["T"]):
        if board[t]:
            seated[d["cline"][t] - 1] += d["w"][t]
    if any(seated[b] > d["seats"][b] for b in range(d["L"])):
        return None
    return sum(d["w"][t] for t in range(d["T"]) if board[t])


def _hidden_optimum(path):
    return int(open(path).read().strip())


def test_solution_feasible():
    """The agent plan is a legal schedule: spaced offsets, and a boarding the
    passengers would actually settle on, within every bus's seats."""
    x, board = _solve(MODEL, INST)
    assert _score(x, board, INST) is not None


def test_objective_is_optimum():
    """The agent plan, rescored from the raw instance, carries the most weight."""
    x, board = _solve(MODEL, INST)
    assert _score(x, board, INST) == REFERENCE_OPTIMUM


def test_naive_free_model_wrong():
    """Handing the boarding to the planner lets it wave a body of passengers onto
    a later bus, or hold them back to spare seats for somebody heavier. Neither
    is open to it, and the plans it likes are not the ones the passengers make."""
    x, board = _solve(NAIVE_FREE, INST)
    assert _score(x, board, INST) != REFERENCE_OPTIMUM


def test_naive_walk_model_wrong():
    """Reading WK as the walk itself, rather than the cheapest chain of passages,
    mistimes the connections it boards."""
    x, board = _solve(NAIVE_WALK, INST)
    assert _score(x, board, INST) != REFERENCE_OPTIMUM


def test_naive_nocap_model_wrong():
    """Letting a bus lift more passengers than it has seats claims more than it
    can carry away."""
    x, board = _solve(NAIVE_NOCAP, INST)
    assert _score(x, board, INST) != REFERENCE_OPTIMUM


def test_naive_sum_model_wrong():
    """Banking a weight for every comfortable row puts one body of passengers on
    several buses at once."""
    x, board = _solve(NAIVE_SUM, INST)
    assert _score(x, board, INST) != REFERENCE_OPTIMUM


def test_naive_nowrap_model_wrong():
    """Measuring the interval as a straight-line difference of clock minutes
    misses the connections caught on the next turn of the cycle."""
    x, board = _solve(NAIVE_NOWRAP, INST)
    assert _score(x, board, INST) != REFERENCE_OPTIMUM


def test_hardcoded_model_fails_hidden():
    """A model that bakes in the committed answer cannot survive a fresh seed."""
    x, board = _solve(HARDCODED, INST)
    assert _score(x, board, INST) == REFERENCE_OPTIMUM
    inst, opt = HIDDEN[0]
    x, board = _solve(HARDCODED, inst)
    assert _score(x, board, inst) != _hidden_optimum(opt)


def test_hidden_instances_generalize():
    """The agent model attains the recomputed maximum on unseen seeds."""
    for inst, opt in HIDDEN:
        x, board = _solve(MODEL, inst)
        assert _score(x, board, inst) == _hidden_optimum(opt), inst


def test_model_declares_decisions():
    """model.mzn optimises rather than merely satisfying, and does not reach
    into the verifier's files."""
    src = open(MODEL).read()
    assert re.search(r"var[^;]*:\s*x\b", src)
    assert re.search(r"var[^;]*:\s*board\b", src)
    assert "maximize" in src or "minimize" in src
    for banned in ("/tests", "/fixtures", "optimum.txt", "instance_hidden"):
        assert banned not in src
