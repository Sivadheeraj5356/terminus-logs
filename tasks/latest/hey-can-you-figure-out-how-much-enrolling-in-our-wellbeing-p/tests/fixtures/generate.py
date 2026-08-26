import csv
import os

import numpy as np

BASE = [
    "age_index",
    "bmi_index",
    "activity_index",
    "chronic_index",
    "diet_index",
    "sleep_index",
    "stress_index",
    "income_index",
]
TRIPLE_A = ("diet_index", "sleep_index", "stress_index")
TRIPLE_B = ("activity_index", "chronic_index", "income_index")
CG_YA = 3.2
CG_YB = 3.2
CG_AA = 3.4
CG_AB = 3.4
COUT = 1.6
CTEN = 1.0


def _prod(x, tri, w):
    return np.sin(w * x[tri[0]]) * np.sin(w * x[tri[1]]) * np.sin(w * x[tri[2]])


def draw(seed, n, tau, tau_het, w_a, w_b):
    rng = np.random.default_rng(seed)
    x = {k: rng.standard_normal(n) for k in BASE}
    tenure = rng.uniform(1.0, 7.0, n)
    ga = _prod(x, TRIPLE_A, w_a)
    gb = _prod(x, TRIPLE_B, w_b)
    outreach = 0.5 * x["income_index"] + rng.normal(0, 1, n) * 1.3
    a_lin = (
        0.3
        + COUT * outreach
        + 0.5 * x["activity_index"]
        - 0.4 * x["chronic_index"]
        + 0.4 * x["age_index"]
        + CTEN * (tenure - 4.0)
        + CG_AA * ga
        + CG_AB * gb
    )
    enrolled = ((a_lin + rng.logistic(0, 1, n)) > 0).astype(int)
    wellbeing = (
        2.0
        + tau * enrolled
        + tau_het * enrolled * tenure
        + 0.5 * tenure
        + 0.8 * x["age_index"]
        + 0.6 * x["bmi_index"]
        - 0.5 * x["chronic_index"]
        + 0.7 * x["activity_index"]
        + 0.4 * x["income_index"]
        + CG_YA * ga
        + CG_YB * gb
        + rng.normal(0, 1.0, n)
    )
    return {
        "x": x,
        "tenure": tenure,
        "outreach": outreach,
        "enrolled": enrolled,
        "wellbeing": wellbeing,
    }


def write_dataset(target_dir, sample):
    os.makedirs(target_dir, exist_ok=True)
    n = len(sample["enrolled"])
    ids = ["E%06d" % (100000 + i) for i in range(n)]

    def emit(name, header, rows):
        with open(os.path.join(target_dir, name), "w", newline="") as fh:
            wtr = csv.writer(fh)
            wtr.writerow(header)
            wtr.writerows(rows)

    emit(
        "baseline_covariates.csv",
        ["employee_id"] + BASE,
        [
            [ids[i]] + [round(float(sample["x"][k][i]), 5) for k in BASE]
            for i in range(n)
        ],
    )
    emit(
        "tenure.csv",
        ["employee_id", "tenure_years"],
        [[ids[i], round(float(sample["tenure"][i]), 4)] for i in range(n)],
    )
    emit(
        "outreach.csv",
        ["employee_id", "outreach_contacts"],
        [[ids[i], round(float(sample["outreach"][i]), 5)] for i in range(n)],
    )
    emit(
        "enrollment.csv",
        ["employee_id", "enrolled"],
        [[ids[i], int(sample["enrolled"][i])] for i in range(n)],
    )
    emit(
        "outcome.csv",
        ["employee_id", "wellbeing_index"],
        [[ids[i], round(float(sample["wellbeing"][i]), 5)] for i in range(n)],
    )
