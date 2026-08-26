"""Independent verifier-side oracle for the extended-persistence fold signature.

Extended persistence over the field F2 of the 2-D lower-star filtration of an
integer scalar field, read in dimensions 0 and 1. The ascending (sublevel) pass
gives the ordinary bars Ord_0 and Ord_1; the descending (superlevel) pass gives
the relative bars Rel_0 and Rel_1; the single essential class spans the global
minimum to the global maximum (ext0). Before each family is summarized, bars whose
persistence does not strictly exceed the significance floor (one quarter of the
largest ordinary persistence) are discarded, so every count/total/max/second is
over the surviving bars only. Each family contributes count, total, maximum and
second-largest persistence, giving a seventeen-integer signature, and each query is
labelled by its L1-nearest reference. Implemented separately from the
candidate's Rust program; every quantity is an integer, so agent and verifier agree
exactly with no float tolerance. References come only from reference_labels.csv and
queries only from queries.csv; structures.csv is ignored."""

import csv
import os

NF = 17


def grid_simplices(n):
    """Vertices (vid,), edges (u,v) [horizontal, vertical, diagonal], and the two
    triangles per unit square. Vertex id of grid point (r, c) is r * n + c."""
    verts = [(r * n + c,) for r in range(n) for c in range(n)]
    edges = []
    for r in range(n):
        for c in range(n):
            v = r * n + c
            if c + 1 < n:
                edges.append((v, v + 1))
            if r + 1 < n:
                edges.append((v, v + n))
    tris = []
    for r in range(n - 1):
        for c in range(n - 1):
            a = r * n + c
            b = r * n + c + 1
            d = (r + 1) * n + c
            e = (r + 1) * n + c + 1
            edges.append((a, e))
            tris.append((a, b, e))
            tris.append((a, d, e))
    return verts, edges, tris


def _finite_bars(height, simplices):
    """Ordinary persistent homology (F2) of the lower-star filtration given vertex
    heights. Filtration value of a simplex is the maximum height over its vertices.
    Returns finite bars {0: [persistences], 1: [persistences]} with strictly
    positive persistence."""
    verts, edges, tris = simplices
    allsimp = []
    for s in verts:
        allsimp.append((height[s[0]], 0, s))
    for s in edges:
        allsimp.append((max(height[s[0]], height[s[1]]), 1, s))
    for s in tris:
        allsimp.append((max(height[s[0]], height[s[1]], height[s[2]]), 2, s))
    allsimp.sort(key=lambda t: (t[0], t[1], t[2]))
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
                    birth = filt[low]
                    death = filt[j]
                    if death > birth:
                        fin[p].append(death - birth)
                break
    return fin


def diagram(field, n):
    """Return the four bar families (as persistence lists, descending) plus ext0."""
    simp = grid_simplices(n)
    hf = [0] * (n * n)
    hg = [0] * (n * n)
    vmin = None
    vmax = None
    for r in range(n):
        for c in range(n):
            val = field[r][c]
            hf[r * n + c] = val
            hg[r * n + c] = -val
            if vmin is None or val < vmin:
                vmin = val
            if vmax is None or val > vmax:
                vmax = val
    sub = _finite_bars(hf, simp)
    sup = _finite_bars(hg, simp)
    return {
        ("Ord", 0): sorted(sub[0], reverse=True),
        ("Ord", 1): sorted(sub[1], reverse=True),
        ("Rel", 0): sorted(sup[0], reverse=True),
        ("Rel", 1): sorted(sup[1], reverse=True),
        "ext0": vmax - vmin,
    }


def _stat4(lst):
    return [len(lst), sum(lst), lst[0] if lst else 0, lst[1] if len(lst) >= 2 else 0]


def significance_floor(ordinary):
    """Floor a bar's persistence must strictly exceed to enter its family's
    summary: one quarter (rounded down) of the largest ordinary persistence in
    the structure, or 0 when the structure has no ordinary bar."""
    m = max(ordinary) if ordinary else 0
    return m // 4


def features(field, n):
    """The seventeen-integer signature of one field."""
    fam = diagram(field, n)
    o0, o1 = fam[("Ord", 0)], fam[("Ord", 1)]
    r0, r1 = fam[("Rel", 0)], fam[("Rel", 1)]
    s = significance_floor(o0 + o1)
    f = []
    f += _stat4([p for p in o0 if p > s])
    f += _stat4([p for p in o1 if p > s])
    f += _stat4([p for p in r0 if p > s])
    f += _stat4([p for p in r1 if p > s])
    f.append(fam["ext0"])
    return tuple(f)


def load_fields(csv_dir):
    """Return {structure_id: (field, n)} from field.csv, read by (row, col)."""
    cells = {}
    maxrc = {}
    with open(os.path.join(csv_dir, "field.csv")) as fh:
        for row in csv.DictReader(fh):
            sid = row["structure_id"]
            r = int(row["row"])
            c = int(row["col"])
            v = int(row["value"])
            cells.setdefault(sid, {})[(r, c)] = v
            maxrc[sid] = max(maxrc.get(sid, 0), r, c)
    out = {}
    for sid, d in cells.items():
        n = maxrc[sid] + 1
        field = [[0] * n for _ in range(n)]
        for (r, c), v in d.items():
            field[r][c] = v
        out[sid] = (field, n)
    return out


def classify(csv_dir):
    """Return {query_id: (retrieved_ref_id, fold_group, feature_tuple)}."""
    fields = load_fields(csv_dir)
    refs = []
    with open(os.path.join(csv_dir, "reference_labels.csv")) as fh:
        for row in csv.DictReader(fh):
            refs.append((row["structure_id"], row["fold_group"]))
    refs.sort()
    queries = []
    with open(os.path.join(csv_dir, "queries.csv")) as fh:
        for row in csv.DictReader(fh):
            queries.append(row["structure_id"])
    queries.sort()
    ref_feat = {sid: features(*fields[sid]) for sid, _g in refs}
    out = {}
    for q in queries:
        fq = features(*fields[q])
        best = None
        for sid, grp in refs:
            dist = sum(abs(a - b) for a, b in zip(fq, ref_feat[sid]))
            if best is None or dist < best[0]:
                best = (dist, sid, grp)
        out[q] = (best[1], best[2], fq)
    return out
