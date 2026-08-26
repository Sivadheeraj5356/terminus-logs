"""Independent oracle for cross-conformal p-values, sets, and diagnostics.

Reads a bundle directory and recomputes every graded quantity with
fractions.Fraction, entirely independently of the candidate program.
"""

import csv
import os
from fractions import Fraction


def _read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_bundle(bundle_dir):
    b = {}
    b["cells"] = _read(os.path.join(bundle_dir, "terrain_cells.csv"))
    b["labels"] = _read(os.path.join(bundle_dir, "cover_labels.csv"))
    b["registry"] = _read(os.path.join(bundle_dir, "fold_registry.csv"))
    b["cal"] = _read(os.path.join(bundle_dir, "fold_scores_calibration.csv"))
    b["ev"] = _read(os.path.join(bundle_dir, "fold_scores_evaluation.csv"))
    b["grid"] = _read(os.path.join(bundle_dir, "decision_grid.csv"))
    return b


def compute(bundle_dir):
    b = load_bundle(bundle_dir)
    classes = list(range(1, 8))

    member_fold = {r["cell_id"]: int(r["fold"]) for r in b["registry"]}
    fold_universe = sorted({int(r["fold"]) for r in b["ev"]})

    # calibration multiset of fold k: scores (context k) of cells assigned to k
    cal_score = {(r["cell_id"], int(r["fold"])): int(r["score_q"]) for r in b["cal"]}
    S = {k: [] for k in fold_universe}
    for cell, k in member_fold.items():
        if k in S and (cell, k) in cal_score:
            S[k].append(cal_score[(cell, k)])

    ev = {}
    for r in b["ev"]:
        ev[(r["cell_id"], int(r["fold"]), int(r["class_id"]))] = (
            int(r["score_q"]),
            Fraction(int(r["theta_num"]), int(r["theta_den"])),
        )

    area = {r["cell_id"]: int(r["wilderness_area"]) for r in b["cells"]}

    def p_fold(cell, k, cl):
        s, theta = ev[(cell, k, cl)]
        scores = S.get(k, [])
        nk = len(scores)
        g = sum(1 for x in scores if x > s)
        e = sum(1 for x in scores if x == s)
        return (Fraction(g) + theta * (e + 1)) / (nk + 1)

    def combine(ps, rule):
        kk = len(ps)
        if rule == "arith2":
            return min(Fraction(1), 2 * sum(ps) / kk)
        if rule == "bonf":
            return min(Fraction(1), kk * min(ps))
        if rule == "median2":
            srt = sorted(ps)
            m = kk // 2
            med = srt[m] if kk % 2 == 1 else (srt[m - 1] + srt[m]) / 2
            return min(Fraction(1), 2 * med)
        raise ValueError(rule)

    pvalues = []  # (request_id, class_id, Fraction p, in_set)
    diag_acc = {}  # (area, alpha_num, alpha_den, rule) -> [set sizes]
    for r in b["grid"]:
        rid, cell = r["request_id"], r["cell_id"]
        alpha = Fraction(int(r["alpha_num"]), int(r["alpha_den"]))
        rule = r["combination_rule"]
        combined = {}
        for cl in classes:
            ps = [p_fold(cell, k, cl) for k in fold_universe]
            combined[cl] = combine(ps, rule)
        lset = {cl for cl in classes if combined[cl] > alpha}
        for cl in classes:
            pvalues.append((rid, cl, combined[cl], 1 if cl in lset else 0))
        key = (area[cell], r["alpha_num"], r["alpha_den"], rule)
        diag_acc.setdefault(key, []).append(len(lset))

    diagnostics = []
    for (a, an, ad, rule), sizes in diag_acc.items():
        mean = Fraction(sum(sizes), len(sizes))
        diagnostics.append((a, an, ad, rule, mean))
    diagnostics.sort(key=lambda t: (t[0], Fraction(int(t[1]), int(t[2])), t[3]))
    pvalues.sort(key=lambda t: (t[0], t[1]))
    return pvalues, diagnostics
