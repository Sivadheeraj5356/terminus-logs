"""Behavioral verifier for the extended-persistence fold-retrieval task.

Runs the candidate program on the shipped data and on verifier-generated synthetic,
metamorphic, edge-case, hidden, and large-magnitude structures, then grades its
observed output against an independent oracle (ref.py). Nothing here reads or scores
the candidate's source. Two independent recomputations cross-check the oracle: a
union-find elder-rule computation of the dimension-0 families and a second boundary
reduction under a different simplex ordering, both then subject to the significance
floor. Wrong-baseline checks (wrong_refs.py) prove that a solver which computes only
sublevel persistence, filters by the minimum vertex value, swaps the ordinary and
relative labels, mislabels or drops the essential class, or mishandles the
significance floor (skips it, keeps bars at it, uses the wrong divisor, or derives
it from the wrong bars) gets graded cases wrong."""

import csv
import os
import random
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref
import wrong_refs

AGENT = "/app/analyze"
DATA = "/app/data"
NF = 17
HERE = os.path.dirname(os.path.abspath(__file__))

SHIPPED_QUERIES = ["Q%03d" % i for i in range(24)]


def run_agent(data_dir):
    """Run the candidate; return {qid: (ref_id, group, 17-int feature tuple)}."""
    proc = subprocess.run(
        [AGENT, data_dir], capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, "candidate exited %d: %s" % (
        proc.returncode,
        proc.stderr[:400],
    )
    out = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        f = line.split()
        assert len(f) == 3 + NF, "bad output line: %r" % line
        out[f[0]] = (f[1], f[2], tuple(int(x) for x in f[3 : 3 + NF]))
    return out


# --------------------------------------------------------------------------
# Independent cross-oracles for the shipped/synthetic diagrams.
# --------------------------------------------------------------------------
def _uf_h0(height, edges):
    """Dimension-0 finite persistences via a union-find elder rule on the 1-skeleton,
    fully independent of the boundary reduction in ref.py. `height` is indexed by
    vertex id; `edges` is the list of (u, v) grid edges."""
    n = len(height)
    parent = list(range(n))
    birth = list(height)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    ev = sorted(edges, key=lambda e: (max(height[e[0]], height[e[1]]), e))
    bars = []
    for u, v in ev:
        f = max(height[u], height[v])
        ru, rv = find(u), find(v)
        if ru == rv:
            continue
        if (birth[ru], ru) <= (birth[rv], rv):
            elder, younger = ru, rv
        else:
            elder, younger = rv, ru
        if f > birth[younger]:
            bars.append(f - birth[younger])
        parent[younger] = elder
    return sorted(bars, reverse=True)


def _edges_of(n):
    return ref.grid_simplices(n)[1]


def _alt_finite_bars(height, simplices):
    """A second boundary reduction over F2 using a different (descending id)
    intra-value simplex ordering; the persistence-value multiset is invariant, so it
    must match ref._finite_bars."""
    verts, edges, tris = simplices
    allsimp = []
    for s in verts:
        allsimp.append((height[s[0]], 0, s))
    for s in edges:
        allsimp.append((max(height[s[0]], height[s[1]]), 1, s))
    for s in tris:
        allsimp.append((max(height[s[0]], height[s[1]], height[s[2]]), 2, s))
    allsimp.sort(key=lambda t: (t[0], t[1], tuple(-x for x in t[2])))
    index = {t[2]: i for i, t in enumerate(allsimp)}
    filt = [t[0] for t in allsimp]
    dim = [t[1] for t in allsimp]
    cols = []
    for _f, d, s in allsimp:
        if d == 0:
            cols.append(0)
        elif d == 1:
            cols.append((1 << index[(s[0],)]) | (1 << index[(s[1],)]))
        else:
            a, b, c = s
            e0 = (a, b) if (a, b) in index else (b, a)
            e1 = (a, c) if (a, c) in index else (c, a)
            e2 = (b, c) if (b, c) in index else (c, b)
            cols.append((1 << index[e0]) | (1 << index[e1]) | (1 << index[e2]))
    low_inv = {}
    fin = {0: [], 1: []}
    for j in range(len(cols)):
        col = cols[j]
        while col:
            low = col.bit_length() - 1
            if low in low_inv:
                col ^= cols[low_inv[low]]
            else:
                low_inv[low] = j
                p = dim[low]
                if p in (0, 1):
                    if filt[j] > filt[low]:
                        fin[p].append(filt[j] - filt[low])
                break
    return fin


def cross_features(field, n):
    """Recompute the 17 features via the union-find H0 oracle and the alternate
    reduction, matching ref.features when both are correct. The significance floor
    is applied here too, from the largest ordinary persistence, so this stays a
    fully independent check of the graded signature."""
    hf = [field[r][c] for r in range(n) for c in range(n)]
    hg = [-x for x in hf]
    edges = _edges_of(n)
    simp = ref.grid_simplices(n)
    ord0 = _uf_h0(hf, edges)
    rel0 = _uf_h0(hg, edges)
    alt_f = _alt_finite_bars(hf, simp)
    alt_g = _alt_finite_bars(hg, simp)
    ord1 = sorted(alt_f[1], reverse=True)
    rel1 = sorted(alt_g[1], reverse=True)
    # cross the two H0 methods too
    assert ord0 == sorted(alt_f[0], reverse=True)
    assert rel0 == sorted(alt_g[0], reverse=True)
    vmin = min(hf)
    vmax = max(hf)
    sig = (max(ord0 + ord1) if (ord0 + ord1) else 0) // 4

    def st(lst):
        kept = [p for p in lst if p > sig]
        return [
            len(kept),
            sum(kept),
            kept[0] if kept else 0,
            kept[1] if len(kept) >= 2 else 0,
        ]

    return tuple(st(ord0) + st(ord1) + st(rel0) + st(rel1) + [vmax - vmin])


# --------------------------------------------------------------------------
# Data directory writer.
# --------------------------------------------------------------------------
def write_dir(dst, fields, ref_labels, queries, scramble_seed=None, structures=None):
    os.makedirs(dst, exist_ok=True)
    rows = []
    for sid, (V, n) in fields.items():
        for r in range(n):
            for c in range(n):
                rows.append([sid, r, c, V[r][c]])
    if scramble_seed is not None:
        random.Random(scramble_seed).shuffle(rows)
    with open(os.path.join(dst, "field.csv"), "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["structure_id", "row", "col", "value"])
        w.writerows(rows)
    with open(os.path.join(dst, "reference_labels.csv"), "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["structure_id", "fold_group"])
        for sid in sorted(ref_labels):
            w.writerow([sid, ref_labels[sid]])
    with open(os.path.join(dst, "queries.csv"), "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["structure_id"])
        for sid in sorted(queries):
            w.writerow([sid])
    with open(os.path.join(dst, "structures.csv"), "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["structure_id", "role", "size"])
        if structures is None:
            for sid in sorted(ref_labels):
                w.writerow([sid, "reference", fields[sid][1]])
            for sid in sorted(queries):
                w.writerow([sid, "query", fields[sid][1]])
        else:
            for row in structures:
                w.writerow(row)
    # Keep every on-the-fly data dir world-readable/traversable; tempfile makes 0700.
    os.chmod(dst, 0o755)
    for fn in ("field.csv", "reference_labels.csv", "queries.csv", "structures.csv"):
        os.chmod(os.path.join(dst, fn), 0o644)


def load_shipped_fields():
    return ref.load_fields(DATA)


def _shipped_refs():
    out = {}
    with open(os.path.join(DATA, "reference_labels.csv")) as fh:
        for row in csv.DictReader(fh):
            out[row["structure_id"]] = row["fold_group"]
    return out


# --------------------------------------------------------------------------
# Shipped-data grading.
# --------------------------------------------------------------------------
@pytest.fixture(scope="session")
def shipped_run():
    return run_agent(DATA)


@pytest.fixture(scope="session")
def shipped_truth():
    return ref.classify(DATA)


@pytest.mark.parametrize("qid", SHIPPED_QUERIES)
def test_matches_independent_oracle(shipped_run, shipped_truth, qid):
    """Each shipped query's whole output line equals the independent oracle."""
    assert qid in shipped_run, "candidate produced no line for %s" % qid
    assert shipped_run[qid] == shipped_truth[qid], (
        "candidate %r != oracle %r for %s"
        % (
            shipped_run[qid],
            shipped_truth[qid],
            qid,
        )
    )


def test_emits_one_line_per_query(shipped_run):
    """Exactly one output line per shipped query, and nothing else."""
    assert set(shipped_run.keys()) == set(SHIPPED_QUERIES)
    assert len(shipped_run) == len(SHIPPED_QUERIES)


@pytest.mark.parametrize("qid", SHIPPED_QUERIES)
def test_shipped_features_cross_oracle(shipped_run, qid):
    """Shipped features agree with the union-find H0 oracle and the alternate
    reduction, and the candidate reproduces them."""
    fields = load_shipped_fields()
    V, n = fields[qid]
    exp = ref.features(V, n)
    assert exp == cross_features(V, n), "cross-oracle disagrees on %s" % qid
    assert shipped_run[qid][2] == exp, "candidate features wrong on %s" % qid


def test_relative_families_load_bearing(shipped_run):
    """The relative (superlevel) families survive the floor on the shipped queries,
    so a signature that omits them cannot reproduce the graded output."""
    nonzero = 0
    for qid in SHIPPED_QUERIES:
        f = shipped_run[qid][2]
        if f[8] > 0 or f[12] > 0:  # Rel_0 count or Rel_1 count
            nonzero += 1
    assert nonzero >= 12, "relative families vacuous on too many queries: %d" % nonzero


def test_significance_floor_load_bearing(shipped_run, shipped_truth):
    """The significance floor discards bars on the shipped queries, so a solver that
    summarizes every bar (the whole pre-floor signature) reproduces almost none of
    the graded output."""
    unfloored = wrong_refs.classify(DATA, "no_floor")
    changed = [q for q in shipped_truth if unfloored[q][2] != shipped_truth[q][2]]
    assert len(changed) >= 20, "floor changes too few signatures: %d" % len(changed)
    for q in shipped_truth:
        assert shipped_run[q] == shipped_truth[q]


# Constructed field with a relative bar of persistence exactly equal to the floor,
# so `> floor` (correct) and `>= floor` differ on it. Found by deterministic search.
SIGMA_BOUNDARY_FIELD = [
    [5, -6, 6, -2, -1],
    [-3, -2, 3, 0, -4],
    [-1, -5, 0, -2, 2],
    [4, -4, 3, 2, -4],
    [-1, 5, 5, -5, 2],
]


def test_sigma_boundary_is_strict():
    """A bar whose persistence equals the floor is excluded (strict `>`), not kept.
    The candidate must reproduce the strict-boundary signature, which differs from the
    at-or-above variant on this constructed field."""
    V = SIGMA_BOUNDARY_FIELD
    n = len(V)
    strict = ref.features(V, n)
    at_or_above = wrong_refs.features_mode(V, n, "floor_ge")
    assert strict != at_or_above, "boundary field no longer exercises the floor edge"
    assert strict == cross_features(V, n), "cross-oracle disagrees on boundary field"
    fields = {
        "AAA": (_const(3, 0), 3),
        "BBB": ([[0, 2, 0], [2, 4, 2], [0, 2, 0]], 3),
        "Q": (V, n),
    }
    with tempfile.TemporaryDirectory() as d:
        write_dir(d, fields, {"AAA": "x", "BBB": "y"}, ["Q"])
        got = run_agent(d)
    assert got["Q"][2] == strict, "candidate does not use the strict floor boundary"


def test_single_cell_perturbation_changes_output():
    """Bumping one interior cell of a shipped query changes its graded signature, and
    the candidate tracks the change exactly; a solver blind to a single vertex fails."""
    fields = load_shipped_fields()
    base_V, n = fields["Q000"]
    pert = [row[:] for row in base_V]
    pert[n // 2][n // 2] += 137
    variant = dict(fields)
    variant["Q000"] = (pert, n)
    with tempfile.TemporaryDirectory() as d:
        write_dir(d, variant, _shipped_refs(), SHIPPED_QUERIES)
        got = run_agent(d)
        truth = ref.classify(d)
    assert got["Q000"][2] != ref.features(base_V, n), (
        "perturbation left signature unchanged"
    )
    assert got == truth


def test_agent_is_deterministic():
    """Three independent runs on the shipped data are identical."""
    runs = [run_agent(DATA) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


# --------------------------------------------------------------------------
# Metamorphic invariances.
# --------------------------------------------------------------------------
def test_input_row_order_invariance():
    """Result is invariant to field.csv row order; a positional reader is wrong."""
    fields = load_shipped_fields()
    refs = _shipped_refs()
    with tempfile.TemporaryDirectory() as d1:
        write_dir(d1, fields, refs, SHIPPED_QUERIES)
        ordered = run_agent(d1)
    with tempfile.TemporaryDirectory() as d2:
        write_dir(d2, fields, refs, SHIPPED_QUERIES, scramble_seed=987654321)
        scrambled = run_agent(d2)
    assert ordered == scrambled
    assert len(scrambled) == len(SHIPPED_QUERIES)


def test_global_value_shift_invariance():
    """Adding a constant to every value leaves the full output unchanged."""
    base = run_agent(DATA)
    fields = load_shipped_fields()
    shifted = {
        sid: ([[v + 100000 for v in row] for row in V], n)
        for sid, (V, n) in fields.items()
    }
    with tempfile.TemporaryDirectory() as d:
        write_dir(d, shifted, _shipped_refs(), SHIPPED_QUERIES)
        got = run_agent(d)
    assert got == base


def test_structures_table_non_authoritative():
    """An inconsistent structures.csv (inverted roles, wrong sizes, a decoy, an
    omitted structure) plus a distractor field must not change the result."""
    fields = {
        "AAA": ([[0, 3, 0], [3, 0, 3], [0, 3, 0]], 3),
        "BBB": ([[5, 1, 5], [1, 5, 1], [5, 1, 5]], 3),
        "Q1": ([[0, 4, 1, 0], [4, 0, 4, 2], [1, 4, 0, 3], [0, 2, 3, 0]], 4),
        "ZDECOY": ([[9, 0, 9], [0, 9, 0], [9, 0, 9]], 3),
    }
    ref_labels = {"AAA": "x", "BBB": "y"}
    queries = ["Q1"]
    liar = [
        ["AAA", "query", 999],
        ["Q1", "reference", 1],
        ["ZDECOY", "reference", 7],
        ["GHOST", "reference", 3],
    ]
    with tempfile.TemporaryDirectory() as d:
        write_dir(d, fields, ref_labels, queries, structures=liar)
        got = run_agent(d)
        truth = ref.classify(d)
    assert set(got) == {"Q1"}
    assert got["Q1"] == truth["Q1"]


def test_decoys_never_emitted():
    """A reference or extra structure is never emitted as a query line."""
    fields = {
        "R0": ([[0, 2, 0], [2, 5, 2], [0, 2, 0]], 3),
        "R1": ([[5, 2, 5], [2, 0, 2], [5, 2, 5]], 3),
        "QA": ([[1, 3, 1], [3, 6, 3], [1, 3, 1]], 3),
        "EXTRA": ([[9, 9, 9], [9, 0, 9], [9, 9, 9]], 3),
    }
    with tempfile.TemporaryDirectory() as d:
        write_dir(d, fields, {"R0": "a", "R1": "b"}, ["QA"])
        got = run_agent(d)
    assert set(got) == {"QA"}
    for x in ("R0", "R1", "EXTRA"):
        assert x not in got


# --------------------------------------------------------------------------
# Edge cases.
# --------------------------------------------------------------------------
def _const(n, val):
    return [[val] * n for _ in range(n)]


EDGE_FIELDS = {
    "flat0": _const(4, 0),
    "flat7": _const(5, 7),
    "min2": [[0, 5], [5, 0]],
    "one_pit": [[0, 0, 0, 0], [0, -9, -9, 0], [0, -9, -9, 0], [0, 0, 0, 0]],
    "one_peak": [[0, 0, 0, 0], [0, 9, 9, 0], [0, 9, 9, 0], [0, 0, 0, 0]],
    "ramp": [[i + j for j in range(6)] for i in range(6)],
    "checker": [
        [(10 if (i + j) % 2 == 0 else -10) for j in range(6)] for i in range(6)
    ],
    "saddle": [[i * i - j * j for j in range(5)] for i in range(5)],
    "twin_peaks": [
        [0, 0, 0, 0, 0, 0, 0],
        [0, 8, 0, 0, 0, 6, 0],
        [0, 8, 0, 0, 0, 6, 0],
        [0, 0, 0, 0, 0, 0, 0],
        [0, 5, 0, 0, 0, 7, 0],
        [0, 5, 0, 0, 0, 7, 0],
        [0, 0, 0, 0, 0, 0, 0],
    ],
    "min8": [
        [3, 1, 4, 1, 5, 9, 2, 6],
        [5, 3, 5, 8, 9, 7, 9, 3],
        [2, 3, 8, 4, 6, 2, 6, 4],
        [3, 3, 8, 3, 2, 7, 9, 5],
        [0, 2, 8, 8, 4, 1, 9, 7],
        [1, 6, 9, 3, 9, 9, 3, 7],
        [5, 1, 0, 5, 8, 2, 0, 9],
        [7, 4, 9, 4, 4, 5, 9, 2],
    ],
}


@pytest.mark.parametrize("name", sorted(EDGE_FIELDS))
def test_edge_case_features(name):
    """Hand-picked edge-case fields: candidate features match every oracle."""
    V = EDGE_FIELDS[name]
    n = len(V)
    fields = {
        "AAA": (_const(3, 0), 3),
        "BBB": ([[0, 2, 0], [2, 4, 2], [0, 2, 0]], 3),
        "Q": (V, n),
    }
    with tempfile.TemporaryDirectory() as d:
        write_dir(d, fields, {"AAA": "x", "BBB": "y"}, ["Q"])
        got = run_agent(d)
    exp = ref.features(V, n)
    assert exp == cross_features(V, n), "oracles disagree on %s" % name
    assert got["Q"][2] == exp, "candidate wrong on %s: %s vs %s" % (
        name,
        got["Q"][2],
        exp,
    )


def test_flat_field_is_all_zero():
    """A constant field has empty diagrams and zero span."""
    V = _const(5, 4)
    assert ref.features(V, 5) == tuple([0] * NF)


# --------------------------------------------------------------------------
# Synthetic battery.
# --------------------------------------------------------------------------
def _rand_field(rng, n, lo, hi):
    return [[rng.randint(lo, hi) for _ in range(n)] for _ in range(n)]


def _make_battery(seed, count):
    rng = random.Random(seed)
    fields = {}
    ref_labels = {}
    queries = []
    for r in range(8):
        n = rng.choice([8, 10, 12])
        fields["R%02d" % r] = (
            _rand_field(rng, n, -rng.choice([5, 50, 300]), rng.choice([5, 50, 300])),
            n,
        )
        ref_labels["R%02d" % r] = "g%d" % (r % 3)
    for k in range(count):
        n = rng.choice([8, 9, 10, 11, 12, 13, 14])
        span = rng.choice([4, 30, 200, 2000])
        fields["Q%02d" % k] = (_rand_field(rng, n, -span, span), n)
        queries.append("Q%02d" % k)
    return fields, ref_labels, queries


@pytest.fixture(scope="session")
def synth():
    fields, ref_labels, queries = _make_battery(seed=20260718, count=40)
    d = tempfile.mkdtemp(prefix="synth_")
    write_dir(d, fields, ref_labels, queries)
    return d, run_agent(d), ref.classify(d), fields, ref_labels, queries


@pytest.mark.parametrize("k", range(40))
def test_synthetic_query_matches_oracle(synth, k):
    """Each synthetic query's whole output line equals the oracle, and the oracle
    agrees with the independent cross-recomputation."""
    d, got, truth, fields, ref_labels, queries = synth
    qid = "Q%02d" % k
    V, n = fields[qid]
    assert ref.features(V, n) == cross_features(V, n), (
        "cross-oracle disagrees on %s" % qid
    )
    assert got[qid] == truth[qid], "candidate %r != oracle %r on %s" % (
        got[qid],
        truth[qid],
        qid,
    )


def test_synthetic_battery_size(synth):
    """The graded battery clears the behavioral floor of 60 distinct cases."""
    d, got, truth, fields, ref_labels, queries = synth
    distinct = len(queries) + len(SHIPPED_QUERIES) + len(EDGE_FIELDS) + 8
    assert distinct >= 60, "only %d distinct cases" % distinct


def test_no_vacuous_feature_column(shipped_truth, synth):
    """Every one of the seventeen features takes at least two distinct values across
    the graded battery, so no column is a free pass a constant-wrong output could
    satisfy; each is genuinely tied to the recompute."""
    d, got, truth, fields, ref_labels, queries = synth
    vecs = [shipped_truth[q][2] for q in shipped_truth]
    vecs += [truth[q][2] for q in queries]
    for _name, V in EDGE_FIELDS.items():
        vecs.append(ref.features(V, len(V)))
    for i in range(NF):
        assert len({v[i] for v in vecs}) >= 2, "feature column %d is vacuous" % (i + 1)


def test_large_magnitude_exact():
    """Large-magnitude fields keep every integer exact (totals of squared spans
    are not used, but sums cross into the millions)."""
    rng = random.Random(4242)
    fields = {}
    ref_labels = {}
    queries = []
    for r in range(4):
        fields["R%d" % r] = (_rand_field(rng, 10, -500000, 500000), 10)
        ref_labels["R%d" % r] = "g%d" % (r % 2)
    for k in range(6):
        fields["Q%d" % k] = (_rand_field(rng, 12, -900000, 900000), 12)
        queries.append("Q%d" % k)
    with tempfile.TemporaryDirectory() as d:
        write_dir(d, fields, ref_labels, queries)
        got = run_agent(d)
        truth = ref.classify(d)
    assert got == truth
    assert max(truth[q][2][16] for q in queries) > 1000000, "spans never large"


# --------------------------------------------------------------------------
# Hidden, value-disjoint battery.
# --------------------------------------------------------------------------
def _load_hidden():
    def read_field(path):
        cells = {}
        maxrc = {}
        with open(path) as fh:
            for row in csv.DictReader(fh):
                sid = row["structure_id"]
                r = int(row["row"])
                c = int(row["col"])
                cells.setdefault(sid, {})[(r, c)] = int(row["value"])
                maxrc[sid] = max(maxrc.get(sid, 0), r, c)
        out = {}
        for sid, dd in cells.items():
            n = maxrc[sid] + 1
            V = [[0] * n for _ in range(n)]
            for (r, c), v in dd.items():
                V[r][c] = v
            out[sid] = (V, n)
        return out

    fields = read_field(os.path.join(HERE, "hidden_field.csv"))
    ref_labels = {}
    with open(os.path.join(HERE, "hidden_reference_labels.csv")) as fh:
        for row in csv.DictReader(fh):
            ref_labels[row["structure_id"]] = row["fold_group"]
    queries = []
    with open(os.path.join(HERE, "hidden_queries.csv")) as fh:
        for row in csv.DictReader(fh):
            queries.append(row["structure_id"])
    return fields, ref_labels, queries


def test_hidden_value_disjoint_battery():
    """The candidate matches the oracle on hidden structures whose integer values are
    disjoint from every shipped value, so no shipped answer can be memorized."""
    fields, ref_labels, queries = _load_hidden()
    shipped_vals = set()
    for _sid, (V, n) in load_shipped_fields().items():
        for row in V:
            shipped_vals.update(row)
    hidden_vals = set()
    for _sid, (V, n) in fields.items():
        for row in V:
            hidden_vals.update(row)
    assert shipped_vals.isdisjoint(hidden_vals), "hidden values overlap shipped values"
    with tempfile.TemporaryDirectory() as d:
        write_dir(d, fields, ref_labels, queries)
        got = run_agent(d)
        truth = ref.classify(d)
    assert set(got) == set(queries)
    assert got == truth
    for q in queries:
        V, n = fields[q]
        assert ref.features(V, n) == cross_features(V, n), (
            "cross-oracle disagrees on %s" % q
        )


# --------------------------------------------------------------------------
# Anti-gaming: every broken obligation misgrades the data.
# --------------------------------------------------------------------------
# Obligations whose breach reshapes many shipped signatures at once.
STRONG_MODES = [
    "sublevel_only",
    "upper_star",
    "swap_ord_rel",
    "swap_rel_ext",
    "ext_zero",
    "ext_abs",
    "no_floor",
    "floor_div_wrong",
]


def test_naive_no_floor_wrong_on_every_query(shipped_run, shipped_truth):
    """A solver that summarizes every bar without the significance floor -- the whole
    pre-floor signature -- misgrades every shipped query, while the candidate matches
    the oracle everywhere."""
    bad = wrong_refs.classify(DATA, "no_floor")
    for q in shipped_truth:
        assert bad[q] != shipped_truth[q], "no-floor accidentally correct on %s" % q
        assert shipped_run[q] == shipped_truth[q]


@pytest.mark.parametrize("mode", sorted(wrong_refs.MODES))
def test_wrong_baseline_diverges_on_shipped(shipped_run, shipped_truth, mode):
    """Breaking any single disclosed obligation misgrades at least one shipped query,
    so no broken pipeline reaches a perfect score; the candidate matches everywhere."""
    bad = wrong_refs.classify(DATA, mode)
    diverged = [q for q in shipped_truth if bad[q] != shipped_truth[q]]
    assert len(diverged) >= 1, "obligation %r (%s) never bit the shipped battery" % (
        mode,
        wrong_refs.MODES[mode],
    )
    for q in shipped_truth:
        assert shipped_run[q] == shipped_truth[q]


@pytest.mark.parametrize("mode", STRONG_MODES)
def test_strong_obligations_bite_hard(shipped_truth, mode):
    """The whole-signature obligations reshape a large share of the shipped output, so
    passing them by luck is impossible."""
    bad = wrong_refs.classify(DATA, mode)
    diverged = [q for q in shipped_truth if bad[q] != shipped_truth[q]]
    assert len(diverged) >= 8, "obligation %r misgrades too few: %d" % (
        mode,
        len(diverged),
    )


@pytest.mark.parametrize("mode", sorted(wrong_refs.MODES))
def test_wrong_baseline_diverges_on_synth(synth, mode):
    """On the disjoint synthetic battery every broken obligation still misgrades some
    query, and the candidate matches the oracle throughout."""
    d, got, truth, fields, ref_labels, queries = synth
    bad = wrong_refs.classify(d, mode)
    assert any(bad[q] != truth[q] for q in queries), (
        "obligation %r never bit the synthetic battery" % mode
    )
    for q in queries:
        assert got[q] == truth[q]
