"""Behavioral verification for one bundle: exact comparison of the candidate's
pvalues.csv and diagnostics.csv against an independent Fraction oracle.

Env: BUNDLE_DIR (inputs), OUT_DIR (candidate outputs).
Every (request, class) combined p-value, every membership bit, and every
diagnostic row is a distinct semantic case derived from the published
contract; internal-consistency cases check in_set against the recomputed
p-value/level comparison.
"""

import csv
import os
from fractions import Fraction
from math import gcd

import pytest

import oracle_lib

BUNDLE = os.environ["BUNDLE_DIR"]
OUT = os.environ["OUT_DIR"]

ORACLE_PV, ORACLE_DIAG = oracle_lib.compute(BUNDLE)


def _read_out(name, ncols):
    path = os.path.join(OUT, name)
    assert os.path.exists(path), f"missing output {name}"
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    assert rows, f"empty output {name}"
    assert len(rows[0]) == ncols, f"bad header in {name}"
    return rows[0], rows[1:]


def test_pvalues_header_and_shape():
    header, body = _read_out("pvalues.csv", 5)
    assert header == ["request_id", "class_id", "p_num", "p_den", "in_set"]
    assert len(body) == len(ORACLE_PV), (
        f"expected {len(ORACLE_PV)} rows, got {len(body)}"
    )


def test_pvalues_row_order():
    _, body = _read_out("pvalues.csv", 5)
    keys = [(r[0], int(r[1])) for r in body]
    assert keys == [(rid, cl) for rid, cl, _, _ in ORACLE_PV], (
        "rows must be ordered by request_id then class_id"
    )


@pytest.mark.parametrize("chunk", range(20))
def test_pvalues_exact(chunk):
    _, body = _read_out("pvalues.csv", 5)
    n = len(ORACLE_PV)
    lo = chunk * n // 20
    hi = (chunk + 1) * n // 20
    by_key = {(r[0], int(r[1])): r for r in body}
    for rid, cl, p, inset in ORACLE_PV[lo:hi]:
        row = by_key.get((rid, cl))
        assert row is not None, f"missing row for {rid} class {cl}"
        num, den = int(row[2]), int(row[3])
        assert den > 0, f"{rid}/{cl}: denominator must be positive"
        assert gcd(abs(num), den) == 1, f"{rid}/{cl}: fraction not reduced"
        assert Fraction(num, den) == p, (
            f"{rid}/{cl}: expected {p.numerator}/{p.denominator}, got {num}/{den}"
        )
        assert int(row[4]) == inset, f"{rid}/{cl}: wrong in_set"


def test_membership_internal_consistency():
    # in_set must equal the strict comparison of the reported fraction itself
    _, body = _read_out("pvalues.csv", 5)
    grid = {
        r["request_id"]: Fraction(int(r["alpha_num"]), int(r["alpha_den"]))
        for r in oracle_lib.load_bundle(BUNDLE)["grid"]
    }
    for r in body:
        alpha = grid[r[0]]
        claimed = Fraction(int(r[2]), int(r[3]))
        assert (1 if claimed > alpha else 0) == int(r[4]), (
            f"{r[0]}/{r[1]}: in_set inconsistent with reported p and alpha"
        )


def test_diagnostics_exact():
    header, body = _read_out("diagnostics.csv", 6)
    assert header == [
        "wilderness_area",
        "alpha_num",
        "alpha_den",
        "combination_rule",
        "mean_setsize_num",
        "mean_setsize_den",
    ]
    assert len(body) == len(ORACLE_DIAG), (
        f"expected {len(ORACLE_DIAG)} diagnostic rows, got {len(body)}"
    )
    for row, (a, an, ad, rule, mean) in zip(body, ORACLE_DIAG):
        assert (int(row[0]), row[1], row[2], row[3]) == (a, str(an), str(ad), rule), (
            f"diagnostic row mismatch/order: {row} vs {(a, an, ad, rule)}"
        )
        num, den = int(row[4]), int(row[5])
        assert den > 0 and gcd(abs(num), den) == 1, "mean not a reduced fraction"
        assert Fraction(num, den) == mean, (
            f"area {a} {an}/{ad} {rule}: expected "
            f"{mean.numerator}/{mean.denominator}, got {num}/{den}"
        )
