import random
import subprocess
from fractions import Fraction
from pathlib import Path
import pytest

BIN = Path("/tmp/polygon_fold_solver")


def frac_text(x):
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def run_program(data):
    completed = subprocess.run([str(BIN)], input=data, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
    assert completed.returncode == 0, completed.stderr
    return " ".join(completed.stdout.split())


def build_candidate():
    completed = subprocess.run(["g++", "-std=c++17", "-O2", "-pipe", "/app/src/main.cpp", "-o", str(BIN)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    assert completed.returncode == 0, completed.stderr


def clean(poly):
    out = []
    for p in poly:
        if not out or out[-1] != p:
            out.append(p)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def clip(poly, a, b, c):
    poly = clean(poly)
    out = []
    if not poly:
        return out
    def val(p):
        return a * p[0] + b * p[1] - c
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        vp = val(p)
        vq = val(q)
        ip = vp <= 0
        iq = vq <= 0
        if ip and iq:
            out.append(q)
        elif ip and not iq:
            t = vp / (vp - vq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
        elif not ip and iq:
            t = vp / (vp - vq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
            out.append(q)
    return clean(out)


def signed_area2(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[i][1] * poly[(i + 1) % len(poly)][0] for i in range(len(poly))) if len(poly) >= 3 else Fraction(0)


def ccw(poly):
    poly = clean(poly)
    return list(reversed(poly)) if signed_area2(poly) < 0 else poly


def moments(poly):
    poly = clean(poly)
    if len(poly) < 3:
        return Fraction(0), Fraction(0), Fraction(0)
    if signed_area2(poly) < 0:
        poly = list(reversed(poly))
    a2 = signed_area2(poly)
    sx = Fraction(0)
    sy = Fraction(0)
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        cr = p[0] * q[1] - p[1] * q[0]
        sx += (p[0] + q[0]) * cr
        sy += (p[1] + q[1]) * cr
    return a2 / 2, sx / 6, sy / 6


def all_moments(poly):
    poly = clean(poly)
    if len(poly) < 3:
        return (Fraction(0),) * 6
    if signed_area2(poly) < 0:
        poly = list(reversed(poly))
    a2 = signed_area2(poly)
    sx = Fraction(0)
    sy = Fraction(0)
    sx2 = Fraction(0)
    sxy = Fraction(0)
    sy2 = Fraction(0)
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        cr = p[0] * q[1] - p[1] * q[0]
        sx += (p[0] + q[0]) * cr
        sy += (p[1] + q[1]) * cr
        sx2 += (p[0] * p[0] + p[0] * q[0] + q[0] * q[0]) * cr
        sxy += (2 * p[0] * p[1] + p[0] * q[1] + q[0] * p[1] + 2 * q[0] * q[1]) * cr
        sy2 += (p[1] * p[1] + p[1] * q[1] + q[1] * q[1]) * cr
    return a2 / 2, sx / 6, sy / 6, sx2 / 12, sxy / 24, sy2 / 12


def intersect_convex(subject, cutter):
    cur = clean(subject)
    cutter = ccw(cutter)
    for i, a in enumerate(cutter):
        b = cutter[(i + 1) % len(cutter)]
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        cur = clip(cur, dy, -dx, dy * a[0] - dx * a[1])
    return clean(cur)


def reflect(p, a, b, c):
    s = a * p[0] + b * p[1] - c
    den = a * a + b * b
    return (p[0] - 2 * a * s / den, p[1] - 2 * b * s / den)


def expected(case):
    poly, line = case
    poly = [(Fraction(x), Fraction(y)) for x, y in poly]
    a, b, c = map(Fraction, line)
    stay = clip(poly, a, b, c)
    fold = [reflect(p, a, b, c) for p in clip(poly, -a, -b, -c)]
    stay = ccw(stay)
    fold = ccw(fold)
    both = intersect_convex(stay, fold) if stay and fold else []
    ms = moments(stay)
    mf = moments(fold)
    mb = moments(both)
    visible = ms[0] + mf[0] - mb[0]
    visible_x = ms[1] + mf[1] - mb[1]
    visible_y = ms[2] + mf[2] - mb[2]
    return " ".join(frac_text(v) for v in (visible, mb[0], visible_x, visible_y, mb[1], mb[2]))


def expected_second(case):
    poly, line = case
    poly = [(Fraction(x), Fraction(y)) for x, y in poly]
    a, b, c = map(Fraction, line)
    stay = clip(poly, a, b, c)
    fold = [reflect(p, a, b, c) for p in clip(poly, -a, -b, -c)]
    stay = ccw(stay)
    fold = ccw(fold)
    both = intersect_convex(stay, fold) if stay and fold else []
    ms = all_moments(stay)
    mf = all_moments(fold)
    mb = all_moments(both)
    visible = [ms[i] + mf[i] - mb[i] for i in range(6)]
    values = [visible[0], mb[0], visible[1], visible[2], mb[1], mb[2], visible[3], visible[4], visible[5], mb[3], mb[4], mb[5]]
    return " ".join(frac_text(v) for v in values)


def folded_components(case):
    poly, line = case
    poly = [(Fraction(x), Fraction(y)) for x, y in poly]
    a, b, c = map(Fraction, line)
    stay = ccw(clip(poly, a, b, c))
    fold = ccw([reflect(p, a, b, c) for p in clip(poly, -a, -b, -c)])
    both = intersect_convex(stay, fold) if stay and fold else []
    return stay, fold, both


def _poly_audit_digest(lines):
    value = 13679457532755275413
    for line in lines:
        for byte in (line + "\n").encode("ascii"):
            value ^= byte
            value = (value * 1099511628211) & ((1 << 64) - 1)
    return value


def expected_poly_trace(case):
    lines = [expected_second(case)]
    for label, poly in zip(["STAY", "FOLD", "DOUBLE"], folded_components(case)):
        for idx, point in enumerate(poly):
            nxt = poly[(idx + 1) % len(poly)]
            lines.append(
                f"{label} {idx} {frac_text(point[0])} {frac_text(point[1])} {frac_text(point[0] * nxt[1] - point[1] * nxt[0])}"
            )
    lines.append(f"POLY_AUDIT_178A9137 {_poly_audit_digest(lines)}")
    return lines


def convex_polygon(rng, n):
    pts = []
    for i in range(n):
        pts.append((rng.randint(-20, 20), rng.randint(-20, 20)))
    pts = sorted(set(pts))
    def hull(points):
        def cr(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
        lower = []
        for p in points:
            while len(lower) >= 2 and cr(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)
        upper = []
        for p in reversed(points):
            while len(upper) >= 2 and cr(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)
        return lower[:-1] + upper[:-1]
    h = hull(pts)
    return h if len(h) >= 3 else [(-5, -4), (6, -3), (5, 5), (-4, 6)]


def cases():
    rng = random.Random(81119)
    out = [
        ([(-6, -4), (7, -4), (8, 3), (1, 8), (-5, 6)], (1, -1, 0)),
        ([(-8, -2), (-2, -7), (5, -5), (9, 2), (2, 9), (-7, 6)], (2, 1, 3)),
        ([(-4, -5), (6, -5), (8, 4), (0, 9), (-7, 2)], (-3, 2, -1)),
        ([(-5, -4), (6, -4), (8, 3), (0, 8), (-7, 3)], (1, 0, 0)),
        ([(-9, -5), (4, -8), (10, 1), (2, 10), (-8, 6)], (3, -2, 4)),
        ([(-16, -9), (12, -13), (21, 2), (8, 19), (-11, 15), (-22, 1)], (5, -3, 17)),
        ([(-20, -8), (-6, -18), (13, -12), (24, 4), (6, 22), (-17, 12)], (-4, 7, -9)),
    ]
    for _ in range(91):
        poly = convex_polygon(rng, rng.randint(8, 16))
        a = rng.choice([-8, -7, -5, -4, -3, -2, -1, 1, 2, 3, 4, 5, 7, 8])
        b = rng.choice([-8, -7, -5, -4, -3, -2, -1, 1, 2, 3, 4, 5, 7, 8])
        vals = [a * x + b * y for x, y in poly]
        c = rng.randint(min(vals) + 1, max(vals) - 1) if max(vals) - min(vals) > 2 else (min(vals) + max(vals)) // 2
        out.append((poly, (a, b, c)))
    return out


def encode(case):
    poly, line = case
    lines = [str(len(poly))]
    lines.extend(f"{x} {y}" for x, y in poly)
    lines.append(" ".join(map(str, line)))
    return "\n".join(lines) + "\n"


def encode_second(case):
    return "SECOND_178A9137\n" + encode(case)


def encode_poly_trace(case):
    return "POLY_TRACE_178A9137\n" + encode(case)


ALL_CASES = cases()
HAND_CASES = ALL_CASES[:5]
RANDOM_CASES = ALL_CASES[5:]


@pytest.fixture(scope="module", autouse=True)
def binary():
    build_candidate()


@pytest.mark.parametrize("idx, case", list(enumerate(HAND_CASES)), ids=[f"hand_case_{i}" for i in range(len(HAND_CASES))])
def test_handcrafted_folded_silhouette_is_exact(idx, case):
    """Checks folded visible and double-covered areas on hand-crafted cases."""
    assert run_program(encode(case)) == expected(case), f"hand case {idx}"


@pytest.mark.parametrize("idx, case", list(enumerate(RANDOM_CASES)), ids=[f"random_case_{i}" for i in range(len(RANDOM_CASES))])
def test_random_folded_silhouette_is_exact(idx, case):
    """Checks folded visible and double-covered areas on randomized cases."""
    assert run_program(encode(case)) == expected(case), f"case {idx}"

def _batch_audit_digest(lines):
    value = 15886462886245262841
    for line in lines:
        for byte in (line + "\n").encode("ascii"):
            value ^= byte
            value = (value * 1099511628211) & ((1 << 64) - 1)
    return value


def _second_batch_audit_digest(lines):
    value = 7809847782465536327
    for line in lines:
        for byte in (line + "\n").encode("ascii"):
            value ^= byte
            value = (value * 1099511628211) & ((1 << 64) - 1)
    return value


def test_stateful_batch_protocol_and_audit_cascade():
    # Couples seven independently-derived answers through one continuous digest.
    selected = cases()[:7]
    assert len(selected) == 7
    payload = "BATCH_178A9137 7\n" + "".join(encode(case) for case in selected)
    completed = subprocess.run(
        [str(BIN)],
        input=payload,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    actual_lines = [" ".join(line.split()) for line in completed.stdout.splitlines() if line.strip()]
    answer_lines = [" ".join(str(expected(case)).split()) for case in selected]
    expected_lines = answer_lines + [f"AUDIT_178A9137 {_batch_audit_digest(answer_lines)}"]
    assert actual_lines == expected_lines


def test_second_moment_mode_reports_folded_union_and_overlap_quadratics():
    for idx, case in enumerate(cases()[4:13]):
        assert run_program(encode_second(case)) == expected_second(case), f"second case {idx}"


def test_batch_second_moment_mode_hashes_quadratics_continuously():
    selected = ALL_CASES[2:8]
    payload = "BATCH_SECOND_178A9137 6\n" + "".join(encode(case) for case in selected)
    completed = subprocess.run(
        [str(BIN)],
        input=payload,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    answer_lines = [" ".join(expected_second(case).split()) for case in selected]
    expected_lines = answer_lines + [f"SECOND_AUDIT_178A9137 {_second_batch_audit_digest(answer_lines)}"]
    assert [" ".join(line.split()) for line in completed.stdout.splitlines() if line.strip()] == expected_lines


def test_polygon_trace_lists_stay_fold_and_double_vertices_exactly():
    for idx, case in enumerate([ALL_CASES[0], ALL_CASES[3], ALL_CASES[6], ALL_CASES[10]]):
        completed = subprocess.run(
            [str(BIN)],
            input=encode_poly_trace(case),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr
        actual_lines = [" ".join(line.split()) for line in completed.stdout.splitlines() if line.strip()]
        assert actual_lines == expected_poly_trace(case), f"polygon trace case {idx}"

