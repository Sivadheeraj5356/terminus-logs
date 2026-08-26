"""Independent replay oracle for the delayed-label varying-dimension coupled-ridge stream."""

import csv
import os
from fractions import Fraction


def read_config(d):
    cfg = {}
    with open(os.path.join(d, "config.csv"), newline="") as f:
        for row in csv.DictReader(f):
            cfg[row["key"]] = row["value"]
    return {
        "grace_G": int(cfg["grace_G"]),
        "lam": Fraction(int(cfg["ridge_lambda_num"]), int(cfg["ridge_lambda_den"])),
        "scale": int(cfg["value_scale"]),
        "label_delay": int(cfg["label_delay"]),
    }


def scaled_int(text, scale):
    value = Fraction(text) * scale
    if value.denominator != 1:
        raise ValueError(f"value {text!r} is not exact under scale {scale}")
    return value.numerator


def read_events(d, scale):
    with open(os.path.join(d, "events.csv"), newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        feat_ids = [int(c) for c in header[2:]]
        events = []
        for row in reader:
            present = {}
            for fid, cell in zip(feat_ids, row[2:]):
                if cell != "":
                    present[fid] = scaled_int(cell, scale)
            events.append(present)
    return feat_ids, events


def read_targets(d, scale):
    targets = {}
    with open(os.path.join(d, "targets.csv"), newline="") as f:
        for row in csv.DictReader(f):
            y = row["y"]
            targets[int(row["event_id"])] = None if y == "" else scaled_int(y, scale)
    return targets


def read_pairs(d, name, key_a, key_b):
    out = []
    with open(os.path.join(d, name), newline="") as f:
        for row in csv.DictReader(f):
            out.append((int(row[key_a]), int(row[key_b])))
    return out


def solve(active, gram, bvec, lam):
    d = len(active)
    if d == 0:
        return {}
    mat = [
        [
            Fraction(gram.get((active[i], active[j]), 0)) + (lam if i == j else 0)
            for j in range(d)
        ]
        for i in range(d)
    ]
    rhs = [Fraction(bvec.get(active[i], 0)) for i in range(d)]
    for col in range(d):
        piv = next((r for r in range(col, d) if mat[r][col] != 0), None)
        if piv is None:
            continue
        mat[col], mat[piv] = mat[piv], mat[col]
        rhs[col], rhs[piv] = rhs[piv], rhs[col]
        p = mat[col][col]
        for r in range(d):
            if r != col and mat[r][col] != 0:
                factor = mat[r][col] / p
                for c in range(col, d):
                    mat[r][c] -= factor * mat[col][c]
                rhs[r] -= factor * rhs[col]
    return {
        active[i]: (rhs[i] / mat[i][i] if mat[i][i] != 0 else Fraction(0))
        for i in range(d)
    }


def compute(d):
    cfg = read_config(d)
    grace = cfg["grace_G"]
    lam = cfg["lam"]
    scale = cfg["scale"]
    delay = cfg["label_delay"]
    feat_ids, events = read_events(d, scale)
    targets = read_targets(d, scale)
    queries = read_pairs(d, "queries.csv", "query_id", "at_event")
    ckpts = read_pairs(d, "checkpoints.csv", "checkpoint_id", "at_event")

    q_at = {}
    for qid, at in queries:
        q_at.setdefault(at, []).append(qid)
    c_at = {}
    for cid, at in ckpts:
        c_at.setdefault(at, []).append(cid)

    active = []
    active_set = set()
    gram = {}
    bvec = {}
    absent = {}
    pending = {}

    predictions = {}
    checkpoints = {}

    for eid, present in enumerate(events):
        for fid in sorted(present):
            if fid not in active_set:
                active.append(fid)
                active_set.add(fid)
                bvec[fid] = 0
                gram[(fid, fid)] = 0
                absent[fid] = 0
        for fid in list(active):
            if fid in present:
                absent[fid] = 0
            else:
                absent[fid] += 1
                if absent[fid] > grace:
                    active.remove(fid)
                    active_set.discard(fid)
                    del bvec[fid]
                    del absent[fid]
                    for key in [k for k in gram if fid in k]:
                        del gram[key]
                    for comp, _ in pending.values():
                        comp.pop(fid, None)
        x = {fid: present[fid] for fid in present if fid in active_set}
        if eid in q_at:
            weights = solve(active, gram, bvec, lam)
            yhat = sum(
                (weights.get(fid, Fraction(0)) * x[fid] for fid in x), Fraction(0)
            )
            for qid in q_at[eid]:
                predictions[qid] = yhat
        due = pending.pop(eid - delay, None)
        if due is not None:
            comp, y = due
            items = list(comp.items())
            for fi, xi in items:
                bvec[fi] = bvec.get(fi, 0) + y * xi
                for fj, xj in items:
                    gram[(fi, fj)] = gram.get((fi, fj), 0) + xi * xj
        y_now = targets.get(eid)
        if y_now is not None:
            pending[eid] = (dict(x), y_now)
        if eid in c_at:
            act = sorted(active)
            tri = [
                [act[i], act[j], gram.get((act[i], act[j]), 0)]
                for i in range(len(act))
                for j in range(i, len(act))
            ]
            weights = solve(active, gram, bvec, lam)
            snap = {
                "active": act,
                "gram": tri,
                "b": [[fid, bvec.get(fid, 0)] for fid in act],
                "weights": [[fid, weights.get(fid, Fraction(0))] for fid in act],
            }
            for cid in c_at[eid]:
                checkpoints[cid] = snap

    return {
        "n_events": len(events),
        "predictions": predictions,
        "checkpoints": checkpoints,
    }
