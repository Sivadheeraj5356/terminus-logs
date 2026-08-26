"""Independent checker for the plangen calibration ladder.

Everything here is recomputed from the bundle with exact integer arithmetic,
following /app/environment/docs/contract.rst. Nothing is read back from a file
the agent can rewrite: the binary is rebuilt from source, held-out ladders are
generated here, and every emitted number is recomputed from the fit fold and
rim. Durable fit-store and journal rules follow protocol.rst.
"""

import json
import subprocess
from pathlib import Path

import pytest

BIN = Path("/app/bin/plangen")
FAMILY_NAMES = ["hist", "iso", "giso"]
MASK = (1 << 64) - 1
FITSTORE = Path("/app/environment/var/fitstore")
RUNROOT = Path("/app/environment/var/run")
STEEP = Path("/app/environment/data/bundles/steep.json")
STEEP_OUT = Path("/app/out/plan.json")

FNV_OFFSET = 14695981039346656037
FNV_PRIME = 1099511628211

HELD_OUT_SEEDS = [20260716, 5150, 987211]


def fold_digest(bundle):
    """Sixteen-hex fold digest, protocol.rst."""
    h = FNV_OFFSET

    def feed(line):
        nonlocal h
        for b in (line + "\n").encode("ascii"):
            h ^= b
            h = (h * FNV_PRIME) & MASK

    feed(str(bundle["unit"]))
    feed(str(bundle["cells"]))
    feed(str(bundle["lanes"]))
    feed(str(bundle["bins"]))
    for r in bundle["fit"]:
        feed(f'{r["raw"]},{r["hit"]},{r["lane"]}')
    feed("---")
    for r in bundle.get("rim") or []:
        feed(f'{r["raw"]},{r["hit"]},{r["lane"]}')
    return f"{h:016x}"


# --------------------------------------------------------------------------
# Reference arithmetic (contract.rst sections 1-6)
# --------------------------------------------------------------------------

def round_div(num, den):
    """Round-half-up of num/den for den > 0, contract.rst section 1."""
    if den <= 0:
        return 0
    return (2 * num + den) // (2 * den)


def cell_of(raw, unit, cells):
    """Equal-width cell of a raw score, contract.rst section 2.1."""
    k = raw * cells // (unit + 1)
    if k >= cells:
        k = cells - 1
    if k < 0:
        k = 0
    return k


def build_hist(rows, unit, cells):
    """Uniform-width histogram fit, contract.rst section 2.1."""
    h = [0] * cells
    t = [0] * cells
    for r in rows:
        k = cell_of(r["raw"], unit, cells)
        t[k] += 1
        h[k] += r["hit"]
    out = []
    for k in range(cells):
        if t[k] > 0:
            out.append(round_div(unit * h[k], t[k]))
        else:
            out.append(round_div(unit * (2 * k + 1), 2 * cells))
    return out


def pool(rows):
    """Pool-adjacent-violators over distinct raw values, contract.rst section 2.2."""
    agg = {}
    for r in rows:
        h, t = agg.get(r["raw"], (0, 0))
        agg[r["raw"]] = (h + r["hit"], t + 1)
    stack = []
    for v in sorted(agg):
        h, t = agg[v]
        lo = v
        while stack:
            top_lo, top_h, top_t = stack[-1]
            if h * top_t < top_h * t:
                lo = top_lo
                h += top_h
                t += top_t
                stack.pop()
            else:
                break
        stack.append((lo, h, t))
    return stack


def eval_blocks(blocks, raw, unit):
    """Select the last block at or below raw and map it, contract.rst section 2.2."""
    if not blocks:
        return 0
    idx = 0
    for i, (lo, _h, _t) in enumerate(blocks):
        if lo <= raw:
            idx = i
        else:
            break
    _lo, h, t = blocks[idx]
    return round_div(unit * h, t)


class Book:
    """The three fit-fold maps, contract.rst section 2."""

    def __init__(self, fit, unit, cells, lanes):
        self.unit = unit
        self.cells = cells
        self.lanes = lanes
        self.fit = fit
        self.hist = build_hist(fit, unit, cells)
        self.iso = pool(fit)
        self.giso = []
        for g in range(lanes):
            lane = [r for r in fit if r["lane"] == g]
            self.giso.append(pool(lane) if lane else None)

    def eval(self, pick, raw, lane):
        if pick == 0:
            return self.hist[cell_of(raw, self.unit, self.cells)]
        if pick == 1:
            return eval_blocks(self.iso, raw, self.unit)
        if 0 <= lane < len(self.giso) and self.giso[lane]:
            return eval_blocks(self.giso[lane], raw, self.unit)
        return eval_blocks(self.iso, raw, self.unit)


def edge_rows(bundle):
    """Fit fold concatenated with rim, contract.rst section 3."""
    return list(bundle["fit"]) + list(bundle.get("rim") or [])


def edges_of(book, pick, rows, m):
    """Equal-mass edges drawn from fit+rim mapped values, contract.rst section 3."""
    vals = sorted(book.eval(pick, r["raw"], r["lane"]) for r in rows)
    n = len(vals)
    out = []
    for j in range(1, m):
        idx = j * n // m
        if idx >= n:
            idx = n - 1
        if idx < 0:
            idx = 0
        out.append(vals[idx])
    return out


def tally(book, pick, rows, edges, unit):
    """Exact integer deviation over sealed fit+rim edges, contract.rst section 5."""
    m = len(edges) + 1
    nb = [0] * m
    hb = [0] * m
    sc = [0] * m
    for r in rows:
        c = book.eval(pick, r["raw"], r["lane"])
        b = sum(1 for e in edges if e <= c)  # contract.rst section 4
        nb[b] += 1
        hb[b] += r["hit"]
        sc[b] += c
    return sum(abs(unit * hb[b] - sc[b]) for b in range(m) if nb[b] > 0)


def analyze(bundle):
    """Returns (book, dev[rung][family]) for a bundle."""
    book = Book(bundle["fit"], bundle["unit"], bundle["cells"], bundle["lanes"])
    rows = edge_rows(bundle)
    ed = [edges_of(book, f, rows, bundle["bins"]) for f in range(3)]
    dev = [[tally(book, f, rung["rows"], ed[f], bundle["unit"]) for f in range(3)]
           for rung in bundle["rungs"]]
    return book, dev


def any_ordered_assignment(bundle):
    """Any assignment meeting contract.rst section 7, or None."""
    _book, dev = analyze(bundle)
    r = len(bundle["rungs"])
    allow = [rg["budget"] * len(rg["rows"]) for rg in bundle["rungs"]]
    feasible = [[dev[i][f] <= allow[i] for f in range(3)] for i in range(r)]
    best = [[None] * 3 for _ in range(r)]
    for s in range(3):
        if feasible[0][s]:
            best[0][s] = [s]
    for i in range(1, r):
        span = bundle["rungs"][i].get("span", 2)
        for s in range(3):
            if not feasible[i][s]:
                continue
            for p in range(s + 1):
                if best[i - 1][p] is not None and s - p <= span:
                    best[i][s] = best[i - 1][p] + [s]
                    break
    for s in range(3):
        if best[r - 1][s] is not None:
            return best[r - 1][s]
    return None


# --------------------------------------------------------------------------
# Held-out ladder generation (meets the documented floors)
# --------------------------------------------------------------------------

class Rng:
    """Explicit LCG so generated ladders never depend on library internals."""

    def __init__(self, seed):
        self.x = (seed * 2862933555777941757 + 3037000493) & MASK

    def next(self):
        self.x = (self.x * 6364136223846793005 + 1442695040888963407) & MASK
        return (self.x >> 33) & 0x7FFFFFFF

    def below(self, n):
        return self.next() % n


def hit_prob(raw, lane, unit):
    p = raw / unit
    if lane == 1:
        p = p * p
    elif lane >= 2:
        p = min(1.0, p * 1.6)
    return min(max(p, 0.0), 1.0)


def make_rows(rng, n, unit, levels, lane_w):
    total = sum(lane_w)
    rows = []
    for _ in range(n):
        pick = rng.below(total)
        lane = 0
        acc = 0
        for g, w in enumerate(lane_w):
            acc += w
            if pick < acc:
                lane = g
                break
        raw = levels[rng.below(len(levels))]
        p = hit_prob(raw, lane, unit)
        rows.append({"raw": raw, "hit": 1 if rng.below(10_000) < int(p * 10_000) else 0,
                     "lane": lane})
    return rows


def make_rim(rng, unit, levels, lanes, n=120):
    """Edge-placement rows biased toward score extremes so fit-only edges fail."""
    lows = [{"raw": levels[0], "hit": 0, "lane": rng.below(lanes)}
            for _ in range(n // 2)]
    highs = [{"raw": levels[-1], "hit": 1, "lane": rng.below(lanes)}
             for _ in range(n - len(lows))]
    return lows + highs


def draft(seed, unit=1000, bins=10, cells=8, lanes=2, n_levels=16,
          fit_n=400, rung_n=96, n_rungs=5):
    """A ladder meeting the documented size floors, with budgets left unset."""
    rng = Rng(seed)
    step = unit // (n_levels + 1)
    levels = [step * (i + 1) for i in range(n_levels)]
    fit = make_rows(rng, fit_n, unit, levels, [1] * lanes)
    rim = make_rim(rng, unit, levels, lanes)
    hold = make_rows(rng, max(64, rung_n // 2), unit, levels, [1] * lanes)
    rungs = []
    for i in range(n_rungs):
        # Severity tilts the lane mix away from the fit fold's balance.
        lane_w = [1] * lanes
        lane_w[-1] = 1 + 3 * i
        # Later rungs cap strength promotion so staged climbs are required.
        span = 2 if i == 0 else 1
        rungs.append({"severity": i, "budget": 0, "span": span,
                      "rows": make_rows(rng, rung_n, unit, levels, lane_w)})
    bundle = {"unit": unit, "bins": bins, "cells": cells, "lanes": lanes,
              "fit": fit, "rim": rim, "hold": hold, "rungs": rungs}
    book = Book(bundle["fit"], unit, cells, lanes)
    fit_only = [edges_of(book, f, bundle["fit"], bins) for f in range(3)]
    with_rim = [edges_of(book, f, edge_rows(bundle), bins) for f in range(3)]
    assert any(a != b for a, b in zip(fit_only, with_rim)), (
        f"rim for seed {seed} did not shift any family's edges")
    _book, dev = analyze(bundle)
    return bundle, dev


def cheapest_per_rung(dev):
    """The lowest-deviation family on each rung, ignoring budget and order."""
    return [min(range(3), key=lambda f: dev[i][f]) for i in range(len(dev))]


def held_out(seed):
    """A ladder where only the strongest family meets at least two rungs.

    Budgets are pinned so the two chosen rungs admit `giso` alone: a margin of
    at least one rung's row count guarantees the rounded-up budget cannot reach
    either pooled family. This is the instrument for the budget and
    generalization checks.
    """
    for k in range(64):
        bundle, dev = draft(seed + 1000 * k)
        n_rungs = len(bundle["rungs"])
        margin = [min(dev[i][0], dev[i][1]) - dev[i][2] for i in range(n_rungs)]
        rung_n = len(bundle["rungs"][0]["rows"])
        only = [i for i in reversed(range(n_rungs)) if margin[i] >= rung_n][:2]
        for i, rung in enumerate(bundle["rungs"]):
            n = len(rung["rows"])
            if i in only:
                rung["budget"] = -(-dev[i][2] // n)
            else:
                rung["budget"] = -(-max(dev[i]) // n) + 2
        if len(only) >= 2 and any_ordered_assignment(bundle) is not None:
            return bundle
    raise AssertionError(f"no conforming ladder for seed {seed}")


def open_ladder(seed):
    """A ladder with slack in every budget, where the cheapest-per-rung choice
    is out of order.

    A budget of `unit` allows any family on any rung, because a single row can
    contribute at most `unit` to a deviation. Every implementation therefore
    finds this ladder solvable, which isolates the map, order, and emission
    checks from whether a budget is met. The ladder is still order-sensitive:
    taking the lowest-deviation family on each rung would step strength
    downwards somewhere along the severity order.
    """
    for k in range(64):
        bundle, dev = draft(seed + 1000 * k)
        for rung in bundle["rungs"]:
            rung["budget"] = bundle["unit"]
        greedy = cheapest_per_rung(dev)
        span_break = any(
            greedy[i] - greedy[i - 1] > bundle["rungs"][i].get("span", 2)
            for i in range(1, len(greedy))
        )
        if ((greedy != sorted(greedy) or span_break)
                and any_ordered_assignment(bundle) is not None):
            return bundle
    raise AssertionError(f"no order-sensitive ladder for seed {seed}")


# --------------------------------------------------------------------------
# Harness
# --------------------------------------------------------------------------

def rebuild():
    proc = subprocess.run(["make", "-C", "/app/environment", "rebuild"],
                          capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"rebuild failed:\n{proc.stdout}\n{proc.stderr}"
    assert BIN.exists(), f"{BIN} was not produced by the rebuild"


def run_plan(bundle_path, out_path):
    return subprocess.run(["/app/bin/plangen", "plan", "--input", f"{bundle_path}",
                           "--out", f"{out_path}"],
                          capture_output=True, text=True, timeout=120)


def write_bundle(tmp_path, bundle, name="bundle.json"):
    path = tmp_path / name
    path.write_text(json.dumps(bundle, indent=2) + "\n")
    return path


def encode_canonical(plan):
    """Byte-identical encoding per /app/environment/docs/plan-format.rst."""
    hold = plan["hold"]
    ordered = {
        "unit": plan["unit"],
        "bins": plan["bins"],
        "hold": {
            "hist": hold["hist"],
            "iso": hold["iso"],
            "giso": hold["giso"],
        },
        "rungs": [
            {
                "severity": rec["severity"],
                "family": rec["family"],
                "strength": rec["strength"],
                "deviation": rec["deviation"],
                "allowance": rec["allowance"],
                "values": rec["values"],
            }
            for rec in plan["rungs"]
        ],
    }
    return (json.dumps(ordered, indent=2) + "\n").encode("utf-8")


def plan_for(tmp_path, bundle, name="bundle.json"):
    """Run the built binary over a bundle and return the parsed document."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    src = write_bundle(tmp_path, bundle, name)
    dst = tmp_path / "plan.json"
    proc = run_plan(src, dst)
    assert proc.returncode == 0, (
        f"plan exited {proc.returncode} on a solvable ladder\n{proc.stdout}\n{proc.stderr}")
    assert dst.exists(), "plan exited 0 but wrote no document"
    return json.loads(dst.read_text())


def empty_hist_cell_bundle():
    """Ladder where only hist is feasible and rung rows land in empty cells."""
    unit, cells, bins, lanes = 1000, 4, 4, 1
    fit = ([{"raw": 50, "hit": 0, "lane": 0}] * 40
           + [{"raw": 950, "hit": 1, "lane": 0}] * 40)
    # Hit rate ~3/8 matches empty-cell midpoint 375 for cell 1.
    rows = [{"raw": 300, "hit": 1 if i % 8 < 3 else 0, "lane": 0} for i in range(80)]
    hold = [{"raw": 300, "hit": 0, "lane": 0} for _ in range(40)]
    bundle = {
        "unit": unit, "bins": bins, "cells": cells, "lanes": lanes,
        "fit": fit, "rim": [], "hold": hold,
        "rungs": [
            {"severity": 0, "budget": 0, "span": 2, "rows": rows},
            {"severity": 1, "budget": 0, "span": 1, "rows": list(rows)},
        ],
    }
    book, dev = analyze(bundle)
    mid = round_div(unit * (2 * 1 + 1), 2 * cells)
    assert book.eval(0, 300, 0) == mid, "fixture must exercise empty-cell midpoint"
    assert book.eval(1, 300, 0) != mid, "iso must disagree so hist is uniquely feasible"
    for i, rung in enumerate(bundle["rungs"]):
        n = len(rung["rows"])
        rung["budget"] = -(-dev[i][0] // n)
        assert dev[i][0] <= rung["budget"] * n
        assert min(dev[i][1], dev[i][2]) > rung["budget"] * n
    assert any_ordered_assignment(bundle) == [0, 0]
    return bundle


def giso_fallback_bundle():
    """Fit has no lane-1 rows; giso must fall back to the pooled iso blocks."""
    unit, cells, bins, lanes = 1000, 8, 8, 2
    fit = [{"raw": 100 + 3 * i, "hit": i % 2, "lane": 0} for i in range(80)]
    rows = [{"raw": 350, "hit": 0, "lane": 1},
            {"raw": 450, "hit": 1, "lane": 1}] * 25
    rim = [{"raw": 50, "hit": 0, "lane": 0}] * 40
    hold = [{"raw": 400, "hit": 1, "lane": 1} for _ in range(40)]
    bundle = {
        "unit": unit, "bins": bins, "cells": cells, "lanes": lanes,
        "fit": fit, "rim": rim, "hold": hold,
        "rungs": [{"severity": i, "budget": unit, "span": 2 if i == 0 else 1,
                   "rows": list(rows)} for i in range(3)],
    }
    book = Book(fit, unit, cells, lanes)
    assert book.giso[1] is None, "fixture requires an empty giso lane"
    for raw in (350, 450):
        assert book.eval(2, raw, 1) == book.eval(1, raw, 1)
        assert book.eval(2, raw, 1) != 0
    assert any_ordered_assignment(bundle) is not None
    return bundle


def no_rim_ladder(seed):
    """A solvable ladder with no rim field; budgets recomputed on fit-only edges."""
    for k in range(64):
        bundle, _dev = draft(seed + 1000 * k)
        bundle.pop("rim", None)
        _book, dev = analyze(bundle)
        n_rungs = len(bundle["rungs"])
        rung_n = len(bundle["rungs"][0]["rows"])
        margin = [min(dev[i][0], dev[i][1]) - dev[i][2] for i in range(n_rungs)]
        only = [i for i in reversed(range(n_rungs)) if margin[i] >= rung_n][:2]
        for i, rung in enumerate(bundle["rungs"]):
            n = len(rung["rows"])
            if i in only:
                rung["budget"] = -(-dev[i][2] // n)
            else:
                rung["budget"] = -(-max(dev[i]) // n) + 2
        if len(only) >= 2 and any_ordered_assignment(bundle) is not None:
            return bundle
    for k in range(64):
        bundle, _dev = draft(seed + 2000 * k)
        bundle.pop("rim", None)
        for rung in bundle["rungs"]:
            rung["budget"] = bundle["unit"]
        if any_ordered_assignment(bundle) is not None:
            return bundle
    raise AssertionError(f"no rim-free ladder for seed {seed}")


def assert_rejected(tmp_path, bundle, label):
    case_dir = tmp_path / label
    case_dir.mkdir(parents=True, exist_ok=True)
    src = write_bundle(case_dir, bundle, "bundle.json")
    dst = case_dir / "plan.json"
    if dst.exists():
        dst.unlink()
    proc = run_plan(src, dst)
    assert proc.returncode != 0, f"{label}: malformed bundle was accepted"
    leftover = [p.name for p in case_dir.glob("plan.json")]
    assert leftover == [], f"{label}: document written for a malformed bundle"


def by_severity(plan):
    """Index the document's records by severity, rejecting duplicates."""
    out = {}
    for rec in plan["rungs"]:
        assert rec["severity"] not in out, f"severity {rec['severity']} appears twice"
        out[rec["severity"]] = rec
    return out


def check_conforms(bundle, plan):
    """Recompute every acceptance condition of contract.rst section 7."""
    book, _dev = analyze(bundle)
    ed = [edges_of(book, f, edge_rows(bundle), bundle["bins"]) for f in range(3)]
    records = by_severity(plan)
    assert set(records) == {rg["severity"] for rg in bundle["rungs"]}, (
        "document does not carry exactly one record per rung")

    strengths = []
    for rung in bundle["rungs"]:
        rec = records[rung["severity"]]
        pick = rec["strength"]
        assert pick in (0, 1, 2), f"strength {pick} is not a family"
        assert rec["family"] == FAMILY_NAMES[pick], (
            f"family {rec['family']!r} disagrees with strength {pick}")

        want_values = [book.eval(pick, r["raw"], r["lane"]) for r in rung["rows"]]
        assert rec["values"] == want_values, (
            f"severity {rung['severity']}: emitted values do not equal the "
            f"{FAMILY_NAMES[pick]} fit fold map applied to each row")

        want_dev = tally(book, pick, rung["rows"], ed[pick], bundle["unit"])
        assert rec["deviation"] == want_dev, (
            f"severity {rung['severity']}: emitted deviation {rec['deviation']} "
            f"is not the recomputed {want_dev}")

        want_allow = rung["budget"] * len(rung["rows"])
        assert rec["allowance"] == want_allow, (
            f"severity {rung['severity']}: emitted allowance {rec['allowance']} "
            f"is not budget*rows {want_allow}")
        assert want_dev <= want_allow, (
            f"severity {rung['severity']}: {FAMILY_NAMES[pick]} deviation {want_dev} "
            f"exceeds allowance {want_allow}")
        strengths.append(pick)

    assert strengths == sorted(strengths), (
        f"strengths {strengths} decrease along ascending severity")
    for i in range(1, len(strengths)):
        span = bundle["rungs"][i].get("span", 2)
        assert strengths[i] - strengths[i - 1] <= span, (
            f"severity {bundle['rungs'][i]['severity']}: strength jump "
            f"{strengths[i - 1]}->{strengths[i]} exceeds span {span}")

    assert "hold" in plan, "plan is missing holdout witness"
    hold = plan["hold"]
    assert list(hold) == FAMILY_NAMES, f"hold keys {list(hold)} are not family order"
    for f, name in enumerate(FAMILY_NAMES):
        want = tally(book, f, bundle["hold"], ed[f], bundle["unit"])
        assert hold[name] == want, (
            f"hold[{name}]={hold[name]} is not sealed-edge holdout ECE {want}")


@pytest.fixture(scope="session")
def built():
    rebuild()
    return BIN


@pytest.fixture(scope="session")
def ladders():
    """Tight ladders: at least two rungs that only the strongest family meets."""
    return {seed: held_out(seed) for seed in HELD_OUT_SEEDS}


@pytest.fixture(scope="session")
def slack():
    """One order-sensitive ladder whose budgets admit every family."""
    return open_ladder(HELD_OUT_SEEDS[0])


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------

def test_recomputed_lookup(built, slack, tmp_path):
    """Every emitted value equals the chosen family's fit fold map on that row."""
    bundle = slack
    plan = plan_for(tmp_path, bundle)
    book, _dev = analyze(bundle)
    records = by_severity(plan)
    for rung in bundle["rungs"]:
        rec = records[rung["severity"]]
        pick = rec["strength"]
        want = [book.eval(pick, r["raw"], r["lane"]) for r in rung["rows"]]
        assert len(rec["values"]) == len(rung["rows"]), (
            f"severity {rung['severity']}: {len(rec['values'])} values for "
            f"{len(rung['rows'])} rows")
        assert rec["values"] == want, (
            f"severity {rung['severity']}: values disagree with the recomputed "
            f"{FAMILY_NAMES[pick]} fit fold map")


def test_declared_allowance(built, ladders, tmp_path):
    """Each chosen family's recomputed deviation stays at or under its allowance."""
    bundle = ladders[HELD_OUT_SEEDS[0]]
    plan = plan_for(tmp_path, bundle)
    book, _dev = analyze(bundle)
    ed = [edges_of(book, f, edge_rows(bundle), bundle["bins"]) for f in range(3)]
    records = by_severity(plan)
    for rung in bundle["rungs"]:
        rec = records[rung["severity"]]
        pick = rec["strength"]
        want_dev = tally(book, pick, rung["rows"], ed[pick], bundle["unit"])
        want_allow = rung["budget"] * len(rung["rows"])
        assert rec["allowance"] == want_allow, (
            f"severity {rung['severity']}: allowance is not budget*rows")
        assert rec["deviation"] == want_dev, (
            f"severity {rung['severity']}: emitted deviation {rec['deviation']} "
            f"is not the recomputed {want_dev}")
        assert want_dev <= want_allow, (
            f"severity {rung['severity']}: {FAMILY_NAMES[pick]} is over allowance "
            f"({want_dev} > {want_allow})")


def test_rim_edges_differ_from_fit(built, slack, tmp_path):
    """Sealed fit+rim edges differ from fit-only cuts; plans must use the rim."""
    bundle = slack
    book = Book(bundle["fit"], bundle["unit"], bundle["cells"], bundle["lanes"])
    fit_only = [edges_of(book, f, bundle["fit"], bundle["bins"]) for f in range(3)]
    sealed = [edges_of(book, f, edge_rows(bundle), bundle["bins"]) for f in range(3)]
    assert any(a != b for a, b in zip(fit_only, sealed)), (
        "held-out rim did not shift sealed edges relative to the fit fold")
    plan = plan_for(tmp_path, bundle)
    check_conforms(bundle, plan)
    # A plan measured with fit-only edges cannot match sealed deviations.
    records = by_severity(plan)
    mismatches = 0
    for rung in bundle["rungs"]:
        rec = records[rung["severity"]]
        pick = rec["strength"]
        fit_dev = tally(book, pick, rung["rows"], fit_only[pick], bundle["unit"])
        if rec["deviation"] != fit_dev:
            mismatches += 1
    assert mismatches >= 1, (
        "emitted deviations matched fit-only edges; rim sealing was not required")


def test_choice_strength(built, slack, tmp_path):
    """Chosen strengths never decrease along the severity-ordered rungs."""
    bundle = slack
    plan = plan_for(tmp_path, bundle)
    records = by_severity(plan)
    strengths = [records[rg["severity"]]["strength"] for rg in bundle["rungs"]]
    assert strengths == sorted(strengths), (
        f"strengths {strengths} decrease along ascending severity")


def test_generated_cases(built, ladders, tmp_path):
    """Freshly generated held-out ladders satisfy every acceptance condition."""
    for seed in HELD_OUT_SEEDS:
        bundle = ladders[seed]
        plan = plan_for(tmp_path, bundle, name=f"held-{seed}.json")
        check_conforms(bundle, plan)


def test_repeat_stable(built, slack, tmp_path):
    """The same ladder yields byte-identical documents and leaves inputs alone."""
    bundle = slack
    src = write_bundle(tmp_path, bundle, "bundle.json")
    before = src.read_bytes()
    dst = tmp_path / "plan.json"

    first = run_plan(src, dst)
    assert first.returncode == 0, f"first run exited {first.returncode}"
    once = dst.read_bytes()

    second = run_plan(src, dst)
    assert second.returncode == 0, f"second run exited {second.returncode}"
    twice = dst.read_bytes()

    assert once == twice, "two runs of one ladder are not identical"
    assert src.read_bytes() == before, "the bundle was modified by a run"


def test_output_shape(built, slack, tmp_path):
    """The document carries the documented schema, order, and record counts."""
    bundle = slack
    plan = plan_for(tmp_path, bundle)

    assert plan["unit"] == bundle["unit"], "unit is not copied from the bundle"
    assert plan["bins"] == bundle["bins"], "bins is not copied from the bundle"
    assert set(plan["hold"]) == set(FAMILY_NAMES), "hold must name every family"
    assert len(plan["rungs"]) == len(bundle["rungs"]), (
        f"{len(plan['rungs'])} records for {len(bundle['rungs'])} rungs")

    emitted = [rec["severity"] for rec in plan["rungs"]]
    expected = [rg["severity"] for rg in bundle["rungs"]]
    assert emitted == expected, (
        f"records are ordered {emitted}, not the bundle order {expected}")

    for rec, rung in zip(plan["rungs"], bundle["rungs"]):
        assert set(rec) == {"severity", "family", "strength", "deviation",
                            "allowance", "values"}, f"unexpected fields {sorted(rec)}"
        assert rec["family"] in FAMILY_NAMES, f"family {rec['family']!r} is not a family"
        assert len(rec["values"]) == len(rung["rows"]), (
            f"severity {rung['severity']}: one value per row is required")
        assert all(isinstance(v, int) and 0 <= v <= bundle["unit"]
                   for v in rec["values"]), "values must be integers within [0, unit]"


def test_malformed_rejected(built, tmp_path):
    """Malformed bundles from input-format.rst are rejected without a document."""
    base = held_out(HELD_OUT_SEEDS[0])

    over = json.loads(json.dumps(base))
    over["rungs"][1]["rows"][0]["raw"] = over["unit"] + 5
    assert_rejected(tmp_path, over, "raw-over-unit")

    empty_fit = json.loads(json.dumps(base))
    empty_fit["fit"] = []
    assert_rejected(tmp_path, empty_fit, "empty-fit")

    bad_hit = json.loads(json.dumps(base))
    bad_hit["rim"][0]["hit"] = 2
    assert_rejected(tmp_path, bad_hit, "rim-bad-hit")

    bad_lane = json.loads(json.dumps(base))
    bad_lane["rim"][0]["lane"] = bad_lane["lanes"]
    assert_rejected(tmp_path, bad_lane, "rim-bad-lane")

    zero_unit = json.loads(json.dumps(base))
    zero_unit["unit"] = 0
    assert_rejected(tmp_path, zero_unit, "zero-unit")

    empty_hold = json.loads(json.dumps(base))
    empty_hold["hold"] = []
    assert_rejected(tmp_path, empty_hold, "empty-hold")

    bad_span = json.loads(json.dumps(base))
    bad_span["rungs"][1]["span"] = 3
    assert_rejected(tmp_path, bad_span, "bad-span")

    unordered = json.loads(json.dumps(base))
    unordered["rungs"] = list(reversed(unordered["rungs"]))
    assert_rejected(tmp_path, unordered, "severity-order")


def test_absent_on_infeasible(built, tmp_path):
    """An infeasible ladder removes the destination and exits non-zero."""
    bundle = held_out(HELD_OUT_SEEDS[0])
    for rung in bundle["rungs"]:
        rung["budget"] = 0
    assert any_ordered_assignment(bundle) is None, "ladder was meant to be infeasible"

    src = write_bundle(tmp_path, bundle, "bundle.json")
    dst = tmp_path / "plan.json"
    dst.write_text('{"stale": true}\n')

    proc = run_plan(src, dst)
    assert proc.returncode != 0, "an infeasible ladder exited 0"
    leftover = [p.name for p in tmp_path.glob(dst.name)]
    assert leftover == [], "a stale document survived an infeasible run"


def test_shipped_example_output(built):
    """The shipped steep.json bundle produces /app/out/plan.json."""
    assert STEEP_OUT.exists(), "/app/out/plan.json was not produced"
    plan = json.loads(STEEP_OUT.read_text())
    bundle = json.loads(STEEP.read_text())
    check_conforms(bundle, plan)


def test_stale_fitstore_rejected(built, slack, tmp_path):
    """Foreign-digest fitstore edges must not change a conforming plan."""
    bundle = slack
    digest = fold_digest(bundle)
    FITSTORE.mkdir(parents=True, exist_ok=True)
    foreign_digests = ["0" * 16, "f" * 16]
    for foreign, fill in zip(foreign_digests, (0, bundle["unit"])):
        for name in FAMILY_NAMES:
            d = FITSTORE / foreign / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "edges.json").write_text(
                json.dumps([fill] * (bundle["bins"] - 1)) + "\n")
            (d / "meta.json").write_text(json.dumps({
                "digest": foreign,
                "family": name,
                "bins": bundle["bins"],
            }) + "\n")
    plan = plan_for(tmp_path, bundle, name="bundle.json")
    check_conforms(bundle, plan)
    assert digest not in foreign_digests


def test_runstate_cleared_on_success(built, slack, tmp_path):
    """A successful plan leaves no lock or journal under var/run."""
    bundle = slack
    src = write_bundle(tmp_path, bundle, "bundle.json")
    dst = tmp_path / "plan.json"
    proc = run_plan(src, dst)
    assert proc.returncode == 0, f"plan failed:\n{proc.stderr}"
    base = dst.name
    leftover = sorted(p.name for p in RUNROOT.glob(f"{base}.*"))
    assert leftover == [], f"run state survived success: {leftover}"
    check_conforms(bundle, json.loads(dst.read_text()))


def test_interrupted_resume_monotone(built, slack, tmp_path):
    """A matching journal floor bounds the first rung's strength on resume."""
    bundle = slack
    digest = fold_digest(bundle)
    src = write_bundle(tmp_path, bundle, "bundle.json")
    dst = tmp_path / "plan.json"
    RUNROOT.mkdir(parents=True, exist_ok=True)
    base = dst.name
    (RUNROOT / f"{base}.lock").write_text(digest + "\n")
    (RUNROOT / f"{base}.journal").write_text(json.dumps({
        "digest": digest,
        "floor": 2,
        "marks": [0],
    }) + "\n")
    proc = run_plan(src, dst)
    assert proc.returncode == 0, f"resume plan failed:\n{proc.stderr}"
    plan = json.loads(dst.read_text())
    check_conforms(bundle, plan)
    strengths = [rec["strength"] for rec in plan["rungs"]]
    assert strengths[0] >= 2, (
        f"resume ignored journal floor 2; first strength was {strengths[0]}")
    assert strengths == sorted(strengths)
    leftover = sorted(p.name for p in RUNROOT.glob(f"{base}.*"))
    assert leftover == [], f"run state survived resume: {leftover}"


def test_infeasible_clears_runstate(built, tmp_path):
    """Infeasible ladders clear the destination and the run lock/journal."""
    bundle = held_out(HELD_OUT_SEEDS[0])
    for rung in bundle["rungs"]:
        rung["budget"] = 0
    assert any_ordered_assignment(bundle) is None
    digest = fold_digest(bundle)
    src = write_bundle(tmp_path, bundle, "bundle.json")
    dst = tmp_path / "plan.json"
    dst.write_text('{"stale": true}\n')
    RUNROOT.mkdir(parents=True, exist_ok=True)
    base = dst.name
    (RUNROOT / f"{base}.lock").write_text(digest + "\n")
    (RUNROOT / f"{base}.journal").write_text(json.dumps({
        "digest": digest,
        "floor": 1,
        "marks": [0, 1],
    }) + "\n")
    proc = run_plan(src, dst)
    assert proc.returncode != 0, "infeasible ladder exited 0"
    leftover_dst = [p.name for p in tmp_path.glob(dst.name)]
    assert leftover_dst == [], "destination survived infeasible run"
    leftover_run = sorted(p.name for p in RUNROOT.glob(f"{base}.*"))
    assert leftover_run == [], f"run state survived infeasible: {leftover_run}"


def test_canonical_encoding(built, slack, tmp_path):
    """Plan bytes use key order, two-space indent, and one trailing newline."""
    bundle = slack
    src = write_bundle(tmp_path, bundle, "bundle.json")
    dst = tmp_path / "plan.json"
    proc = run_plan(src, dst)
    assert proc.returncode == 0, f"plan failed:\n{proc.stderr}"
    raw = dst.read_bytes()
    body = raw
    while body and body[-1:] == b"\n":
        body = body[:-1]
    trailing = len(raw) - len(body)
    assert trailing == 1, "plan must end with exactly one trailing newline"
    plan = json.loads(raw)
    assert raw == encode_canonical(plan), (
        "plan encoding is not the canonical form in plan-format.rst")
    check_conforms(bundle, plan)


def test_fitstore_sealed_match(built, slack, tmp_path):
    """After a successful plan, sealed edges match fit-plus-rim recomputation."""
    bundle = slack
    digest = fold_digest(bundle)
    plan = plan_for(tmp_path, bundle, name="bundle.json")
    check_conforms(bundle, plan)
    book = Book(bundle["fit"], bundle["unit"], bundle["cells"], bundle["lanes"])
    want_edges = [
        edges_of(book, f, edge_rows(bundle), bundle["bins"]) for f in range(3)
    ]
    for f, name in enumerate(FAMILY_NAMES):
        edges_path = FITSTORE / digest / name / "edges.json"
        meta_path = FITSTORE / digest / name / "meta.json"
        assert edges_path.exists(), f"missing sealed edges for {name}"
        assert meta_path.exists(), f"missing sealed meta for {name}"
        sealed = json.loads(edges_path.read_text())
        assert sealed == want_edges[f], (
            f"{name}: sealed edges {sealed} != fit-plus-rim edges {want_edges[f]}")
        meta = json.loads(meta_path.read_text())
        assert meta.get("digest") == digest, f"{name}: sealed digest mismatch"
        assert meta.get("family") == name, f"{name}: sealed family mismatch"
        assert meta.get("bins") == bundle["bins"], f"{name}: sealed bins mismatch"


def test_optional_rim_omitted_and_empty(built, tmp_path):
    """Omitted rim and empty rim are equivalent; both seal fit-only edges."""
    omitted = no_rim_ladder(HELD_OUT_SEEDS[1])
    empty = json.loads(json.dumps(omitted))
    empty["rim"] = []

    assert fold_digest(omitted) == fold_digest(empty), (
        "omitted rim and empty rim must share a fold digest")
    assert edge_rows(omitted) == edge_rows(empty) == list(omitted["fit"])

    plan_omitted = plan_for(tmp_path / "omit", omitted, name="bundle.json")
    check_conforms(omitted, plan_omitted)
    plan_empty = plan_for(tmp_path / "empty", empty, name="bundle.json")
    check_conforms(empty, plan_empty)
    assert plan_omitted == plan_empty, (
        "omitted rim and empty rim must produce the same plan document")


def test_empty_hist_cell_midpoint(built, tmp_path):
    """Empty hist cells use the documented midpoint, not zero or a neighbor."""
    bundle = empty_hist_cell_bundle()
    plan = plan_for(tmp_path, bundle, name="bundle.json")
    check_conforms(bundle, plan)
    records = by_severity(plan)
    mid = round_div(bundle["unit"] * (2 * 1 + 1), 2 * bundle["cells"])
    for rung in bundle["rungs"]:
        rec = records[rung["severity"]]
        assert rec["strength"] == 0, "fixture requires hist on every rung"
        assert all(v == mid for v in rec["values"]), (
            f"severity {rung['severity']}: empty-cell values {rec['values'][:4]} "
            f"are not the midpoint {mid}")


def test_giso_empty_lane_fallback(built, tmp_path):
    """giso on a lane with no fit rows falls back to the pooled iso map."""
    bundle = giso_fallback_bundle()
    digest = fold_digest(bundle)
    src = write_bundle(tmp_path, bundle, "bundle.json")
    dst = tmp_path / "plan.json"
    RUNROOT.mkdir(parents=True, exist_ok=True)
    base = dst.name
    (RUNROOT / f"{base}.lock").write_text(digest + "\n")
    (RUNROOT / f"{base}.journal").write_text(json.dumps({
        "digest": digest,
        "floor": 2,
        "marks": [0],
    }) + "\n")
    proc = run_plan(src, dst)
    assert proc.returncode == 0, f"giso fallback plan failed:\n{proc.stderr}"
    plan = json.loads(dst.read_text())
    check_conforms(bundle, plan)
    book = Book(bundle["fit"], bundle["unit"], bundle["cells"], bundle["lanes"])
    records = by_severity(plan)
    for rung in bundle["rungs"]:
        rec = records[rung["severity"]]
        assert rec["strength"] == 2, (
            f"resume floor 2 was ignored; strength={rec['strength']}")
        want = [book.eval(2, r["raw"], r["lane"]) for r in rung["rows"]]
        assert rec["values"] == want
        # Wrong fallback to 0 is the common miss when the empty lane is skipped.
        assert any(v != 0 for v in rec["values"]), (
            "giso empty-lane fallback collapsed to zero")


def test_span_limits(built, slack, tmp_path):
    """Later rungs with span 0 forbid any strength promotion."""
    bundle = json.loads(json.dumps(slack))
    for i, rung in enumerate(bundle["rungs"]):
        rung["budget"] = bundle["unit"]
        if i > 0:
            rung["span"] = 0
    assert any_ordered_assignment(bundle) is not None
    plan = plan_for(tmp_path, bundle, name="bundle.json")
    check_conforms(bundle, plan)
    strengths = [by_severity(plan)[rg["severity"]]["strength"] for rg in bundle["rungs"]]
    assert len(set(strengths)) == 1, (
        f"span 0 must keep a flat strength path, got {strengths}")


def test_holdout_witness(built, slack, tmp_path):
    """Hold reports sealed-edge ECE for every family on the holdout fold."""
    bundle = slack
    plan = plan_for(tmp_path, bundle, name="bundle.json")
    check_conforms(bundle, plan)
    book = Book(bundle["fit"], bundle["unit"], bundle["cells"], bundle["lanes"])
    sealed = [edges_of(book, f, edge_rows(bundle), bundle["bins"]) for f in range(3)]
    fit_only = [edges_of(book, f, bundle["fit"], bundle["bins"]) for f in range(3)]
    assert any(a != b for a, b in zip(sealed, fit_only)), (
        "slack ladder must shift edges via rim so hold cannot use fit-only cuts")
    for f, name in enumerate(FAMILY_NAMES):
        sealed_hold = tally(book, f, bundle["hold"], sealed[f], bundle["unit"])
        assert plan["hold"][name] == sealed_hold
    disagree = [
        FAMILY_NAMES[f]
        for f in range(3)
        if tally(book, f, bundle["hold"], sealed[f], bundle["unit"])
        != tally(book, f, bundle["hold"], fit_only[f], bundle["unit"])
    ]
    assert disagree, "rim must change at least one family's holdout ECE"
