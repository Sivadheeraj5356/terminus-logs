import glob
import os
import subprocess
import tempfile
from fractions import Fraction as F
from math import gcd

import pytest

APP = "/app"
BIN = os.path.join(APP, "solver")
HERE = os.path.dirname(__file__)
FIX = os.path.join(HERE, "fixtures")
# /app/data is the agent's copy and the agent may rewrite it, so grading reads
# these verifier-owned copies instead
VISIBLE = os.path.join(HERE, "visible")
EXAMPLES = os.path.join(HERE, "examples")

I128_MAX = 2**127 - 1

# The "standard library only, no separate program" rule is enforced where it can
# be enforced completely: the program is built from the standard library only and
# the image has no network, so no external package can be fetched. The check below
# is a deterrent on top of that: it makes the common interpreters and the toolchain
# unrunnable and clears the search path, so a program that reaches for one of them
# cannot run it here. It is not an operating-system sandbox; the standard-library
# build carries the guarantee.
SEALABLE = sorted(
    p
    for pattern in [
        "/usr/bin/python3*",
        "/usr/local/bin/python3*",
        "/usr/bin/perl*",
        "/usr/bin/bc",
        "/usr/bin/dc",
        "/usr/bin/awk",
        "/usr/bin/gawk",
        "/usr/bin/expr",
        "/usr/bin/factor",
        "/usr/bin/openssl",
        "/usr/local/cargo/bin/*",
    ]
    for p in glob.glob(pattern)
    if os.path.isfile(p)
)


def _build():
    """Build the program from solver.rs.

    make invokes rustc on a single source file, which runs no build script, so
    nothing in the build can read the case files the answers are checked against;
    the graded cases are also in memory before the build starts.
    """
    env = dict(os.environ)
    env["PATH"] = "/usr/local/cargo/bin" + os.pathsep + env.get("PATH", "/usr/bin:/bin")
    r = subprocess.run(
        ["make", "solver"],
        cwd=APP,
        capture_output=True,
        text=True,
        timeout=900,
        env=env,
    )
    if r.returncode != 0:
        return (r.stdout + r.stderr)[-2000:]
    if not os.path.exists(BIN):
        return "the build produced no program at " + BIN
    return None


@pytest.fixture(scope="session", autouse=True)
def built():
    if BUILD_ERR is not None:
        pytest.fail("the program did not build:\n" + BUILD_ERR)


# ------------------------------------------------------- exact reconstruction
def falling(k, j):
    "k!/(k-j)!, the constant in the j-th derivative of x^k"
    r = 1
    for t in range(j):
        r *= k - t
    return r


def row_of(x, j, n):
    "the row of the linear system for the condition of order j at point x"
    return [falling(k, j) * (x ** (k - j)) if k >= j else 0 for k in range(n)]


def build_system(n, conds):
    a = [row_of(x, j, n) for (x, j, _v) in conds]
    b = [v for (_x, _j, v) in conds]
    return a, b


def classify_rref(n, conds):
    "reference one: exact Gauss-Jordan on the augmented matrix"
    a, b = build_system(n, conds)
    m = len(a)
    aug = [[F(a[i][j]) for j in range(n)] + [F(b[i])] for i in range(m)]
    pivots = []
    r = 0
    for c in range(n):
        piv = next((i for i in range(r, m) if aug[i][c] != 0), None)
        if piv is None:
            continue
        aug[r], aug[piv] = aug[piv], aug[r]
        inv = aug[r][c]
        aug[r] = [val / inv for val in aug[r]]
        for i in range(m):
            if i != r and aug[i][c] != 0:
                f = aug[i][c]
                aug[i] = [aug[i][t] - f * aug[r][t] for t in range(n + 1)]
        pivots.append(c)
        r += 1
        if r == m:
            break
    for i in range(m):
        if all(aug[i][j] == 0 for j in range(n)) and aug[i][n] != 0:
            return "NONE", None
    if len(pivots) < n:
        return "MANY", None
    coeffs = [F(0)] * n
    for i, c in enumerate(pivots):
        coeffs[c] = aug[i][n]
    return "UNIQUE", coeffs


def bareiss_rank(mat):
    "rank of an integer matrix by fraction-free elimination"
    m = [row[:] for row in mat]
    rows = len(m)
    cols = len(m[0]) if rows else 0
    prev = 1
    r = 0
    for c in range(cols):
        piv = next((i for i in range(r, rows) if m[i][c] != 0), None)
        if piv is None:
            continue
        m[r], m[piv] = m[piv], m[r]
        for i in range(r + 1, rows):
            for j in range(c + 1, cols):
                m[i][j] = (m[r][c] * m[i][j] - m[i][c] * m[r][j]) // prev
            m[i][c] = 0
        prev = m[r][c]
        r += 1
        if r == rows:
            break
    return r


def int_det(mat):
    "exact determinant of a square integer matrix by Bareiss"
    n = len(mat)
    if n == 0:
        return 1
    m = [row[:] for row in mat]
    prev = 1
    sign = 1
    for k in range(n - 1):
        if m[k][k] == 0:
            piv = next((i for i in range(k + 1, n) if m[i][k] != 0), None)
            if piv is None:
                return 0
            m[k], m[piv] = m[piv], m[k]
            sign = -sign
        for i in range(k + 1, n):
            for j in range(k + 1, n):
                m[i][j] = (m[k][k] * m[i][j] - m[i][k] * m[k][j]) // prev
            m[i][k] = 0
        prev = m[k][k]
    return sign * m[n - 1][n - 1]


def classify_bareiss(n, conds):
    "reference two: ranks by fraction-free elimination, unique solution by Cramer"
    a, b = build_system(n, conds)
    aug = [a[i] + [b[i]] for i in range(len(a))]
    ra = bareiss_rank(a)
    rab = bareiss_rank(aug)
    if rab > ra:
        return "NONE", None
    if ra < n:
        return "MANY", None
    rows = _independent_rows(a, n)
    sq = [a[i] for i in rows]
    rhs = [b[i] for i in rows]
    det = int_det(sq)
    coeffs = []
    for col in range(n):
        rep = [sq[i][:] for i in range(n)]
        for i in range(n):
            rep[i][col] = rhs[i]
        coeffs.append(F(int_det(rep), det))
    return "UNIQUE", coeffs


def _independent_rows(a, n):
    cur, chosen = [], []
    for i in range(len(a)):
        trial = cur + [a[i]]
        if bareiss_rank(trial) == len(trial):
            cur = trial
            chosen.append(i)
            if len(chosen) == n:
                return chosen
    raise RuntimeError("could not find n independent rows")


def eval_deriv(coeffs, j, x):
    "the j-th derivative of the polynomial evaluated at x, exact"
    acc = F(0)
    for k in range(len(coeffs)):
        if k >= j:
            acc += coeffs[k] * falling(k, j) * (F(x) ** (k - j))
    return acc


def plug_back(coeffs, conds):
    return all(eval_deriv(coeffs, j, x) == F(v) for (x, j, v) in conds)


# ------------------------------------------------------------- wrong solvers
def classify_float(n, conds, eps=1e-9):
    "the obvious double-precision solve; wrong on near-singular and big fractions"
    a, b = build_system(n, conds)
    m = len(a)
    aug = [[float(a[i][j]) for j in range(n)] + [float(b[i])] for i in range(m)]
    piv_rows = []
    r = 0
    for c in range(n):
        piv, best = None, eps
        for i in range(r, m):
            if abs(aug[i][c]) > best:
                piv, best = i, abs(aug[i][c])
        if piv is None:
            continue
        aug[r], aug[piv] = aug[piv], aug[r]
        inv = aug[r][c]
        aug[r] = [val / inv for val in aug[r]]
        for i in range(m):
            if i != r and aug[i][c] != 0.0:
                f = aug[i][c]
                aug[i] = [aug[i][t] - f * aug[r][t] for t in range(n + 1)]
        piv_rows.append(c)
        r += 1
        if r == m:
            break
    for i in range(m):
        if all(abs(aug[i][j]) <= eps for j in range(n)) and abs(aug[i][n]) > eps:
            return "NONE", None
    if len(piv_rows) < n:
        return "MANY", None
    sol = [0.0] * n
    for i, c in enumerate(piv_rows):
        sol[c] = aug[i][n]
    return "UNIQUE", [F(round(s)) for s in sol]


def classify_count_only(n, conds):
    "decides by condition count alone, ignoring rank and poisedness"
    c = len(conds)
    if c < n:
        return "MANY", None
    if c > n:
        return "NONE", None
    v, co = classify_rref(n, conds)
    return ("UNIQUE", co) if v == "UNIQUE" else ("UNIQUE", [F(0)] * n)


def classify_confluent_newton(n, conds):
    "the memorized confluent Hermite routine; blind to gaps, rank, and consistency"
    from collections import defaultdict

    by_node = defaultdict(dict)
    for x, j, v in conds:
        by_node[x][j] = v
    z, vals = [], []
    for x in by_node:
        orders = by_node[x]
        for k in range(len(orders)):
            if k not in orders:
                return "UNIQUE", [F(0)] * n
            z.append(x)
            vals.append((k, orders[k]))
    if len(z) != n:
        return "UNIQUE", [F(0)] * n
    dd = [[F(0)] * n for _ in range(n)]
    for i in range(n):
        dd[i][0] = F(vals[i][1])
    fact = [1] * n
    for k in range(1, n):
        fact[k] = fact[k - 1] * k
    for col in range(1, n):
        for i in range(col, n):
            if z[i] == z[i - col]:
                dd[i][col] = F(vals[i][1]) / fact[col] if vals[i][0] == col else F(0)
            else:
                dd[i][col] = (dd[i][col - 1] - dd[i - 1][col - 1]) / (z[i] - z[i - col])
    newton = [dd[i][i] for i in range(n)]
    basis = [F(1)]
    poly = [F(0)] * n
    for i in range(n):
        for d in range(len(basis)):
            poly[d] += newton[i] * basis[d]
        nb = [F(0)] * (len(basis) + 1)
        for d in range(len(basis)):
            nb[d] -= z[i] * basis[d]
            nb[d + 1] += basis[d]
        basis = nb
    return "UNIQUE", poly[:n]


# ------------------------------------------------------------------------- io
def encode(cases):
    lines = [str(len(cases))]
    for n, conds in cases:
        lines.append("%d %d" % (n, len(conds)))
        for x, j, v in conds:
            lines.append("%d %d %d" % (x, j, v))
    return "\n".join(lines) + "\n"


def load_cases(path):
    it = iter(open(path).read().split())
    t = int(next(it))
    out = []
    for _ in range(t):
        n = int(next(it))
        c = int(next(it))
        conds = [(int(next(it)), int(next(it)), int(next(it))) for _ in range(c)]
        out.append((n, conds))
    return out


def _frac(tok):
    assert "/" in tok, "a value is not written as numerator/denominator"
    ns, ds = tok.split("/")
    num, den = int(ns), int(ds)
    assert den > 0, "a denominator is not positive"
    if num == 0:
        assert den == 1, "zero is not written as 0/1"
    else:
        assert gcd(abs(num), den) == 1, "a value is not in lowest terms"
    return F(num, den)


def none_cert_ok(n, conds, lam):
    "lam certifies inconsistency: sum lam_i row_i == 0 and sum lam_i v_i != 0"
    a, b = build_system(n, conds)
    if lam is None or len(lam) != len(conds):
        return False
    combo = [sum(lam[i] * a[i][k] for i in range(len(a))) for k in range(n)]
    if any(val != 0 for val in combo):
        return False
    return sum(lam[i] * b[i] for i in range(len(b))) != 0


def many_ok(n, conds, sols):
    "two distinct coefficient vectors, each satisfying every condition"
    if sols is None:
        return False
    c1, c2 = sols
    if len(c1) != n or len(c2) != n or c1 == c2:
        return False
    return plug_back(c1, conds) and plug_back(c2, conds)


def parse_answer(text, cases):
    it = iter(text.split())
    out = []
    for n, _conds in cases:
        head = next(it)
        if head == "NONE":
            lam = [_frac(next(it)) for _ in range(len(_conds))]
            out.append(("NONE", lam))
        elif head == "MANY":
            c1 = [_frac(next(it)) for _ in range(n)]
            c2 = [_frac(next(it)) for _ in range(n)]
            out.append(("MANY", (c1, c2)))
        else:
            assert int(head) == n, (
                "the reported coefficient count is not the degree bound"
            )
            coeffs = [_frac(next(it)) for _ in range(n)]
            out.append(("UNIQUE", coeffs))
    assert not list(it), "the output carries more than the expected blocks"
    return out


def run_file(path, cases, env=None):
    r = subprocess.run(
        [BIN, path], capture_output=True, text=True, timeout=900, env=env
    )
    assert r.returncode == 0, "the program failed on " + path + "\n" + r.stderr[-1500:]
    return parse_answer(r.stdout, cases)


def write_cases(cases):
    d = tempfile.mkdtemp()
    os.chmod(d, 0o755)
    p = os.path.join(d, "cases.txt")
    with open(p, "w") as f:
        f.write(encode(cases))
    os.chmod(p, 0o644)
    return p


def run_cases(cases, env=None):
    return run_file(write_cases(cases), cases, env=env)


def run_raw(cases):
    r = subprocess.run(
        [BIN, write_cases(cases)], capture_output=True, text=True, timeout=900
    )
    assert r.returncode == 0, r.stderr[-800:]
    return r.stdout


# -------------------------------------------------------------------- grading
def certify(case, answer):
    n, conds = case
    verdict, payload = answer
    truth, tco = classify_rref(n, conds)
    other, oco = classify_bareiss(n, conds)
    assert (truth, tco) == (other, oco), "the two references disagree on this case"
    assert verdict == truth, "the reported classification is wrong"
    if truth == "UNIQUE":
        assert payload is not None and len(payload) == n, "wrong number of coefficients"
        assert plug_back(payload, conds), (
            "the coefficients do not satisfy every condition"
        )
        assert payload == tco, "the coefficients are not the unique solution"
    elif truth == "NONE":
        assert none_cert_ok(n, conds, payload), (
            "the inconsistency certificate is not valid"
        )
    else:
        assert many_ok(n, conds, payload), (
            "the two solutions are not distinct valid solutions"
        )
    return True


def check(cases):
    for case, answer in zip(cases, run_cases(cases)):
        certify(case, answer)
    return True


# ------------------------------------------------------------------ batteries
def _lcg(seed):
    s = seed

    def nxt(lo, hi):
        nonlocal s
        s = (s * 1103515245 + 12345) % (2**31)
        return lo + s % (hi - lo + 1)

    return nxt


def generated_cases(count=20, seed=13372026):
    "problems from a fixed recurrence, stored in no file"
    nxt = _lcg(seed)
    out = []
    guard = 0
    while len(out) < count and guard < 20000:
        guard += 1
        n = nxt(2, 6)
        c = nxt(1, n + 2)
        conds = []
        used = set()
        tries = 0
        while len(conds) < c and tries < 60:
            tries += 1
            x = nxt(-6, 6)
            j = nxt(0, n - 1)
            if (x, j) in used:
                continue
            used.add((x, j))
            conds.append((x, j, nxt(-12, 12)))
        if len(conds) == c:
            out.append((n, conds))
    return out


GENERATED = generated_cases()

_B = 10**14 + 7  # a large node, so the exact coefficients run past a fixed width type

CURATED = [
    (1, [(0, 0, 7)]),
    (1, [(5, 0, 3), (2, 0, 3)]),
    (1, [(5, 0, 3), (2, 0, 4)]),
    (2, [(0, 0, 1)]),
    (2, [(1, 0, 2), (1, 1, 3)]),
    (3, [(0, 1, 0), (0, 2, 0), (1, 0, 5)]),
    (3, [(0, 0, 0), (0, 0, 0), (1, 0, 1)]),
    # node-dependent poisedness: the same derivative pattern, poised then singular
    (3, [(0, 0, 1), (0, 1, 2), (1, 1, 3)]),
    (3, [(2, 0, 1), (2, 1, 2), (2, 1, 2)]),
    # a genuine gap: orders 0 and 2 at a node, no order 1
    (4, [(0, 0, 1), (0, 2, 2), (1, 0, 3), (2, 0, 4)]),
    # over-determined but consistent, so still unique
    (2, [(0, 0, 1), (1, 0, 2), (2, 0, 3)]),
    # over-determined and contradictory
    (2, [(0, 0, 1), (1, 0, 2), (2, 0, 4)]),
    # large-node lacunary schemes forcing a coefficient past 128 bits
    (3, [(_B, 0, 1), (_B, 2, 1), (-_B, 0, 1)]),
    (4, [(_B, 0, 2), (_B, 1, 3), (-_B, 0, 5), (-_B, 2, 7)]),
    # high derivative orders exercising the factorial factors
    (5, [(1, 0, 1), (1, 2, 4), (1, 4, 24), (-1, 0, 0), (-1, 1, 0)]),
]


def _fixture_files():
    return sorted(glob.glob(os.path.join(FIX, "*.txt")))


def _visible_files():
    return sorted(glob.glob(os.path.join(VISIBLE, "*.txt")))


FIXTURES = {os.path.basename(p): load_cases(p) for p in _fixture_files()}
VISIBLE_SETS = {os.path.basename(p): load_cases(p) for p in _visible_files()}
EXAMPLE_SETS = {}
for _name in ["sanity_a", "sanity_b", "sanity_c"]:
    _cases = load_cases(os.path.join(EXAMPLES, _name + ".txt"))
    with open(os.path.join(EXAMPLES, _name + ".expected.txt")) as _fh:
        EXAMPLE_SETS[_name] = (_cases, _fh.read())

assert len(FIXTURES) >= 9, "the hidden fixtures are missing"
assert len(VISIBLE_SETS) >= 8, "the sample data is missing"
assert len(EXAMPLE_SETS) == 3, "a worked example is missing"
assert len(GENERATED) == 20, "a generated case went missing"

ALL_GRADED = (
    CURATED
    + GENERATED
    + [c for cs in FIXTURES.values() for c in cs]
    + [c for cs in VISIBLE_SETS.values() for c in cs]
)

# every graded case is in memory before the program is built, so nothing in the build
# cannot change what is checked
BUILD_ERR = _build()


# --------------------------------------------------------------- graded tests
@pytest.mark.parametrize("idx", range(len(CURATED)))
def test_curated_case(idx):
    "each curated problem is classified correctly, with exact coefficients"
    assert check([CURATED[idx]])


@pytest.mark.parametrize("idx", range(len(GENERATED)))
def test_generated_case(idx):
    "each generated problem, stored in no file, is answered correctly"
    assert check([GENERATED[idx]])


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_hidden_fixture(name):
    "every case in each hidden fixture is answered correctly, read as one batch"
    assert check(FIXTURES[name])


@pytest.mark.parametrize("name", sorted(VISIBLE_SETS))
def test_visible_data(name):
    "every case shipped as sample data is answered correctly, read as one batch"
    assert check(VISIBLE_SETS[name])


def test_batch_preserves_order():
    "a long batch in one file is answered problem by problem, in order"
    assert check(CURATED + GENERATED[:6])


def test_committed_examples():
    "the committed worked answers certify, and the program agrees with them"
    for cases, text in EXAMPLE_SETS.values():
        for case, answer in zip(cases, parse_answer(text, cases)):
            certify(case, answer)
        for case, answer in zip(cases, run_cases(cases)):
            certify(case, answer)


# ------------------------------------------------------------ behaviour tests
def test_no_helper_program_does_the_work():
    "the answers do not change with the common interpreters and the toolchain shut"
    saved = {}
    try:
        for path in SEALABLE:
            saved[path] = os.stat(path).st_mode
            os.chmod(path, 0)
        env = dict(os.environ)
        env["PATH"] = os.path.join(APP, "_no_such_dir")
        env["HOME"] = "/tmp"
        sealed = CURATED[12:15] + GENERATED[:4]
        for case, answer in zip(sealed, run_cases(sealed, env=env)):
            certify(case, answer)
    finally:
        for path, mode in saved.items():
            try:
                os.chmod(path, mode)
            except OSError:
                pass


def test_determinism_rerun():
    "two runs over the same batch produce byte identical output"
    assert run_raw(CURATED[:8]) == run_raw(CURATED[:8])


def test_answer_follows_the_input():
    "the answer tracks the problems rather than replaying a canned block"
    assert run_raw(CURATED[:5]) != run_raw(CURATED[7:12])


# Battery self checks: these grade the case set, not the candidate, keeping the
# wrong solvers genuinely separated.
def _wrong(fn):
    n = 0
    for cn, conds in ALL_GRADED:
        truth = classify_rref(cn, conds)
        try:
            got = fn(cn, conds)
        except Exception:  # noqa: BLE001
            got = ("ERR", None)
        if got != truth:
            n += 1
    return n


def test_battery_references_agree():
    "the two references agree on every case"
    for n, conds in ALL_GRADED:
        assert classify_rref(n, conds) == classify_bareiss(n, conds)


def test_battery_covers_the_three_verdicts():
    "the graded set exercises unique, none, and many"
    seen = {classify_rref(n, conds)[0] for n, conds in ALL_GRADED}
    assert {"UNIQUE", "NONE", "MANY"} <= seen


def test_battery_defeats_the_memorized_routine():
    "the confluent Hermite routine is wrong on many cases: it cannot see gaps or rank"
    assert _wrong(classify_confluent_newton) >= 40, (
        "the battery does not break the classic routine"
    )


def test_battery_defeats_count_only():
    "deciding by condition count alone, ignoring rank and poisedness, fails often"
    assert _wrong(classify_count_only) >= 12, (
        "the battery does not force a rank computation"
    )


def test_battery_defeats_double_precision():
    "a double precision solve mis-handles near-singular schemes and big fractions"
    assert _wrong(classify_float) >= 12, (
        "the battery does not separate float from exact"
    )


def test_battery_needs_arbitrary_precision():
    "some unique answers have coefficients past any fixed width machine type"
    widest = 0
    for n, conds in ALL_GRADED:
        v, co = classify_rref(n, conds)
        if v == "UNIQUE":
            for c in co:
                widest = max(widest, abs(c.numerator), c.denominator)
    assert widest > I128_MAX, "no case forces arbitrary precision in the answer"


def test_battery_has_node_dependent_poisedness():
    "the same derivative pattern is full rank at some nodes and rank deficient at others"

    def mat(a, b):
        return build_system(3, [(a, 0, 0), (a, 1, 0), (b, 1, 0)])[0]

    ranks = {bareiss_rank(mat(a, b)) for a, b in [(0, 1), (1, -1), (2, 2), (0, 0)]}
    assert 3 in ranks and any(r < 3 for r in ranks), (
        "poisedness is not node dependent here"
    )


def test_certificate_is_load_bearing():
    "a correct verdict is rejected unless it is backed by a valid witness"
    none_case = next(c for c in ALL_GRADED if classify_rref(c[0], c[1])[0] == "NONE")
    with pytest.raises(AssertionError):
        certify(none_case, ("NONE", [F(0)] * len(none_case[1])))
    many_case = next(c for c in ALL_GRADED if classify_rref(c[0], c[1])[0] == "MANY")
    n = many_case[0]
    with pytest.raises(AssertionError):
        certify(many_case, ("MANY", ([F(0)] * n, [F(0)] * n)))
