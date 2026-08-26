"""Wrong reference implementations used only for anti-gaming evidence.

Each variant breaks exactly one disclosed obligation of the analysis contract and
otherwise follows it, so it produces a different signature, and usually a different
retrieval, from the independent oracle (ref.py). These live only in the verifier;
the candidate never sees them."""

import ref

MODES = {
    "sublevel_only": "computes only ordinary sublevel persistence; leaves Rel families zero",
    "upper_star": "filters simplices by the minimum vertex value, not the maximum",
    "swap_ord_rel": "labels the ascending bars as relative and the descending bars as ordinary",
    "swap_rel_ext": "counts the essential min-to-max class as a Rel_0 bar and drops ext0",
    "ext_zero": "fails to pair the essential class, reporting ext0 = 0",
    "ext_abs": "reports the essential class as the absolute maximum, not the max-minus-min span",
    "no_floor": "summarizes every bar, never applying the significance floor",
    "floor_ge": "keeps bars at the floor (persistence >= sigma) instead of strictly above it",
    "floor_div_wrong": "uses M/2 for the floor instead of M/4",
    "floor_all_bars": "derives the floor from the largest bar of any family, not the largest ordinary bar",
}

_FLOOR_MODES = {"no_floor", "floor_ge", "floor_div_wrong", "floor_all_bars"}


def _finite_bars_mode(height, simplices, mode):
    verts, edges, tris = simplices
    allsimp = []

    def fval(s):
        vals = [height[v] for v in s]
        return min(vals) if mode == "upper_star" else max(vals)

    for s in verts:
        allsimp.append((fval(s), 0, s))
    for s in edges:
        allsimp.append((fval(s), 1, s))
    for s in tris:
        allsimp.append((fval(s), 2, s))
    if mode == "upper_star":
        allsimp.sort(key=lambda t: (t[0], -t[1], t[2]))
    else:
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
                        fin[p].append(abs(death - birth))
                break
    return fin


def features_mode(field, n, mode):
    simp = ref.grid_simplices(n)
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
    sub = _finite_bars_mode(hf, simp, mode)
    if mode == "sublevel_only":
        sup = {0: [], 1: []}
    else:
        sup = _finite_bars_mode(hg, simp, mode)
    o0 = sorted(sub[0], reverse=True)
    o1 = sorted(sub[1], reverse=True)
    r0 = sorted(sup[0], reverse=True)
    r1 = sorted(sup[1], reverse=True)
    ext0 = vmax - vmin
    if mode == "swap_ord_rel":
        o0, r0 = r0, o0
        o1, r1 = r1, o1
    if mode == "swap_rel_ext":
        r0 = sorted(r0 + [ext0], reverse=True)
        ext0 = 0
    if mode == "ext_zero":
        ext0 = 0
    if mode == "ext_abs":
        ext0 = vmax

    ordinary = o0 + o1
    pool_all = o0 + o1 + r0 + r1
    if mode == "no_floor":
        fam = [o0, o1, r0, r1]
    else:
        if mode == "floor_all_bars":
            m = max(pool_all) if pool_all else 0
        else:
            m = max(ordinary) if ordinary else 0
        sigma = m // 2 if mode == "floor_div_wrong" else m // 4
        if mode == "floor_ge":
            fam = [[p for p in fm if p >= sigma] for fm in (o0, o1, r0, r1)]
        else:
            fam = [[p for p in fm if p > sigma] for fm in (o0, o1, r0, r1)]

    def st(lst):
        return [
            len(lst),
            sum(lst),
            lst[0] if lst else 0,
            lst[1] if len(lst) >= 2 else 0,
        ]

    out = []
    for fm in fam:
        out += st(fm)
    out.append(ext0)
    return tuple(out)


def classify(csv_dir, mode):
    """Whole-dataset classification with the single obligation `mode` broken."""
    fields = ref.load_fields(csv_dir)
    refs = []
    import csv as _csv
    import os as _os

    with open(_os.path.join(csv_dir, "reference_labels.csv")) as fh:
        for row in _csv.DictReader(fh):
            refs.append((row["structure_id"], row["fold_group"]))
    refs.sort()
    queries = []
    with open(_os.path.join(csv_dir, "queries.csv")) as fh:
        for row in _csv.DictReader(fh):
            queries.append(row["structure_id"])
    queries.sort()
    ref_feat = {sid: features_mode(*fields[sid], mode) for sid, _g in refs}
    out = {}
    for q in queries:
        fq = features_mode(*fields[q], mode)
        best = None
        for sid, grp in refs:
            dist = sum(abs(a - b) for a, b in zip(fq, ref_feat[sid]))
            if best is None or dist < best[0]:
                best = (dist, sid, grp)
        out[q] = (best[1], best[2], fq)
    return out
