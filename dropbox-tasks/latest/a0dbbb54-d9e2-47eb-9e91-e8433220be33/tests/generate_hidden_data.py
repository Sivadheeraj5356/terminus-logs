"""Derive hidden bundles deterministically from the public fixtures.

Each hidden bundle is a schema-valid re-arrangement of the shipped real-data
tables: re-folded registries, coarsened scores, edge smoothing tapes, empty
folds, K=1 degeneracy, and decision grids carrying constructed boundary
alphas (achievable combined p-values computed via the oracle). No randomness;
every transformation is a pure function of the fixture bytes.

Env: PUB_DIR (public fixture bundle), HIDDEN_ROOT (output root).
"""

import csv
import os
import sys
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle_lib  # noqa: E402

PUB = os.environ["PUB_DIR"]
ROOT = os.environ["HIDDEN_ROOT"]

RULES = ["arith2", "bonf", "median2"]


def read(name):
    with open(os.path.join(PUB, name), newline="") as f:
        return list(csv.DictReader(f))


def write(bdir, name, header, rows):
    os.makedirs(bdir, exist_ok=True)
    with open(os.path.join(bdir, name), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def copy_table(bdir, name, rows, header):
    write(bdir, name, header, [[r[h] for h in header] for r in rows])


CELLS = read("terrain_cells.csv")
LABELS = read("cover_labels.csv")
REG = read("fold_registry.csv")
CAL = read("fold_scores_calibration.csv")
EV = read("fold_scores_evaluation.csv")
GRID = read("decision_grid.csv")

H_CELLS = ["cell_id", "wilderness_area"]
H_LABELS = ["cell_id", "cover_class"]
H_REG = ["cell_id", "fold"]
H_CAL = ["cell_id", "fold", "score_q"]
H_EV = ["cell_id", "fold", "class_id", "score_q", "theta_num", "theta_den"]
H_GRID = ["request_id", "cell_id", "alpha_num", "alpha_den", "combination_rule"]

LAB_ORDER = sorted({r["cell_id"] for r in REG})
EV_CELLS = sorted({r["cell_id"] for r in EV})


def base_grid_alphas(bdir):
    """After a bundle's tables exist, append a grid whose alphas include two
    generic levels plus one constructed achievable boundary value."""
    pv, _ = oracle_lib.compute(bdir)
    achievable = sorted({p for _, _, p, _ in pv if 0 < p < 1})
    boundary = achievable[len(achievable) // 3] if achievable else Fraction(1, 7)
    alphas = [Fraction(1, 10), Fraction(3, 40), boundary]
    rows, rid = [], 0
    for cell in EV_CELLS[:30]:
        for a in alphas:
            for rule in RULES:
                rows.append([f"H{rid:05d}", cell, a.numerator, a.denominator, rule])
                rid += 1
    write(bdir, "decision_grid.csv", H_GRID, rows)


def provisional_grid(bdir):
    rows, rid = [], 0
    for cell in EV_CELLS[:30]:
        for rule in RULES:
            rows.append([f"P{rid:05d}", cell, 1, 10, rule])
            rid += 1
    write(bdir, "decision_grid.csv", H_GRID, rows)


def finish(bdir):
    provisional_grid(bdir)
    base_grid_alphas(bdir)


def bundle_dir(name):
    return os.path.join(ROOT, name)


# h1: K=3 re-registry (fold contexts 0..2 only)
b = bundle_dir("h1_refold_k3")
copy_table(b, "terrain_cells.csv", CELLS, H_CELLS)
copy_table(b, "cover_labels.csv", LABELS, H_LABELS)
write(b, "fold_registry.csv", H_REG, [[cid, i % 3] for i, cid in enumerate(LAB_ORDER)])
write(
    b,
    "fold_scores_calibration.csv",
    H_CAL,
    [[r["cell_id"], r["fold"], r["score_q"]] for r in CAL if int(r["fold"]) < 3],
)
write(
    b,
    "fold_scores_evaluation.csv",
    H_EV,
    [[r[h] for h in H_EV] for r in EV if int(r["fold"]) < 3],
)
finish(b)

# h2: K=2 with coarsened scores (integer division by 100 -> tie storm)
b = bundle_dir("h2_coarse_k2")
copy_table(b, "terrain_cells.csv", CELLS, H_CELLS)
copy_table(b, "cover_labels.csv", LABELS, H_LABELS)
write(b, "fold_registry.csv", H_REG, [[cid, i % 2] for i, cid in enumerate(LAB_ORDER)])
write(
    b,
    "fold_scores_calibration.csv",
    H_CAL,
    [
        [r["cell_id"], r["fold"], int(r["score_q"]) // 100]
        for r in CAL
        if int(r["fold"]) < 2
    ],
)
write(
    b,
    "fold_scores_evaluation.csv",
    H_EV,
    [
        [
            r["cell_id"],
            r["fold"],
            r["class_id"],
            int(r["score_q"]) // 100,
            r["theta_num"],
            r["theta_den"],
        ]
        for r in EV
        if int(r["fold"]) < 2
    ],
)
finish(b)

# h3: empty fold — registry drops fold 4's members; evaluation keeps fold 4
b = bundle_dir("h3_empty_fold")
copy_table(b, "terrain_cells.csv", CELLS, H_CELLS)
copy_table(b, "cover_labels.csv", LABELS, H_LABELS)
write(
    b,
    "fold_registry.csv",
    H_REG,
    [[r["cell_id"], r["fold"]] for r in REG if int(r["fold"]) != 4],
)
copy_table(b, "fold_scores_calibration.csv", CAL, H_CAL)
copy_table(b, "fold_scores_evaluation.csv", EV, H_EV)
finish(b)

# h4: K=1 degeneracy — single fold context 0
b = bundle_dir("h4_k1_degenerate")
copy_table(b, "terrain_cells.csv", CELLS, H_CELLS)
copy_table(b, "cover_labels.csv", LABELS, H_LABELS)
write(b, "fold_registry.csv", H_REG, [[cid, 0] for cid in LAB_ORDER])
write(
    b,
    "fold_scores_calibration.csv",
    H_CAL,
    [[r["cell_id"], r["fold"], r["score_q"]] for r in CAL if r["fold"] == "0"],
)
write(
    b,
    "fold_scores_evaluation.csv",
    H_EV,
    [[r[h] for h in H_EV] for r in EV if r["fold"] == "0"],
)
finish(b)

# h5: theta edge tapes — deterministic 0/1 alternation
b = bundle_dir("h5_theta_edges")
copy_table(b, "terrain_cells.csv", CELLS, H_CELLS)
copy_table(b, "cover_labels.csv", LABELS, H_LABELS)
copy_table(b, "fold_registry.csv", REG, H_REG)
copy_table(b, "fold_scores_calibration.csv", CAL, H_CAL)
rows = []
for i, r in enumerate(EV):
    edge = (int(r["fold"]) + int(r["class_id"]) + i) % 2
    rows.append([r["cell_id"], r["fold"], r["class_id"], r["score_q"], edge, 1])
write(b, "fold_scores_evaluation.csv", H_EV, rows)
finish(b)

# h6: row-order rotation of h1 (order independence of every table)
src = bundle_dir("h1_refold_k3")
b = bundle_dir("h6_roworder")
for name in [
    "terrain_cells.csv",
    "cover_labels.csv",
    "fold_registry.csv",
    "fold_scores_calibration.csv",
    "fold_scores_evaluation.csv",
    "decision_grid.csv",
]:
    with open(os.path.join(src, name), newline="") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    cut = len(body) // 3
    write(b, name, header, body[cut:] + body[:cut])

print("hidden bundles written under", ROOT)
