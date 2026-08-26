"""Verifier-side generator and hidden ground truth for the sequence-labeling induction task. A
hidden stateful rule (fixed structure, per-instance parameters) labels each event from one of its
integer features and a self-resetting accumulator built from an earlier feature, read at a delay.
The candidate must infer the rule from a labeled training split and predict a held-out split. The
rule is never disclosed to the candidate."""

import csv
import os
import random

D = 4
FMAX = 10


def rand_params(seed):
    """Draw the hidden per-instance parameters deterministically from the seed."""
    r = random.Random(seed * 2654435761 & 0xFFFFFFFF)
    j = r.randint(0, D - 1)
    t = r.randint(0, D - 1)
    while t == j:
        t = r.randint(0, D - 1)
    cap = r.randint(8, 14)
    delay = r.randint(1, 3)
    return (j, t, cap, delay)


def gen_features(seed, n):
    """Generate n rows of D small integer features deterministically from the seed."""
    r = random.Random(seed * 7 + 1)
    return [[r.randrange(FMAX) for _ in range(D)] for _ in range(n)]


def label(params, xs):
    """Label each row: 1 if feature j exceeds a delayed, self-resetting accumulator of feature t."""
    j, t, cap, delay = params
    snap = []
    acc = 0
    for x in xs:
        snap.append(acc)
        acc += x[t]
        if acc >= cap:
            acc = 0
    out = []
    for i in range(len(xs)):
        bar = snap[i - delay] if i - delay >= 0 else 0
        out.append(1 if xs[i][j] > bar else 0)
    return out


def write_instance(dirpath, seed, n_train, n_test, with_test_labels=False):
    """Materialize one instance: train.csv (features+label), test.csv (features). Returns test
    labels. When with_test_labels is set (the shipped public instance), also write
    test_labels.csv so a candidate can score a recovered rule locally end to end."""
    os.makedirs(dirpath, exist_ok=True)
    params = rand_params(seed)
    trx = gen_features(seed, n_train)
    trY = label(params, trx)
    tex = gen_features(1000 + seed, n_test)
    teY = label(params, tex)
    with open(os.path.join(dirpath, "train.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["event_id"] + [f"f{j}" for j in range(D)] + ["label"])
        for i, (x, y) in enumerate(zip(trx, trY)):
            w.writerow([i] + x + [y])
    with open(os.path.join(dirpath, "test.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["event_id"] + [f"f{j}" for j in range(D)])
        for i, x in enumerate(tex):
            w.writerow([i] + x)
    if with_test_labels:
        with open(os.path.join(dirpath, "test_labels.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["event_id", "label"])
            for i, y in enumerate(teY):
                w.writerow([i, y])
    return teY
