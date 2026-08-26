#!/usr/bin/env python3
"""Offline training batch evaluation on point-in-time feature ledgers.

Consumes a materialized training fold report, builds a tiny linear model on a
temporal train split, scores holdout accuracy, and records a leakage score for
rows whose chosen feature revision should not have been available at asof.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _row_vector(row: dict) -> list[float]:
    values = row.get("values") or {}
    keys = sorted(values.keys())
    if not keys:
        return [0.0, 0.0, 0.0]
    vec = [float(values[k]) for k in keys]
    while len(vec) < 3:
        vec.append(0.0)
    return vec[:3]


def _label(vec: list[float]) -> int:
    score = 0.7 * vec[0] - 0.4 * vec[1] + 0.2 * vec[2]
    return 1 if score >= 0.0 else 0


def _fit(xs: list[list[float]], ys: list[int]) -> list[float]:
    # Closed-form ridge on bias + three feature dims (deterministic, no sklearn).
    dim = 4
    ata = [[0.0] * dim for _ in range(dim)]
    atb = [0.0] * dim
    for x, y in zip(xs, ys, strict=True):
        z = [1.0, *x]
        for i in range(dim):
            atb[i] += z[i] * float(y)
            for j in range(dim):
                ata[i][j] += z[i] * z[j]
        for i in range(dim):
            ata[i][i] += 1e-3
    # Gauss-Jordan solve
    m = [ata[i][:] + [atb[i]] for i in range(dim)]
    for col in range(dim):
        pivot = max(range(col, dim), key=lambda r: abs(m[r][col]))
        m[col], m[pivot] = m[pivot], m[col]
        div = m[col][col] if abs(m[col][col]) > 1e-12 else 1e-12
        m[col] = [v / div for v in m[col]]
        for row in range(dim):
            if row == col:
                continue
            factor = m[row][col]
            m[row] = [a - factor * b for a, b in zip(m[row], m[col], strict=True)]
    return [m[i][-1] for i in range(dim)]


def _predict(w: list[float], x: list[float]) -> int:
    z = w[0] + sum(w[i + 1] * x[i] for i in range(3))
    return 1 if z >= 0.5 else 0


def _leakage_hits(report: dict) -> int:
    hits = 0
    rows = report.get("rows") or []
    auds = report.get("audit_trace") or []
    for row, aud in zip(rows, auds, strict=True):
        chosen = row.get("feat_rev") or ""
        cands = set((aud or {}).get("candidate_revs") or [])
        if chosen and chosen not in cands:
            hits += 1
        if (aud or {}).get("policy") == "asof_wm" and not chosen:
            hits += 1
    return hits


def evaluate(report: dict) -> dict:
    rows = sorted(report.get("rows") or [], key=lambda r: (r.get("asof_ms", 0), r.get("event_id", "")))
    xs = [_row_vector(r) for r in rows]
    ys = [_label(x) for x in xs]
    if len(rows) < 2:
        split = max(1, len(rows))
    else:
        split = max(1, len(rows) // 2)
    train_x, train_y = xs[:split], ys[:split]
    test_x, test_y = xs[split:] or xs[:1], ys[split:] or ys[:1]
    weights = _fit(train_x, train_y)
    preds = [_predict(weights, x) for x in test_x]
    correct = sum(int(p == y) for p, y in zip(preds, test_y, strict=True))
    acc = correct / max(1, len(test_y))
    leak = _leakage_hits(report)
    return {
        "fold_id": report.get("fold_id"),
        "train_rows": len(train_x),
        "holdout_rows": len(test_x),
        "holdout_accuracy": round(acc, 6),
        "leakage_hits": leak,
        "model": "ridge_linear_v1",
        "training_ok": leak == 0 and not math.isnan(acc),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Train/eval a tiny model on a PIT training ledger")
    ap.add_argument("--report", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    metrics = evaluate(report)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics))
    return 0 if metrics.get("training_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
