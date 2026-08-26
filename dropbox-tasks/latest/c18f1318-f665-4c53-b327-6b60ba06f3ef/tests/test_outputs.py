"""Behavioral verifier for the mode-consolidation-histogram-profiler task.

The agent must build a Java tool invoked as /app/consolidate <data_file> that
consolidates the modes of one integer histogram self-consistently and reports the
converged partition. The stack under test: every bin climbs to the lowest-position
heaviest bin in its radius window until it settles (initial modes and basins), then
dissolution rounds where the bar floor(M/(q*m)) is recomputed from the CURRENT
surviving mode count (freezing the first bar misses cascades — the reflex error),
basins strictly under the bar dissolve batched and are handed WHOLE to the survivor
nearest the dissolved mode with ties to the lower position (per-bin splitting is the
second reflex error), and the converged partition feeds reduced exact mass fractions,
gap statistics via the lower median, and a floored concentration percent, while
raw_modes and raw_span deliberately ignore the consolidation. A guard directive caps
how many dissolved basins a given mode may absorb across the whole run, not per round,
and a link directive merges guarded modes into one shared budget whose cap is the
smallest declared member cap. Layered on top, and requested by no line in the input,
is an emergent majority saturation latch: a surviving mode that carries an outright
majority of the total mass into a round is barred from receiving any further basin for
the rest of the run, walked past exactly like an exhausted guard, with the same
all-candidates-barred fallback. Saturation is judged on carried-in mass, so a mode
that only crosses the half-mass line from basins arriving in a round still keeps every
basin assigned to it that round and latches only from the next round.

Correctness is checked with hand-verified anchors pinned byte-for-byte (the cascade
anchor is the SPEC.md worked example) plus a random agreement sweep against an
independent Python reference implementing the full computation, over fresh histograms
every run. The candidate binary runs under an unprivileged account via runuser while
/tests is chmod 700 root-only, so it cannot read this file or the reference.
Exit-code paths are exercised directly.
"""
import json
import math
import os
import random
import subprocess
import tempfile

import pytest

CONSOLIDATE = "/app/consolidate"
RESULT = "/app/output/result.json"
RUNNER = ["runuser", "-u", "candidate", "--"]

RNG = random.Random()
WORK = tempfile.mkdtemp(prefix="mchp-fixtures-")


@pytest.fixture(scope="session", autouse=True)
def _isolate_candidate():
    """Lock the harness away from the candidate account before any test runs."""
    os.chmod("/tests", 0o700)
    os.chmod(WORK, 0o755)
    os.makedirs("/app/output", exist_ok=True)
    os.chmod("/app/output", 0o1777)
    yield


# ---------------------------------------------------------------------------
# Independent reference implementation.
# ---------------------------------------------------------------------------

def _lower_median(vals):
    c = sorted(vals)
    m = len(c)
    return c[m // 2] if m % 2 == 1 else c[m // 2 - 1]


def _link_groups(guards, links):
    """Union-find over guarded positions joined by (a, b) link pairs.
    Returns (root_of[pos], cap_of[root]) built independently of the Java
    union-find in solution/Main.java."""
    root_of = {p: p for p in guards}

    def find(p):
        r = p
        while root_of[r] != r:
            r = root_of[r]
        while root_of[p] != r:
            root_of[p], p = r, root_of[p]
        return r

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            root_of[ra] = rb

    for a, b in (links or []):
        union(a, b)
    cap_of = {}
    for p, cap in guards.items():
        r = find(p)
        cap_of[r] = min(cap_of.get(r, cap), cap)
    return {p: find(p) for p in guards}, cap_of


def reference(bins, h=2, q=4, guards=None, links=None, _trace=None):
    """bins: list of (pos, count) with distinct positions. guards: dict pos->cap.
    links: list of (pos1, pos2) pairs merging guarded positions into shared
    absorption budget groups per section 4b. Emergent majority saturation per
    section 4c is applied on top and is requested by no directive. Returns the
    result dict; if _trace is a dict it records whether saturation changed any
    placement relative to the same run without saturation (coverage signal)."""
    guards = guards or {}
    root_of, group_cap = _link_groups(guards, links)
    entries = sorted(bins)
    pos = [p for p, _ in entries]
    cnt = [c for _, c in entries]
    n = len(entries)
    total = sum(cnt)

    def climb_target(i):
        lo, hi = pos[i] - h, pos[i] + h
        best = None
        for j in range(n):
            if lo <= pos[j] <= hi:
                if best is None or cnt[j] > cnt[best] or (
                        cnt[j] == cnt[best] and pos[j] < pos[best]):
                    best = j
        return best

    target = [climb_target(i) for i in range(n)]
    endpoint = []
    for i in range(n):
        cur = i
        while target[cur] != cur:
            cur = target[cur]
        endpoint.append(cur)
    basin = {}
    for i in range(n):
        mp = pos[endpoint[i]]
        basin[mp] = basin.get(mp, 0) + cnt[i]
    raw_modes = len(basin)

    absorbed = {}
    saturated = set()
    fired = False
    rounds = 0
    while True:
        m = len(basin)
        bar = total // (q * m)
        threshold_final = bar
        # Emergent majority saturation, judged on carried-in masses (start of round).
        for mp, mass in basin.items():
            if 2 * mass >= total:
                saturated.add(mp)
        dissolved = [mp for mp in basin if basin[mp] < bar]
        if not dissolved:
            break
        survivors = sorted(mp for mp in basin if mp not in set(dissolved))

        def exhausted(s):
            if s not in guards:
                return False
            r = root_of[s]
            return absorbed.get(r, 0) >= group_cap[r]

        gains = {}
        round_absorptions = {}  # key = group root
        for d in dissolved:
            eligible = [s for s in survivors
                        if not exhausted(s) and s not in saturated]
            best = (min(eligible, key=lambda s: (abs(s - d), s))
                    if eligible else min(survivors, key=lambda s: (abs(s - d), s)))
            # Coverage: would the placement differ with saturation switched off?
            no_sat = [s for s in survivors if not exhausted(s)]
            alt = (min(no_sat, key=lambda s: (abs(s - d), s))
                   if no_sat else min(survivors, key=lambda s: (abs(s - d), s)))
            if alt != best:
                fired = True
            gains[best] = gains.get(best, 0) + basin[d]
            if best in guards:
                r = root_of[best]
                round_absorptions[r] = round_absorptions.get(r, 0) + 1
        for d in dissolved:
            del basin[d]
        for s, g in gains.items():
            basin[s] += g
        for r, a in round_absorptions.items():
            absorbed[r] = absorbed.get(r, 0) + a
        rounds += 1

    modes = sorted(basin)
    heaviest = min(modes, key=lambda mp: (-basin[mp], mp))
    concentration = basin[heaviest] * 100 // total
    gaps = [modes[i] - modes[i - 1] for i in range(1, len(modes))]
    if gaps:
        gap_min, gap_max, gap_median = min(gaps), max(gaps), _lower_median(gaps)
    else:
        gap_min = gap_max = gap_median = 0
    fractions = []
    for mp in modes:
        g = math.gcd(basin[mp], total)
        fractions.append(f"{basin[mp] // g}/{total // g}")
    if _trace is not None:
        _trace["fired"] = fired
    return {
        "n": n, "total_mass": total, "raw_modes": raw_modes,
        "mode_count": len(modes), "rounds": rounds,
        "threshold_final": threshold_final, "mode_positions": modes,
        "fractions": fractions, "heaviest_mode": heaviest,
        "concentration_pct": concentration, "gap_min": gap_min,
        "gap_median": gap_median, "gap_max": gap_max,
        "raw_span": pos[-1] - pos[0],
    }


FIELD_ORDER = ["n", "total_mass", "raw_modes", "mode_count", "rounds",
               "threshold_final", "mode_positions", "fractions", "heaviest_mode",
               "concentration_pct", "gap_min", "gap_median", "gap_max", "raw_span"]


def to_json(r):
    parts = []
    for key in FIELD_ORDER:
        v = r[key]
        if key == "mode_positions":
            parts.append(f'"{key}":[' + ",".join(str(i) for i in v) + "]")
        elif key == "fractions":
            parts.append(f'"{key}":[' + ",".join(f'"{s}"' for s in v) + "]")
        else:
            parts.append(f'"{key}":{v}')
    return "{" + ",".join(parts) + "}"


# ---------------------------------------------------------------------------
# Harness helpers.
# ---------------------------------------------------------------------------

def serialize(bins, h=None, q=None, directive_pos=0, guards=None, links=None):
    lines = [f"b {p} {c}\n" for p, c in bins]
    extra = []
    if h is not None:
        extra.append(f"radius {h}\n")
    if q is not None:
        extra.append(f"sharp {q}\n")
    for pos, cap in (guards or {}).items():
        extra.append(f"guard {pos} {cap}\n")
    for p1, p2 in (links or []):
        extra.append(f"link {p1} {p2}\n")
    for e in extra:
        lines.insert(directive_pos, e)
    return "".join(lines)


def _write_raw(text, binary=False):
    path = os.path.join(WORK, f"t-{RNG.randrange(1 << 40):010x}.txt")
    mode = "wb" if binary else "w"
    with open(path, mode) as f:
        f.write(text)
    os.chmod(path, 0o644)
    return path


def _run(path):
    if os.path.exists(RESULT):
        os.remove(RESULT)
    proc = subprocess.run([*RUNNER, CONSOLIDATE, path], capture_output=True,
                          text=True, timeout=120)
    raw = None
    if os.path.exists(RESULT):
        with open(RESULT) as f:
            raw = f.read()
    return proc, raw


def _run_ok(bins, h=None, q=None, directive_pos=0, guards=None, links=None):
    proc, raw = _run(_write_raw(serialize(bins, h, q, directive_pos, guards, links)))
    assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
    assert raw is not None, "result.json was not written"
    stdout = proc.stdout.strip()
    assert stdout, "nothing printed to stdout"
    assert stdout == raw.strip(), "stdout line and result.json differ"
    return raw.strip(), json.loads(raw)


# ---------------------------------------------------------------------------
# Anchors (hand-verified; the cascade anchor is worked in SPEC.md section 5).
# ---------------------------------------------------------------------------

ANCHOR_CASCADE = [(0, 5), (1, 20), (2, 5), (10, 4), (11, 9), (12, 4),
                  (16, 2), (20, 1), (21, 2)]
ANCHOR_CASCADE_EXPECTED = (
    '{"n":9,"total_mass":52,"raw_modes":4,"mode_count":2,"rounds":2,'
    '"threshold_final":6,"mode_positions":[1,11],"fractions":["15/26","11/26"],'
    '"heaviest_mode":1,"concentration_pct":57,"gap_min":10,"gap_median":10,'
    '"gap_max":10,"raw_span":21}')

ANCHOR_SINGLE = [(5, 7)]
ANCHOR_SINGLE_EXPECTED = (
    '{"n":1,"total_mass":7,"raw_modes":1,"mode_count":1,"rounds":0,'
    '"threshold_final":1,"mode_positions":[5],"fractions":["1/1"],'
    '"heaviest_mode":5,"concentration_pct":100,"gap_min":0,"gap_median":0,'
    '"gap_max":0,"raw_span":0}')


def test_binary_exists():
    """The agent must produce an executable launcher at /app/consolidate."""
    assert os.path.exists(CONSOLIDATE), "/app/consolidate missing"
    assert os.access(CONSOLIDATE, os.X_OK), "/app/consolidate is not executable"


def test_candidate_cannot_read_reference():
    """The unprivileged account running the candidate cannot read the harness."""
    probe = subprocess.run([*RUNNER, "cat", "/tests/test_outputs.py"],
                           capture_output=True, text=True, timeout=60)
    assert probe.returncode != 0, "candidate account can read /tests"
    assert not probe.stdout.strip(), "candidate account read harness content"


def test_stale_root_owned_result_is_replaced():
    """A root-owned leftover result.json must not block the demoted candidate."""
    if os.path.exists(RESULT):
        os.remove(RESULT)
    with open(RESULT, "w") as f:
        f.write("stale\n")
    raw, r = _run_ok(ANCHOR_SINGLE)
    assert raw == ANCHOR_SINGLE_EXPECTED


def test_output_schema():
    """Exact key order and value types."""
    raw, r = _run_ok(ANCHOR_CASCADE)
    assert list(r.keys()) == FIELD_ORDER
    for key in FIELD_ORDER:
        if key in ("mode_positions", "fractions"):
            assert isinstance(r[key], list)
        else:
            assert isinstance(r[key], int) and not isinstance(r[key], bool)
    assert all(isinstance(s, str) and "/" in s for s in r["fractions"])


def test_anchor_cascade():
    """The worked example from SPEC.md, byte-for-byte; the recomputed bar must
    drag the second small basin under only in round two."""
    raw, r = _run_ok(ANCHOR_CASCADE)
    assert raw == ANCHOR_CASCADE_EXPECTED, f"\n got {raw}\n exp {ANCHOR_CASCADE_EXPECTED}"
    assert r == reference(ANCHOR_CASCADE)
    assert r["rounds"] == 2, "the cascade must take two applied rounds"
    assert r["raw_modes"] == 4, "raw_modes must ignore the consolidation"


def test_anchor_single_bin():
    """A one-bin histogram: one mode, zero rounds, gap figures all zero."""
    raw, r = _run_ok(ANCHOR_SINGLE)
    assert raw == ANCHOR_SINGLE_EXPECTED, f"\n got {raw}\n exp {ANCHOR_SINGLE_EXPECTED}"


def test_whole_basin_reassignment():
    """A dissolved basin straddling two survivors moves WHOLE to the mode nearest
    its own mode — per-bin splitting sends part of it the other way. No mode here
    holds a majority, so the saturation latch stays inert."""
    bins = [(8, 3), (10, 30), (13, 1), (15, 1), (17, 1), (20, 28), (22, 4)]
    raw, r = _run_ok(bins, q=3)
    exp = reference(bins, q=3)
    assert raw == to_json(exp)
    assert r["mode_count"] == 2 and r["mode_positions"] == [10, 20]
    assert r["fractions"][0] == "9/17", "whole straddling basin must land on mode 10"


def test_nearest_tie_goes_lower():
    """A dissolved mode equidistant from two survivors joins the lower position."""
    bins = [(0, 20), (10, 2), (20, 20)]
    raw, r = _run_ok(bins)
    exp = reference(bins)
    assert raw == to_json(exp)
    assert r["fractions"] == ["11/21", "10/21"], "tied handoff must go to the lower mode"


def test_plateau_collapses_to_lowest():
    """Equal-count neighbours climb to the lowest position of the plateau."""
    bins = [(5, 2), (6, 2), (7, 2)]
    raw, r = _run_ok(bins)
    assert raw == to_json(reference(bins))
    assert r["raw_modes"] == 1 and r["mode_positions"] == [5]
    assert r["gap_min"] == 0 and r["gap_median"] == 0 and r["gap_max"] == 0


def test_climb_multi_hop():
    """A monotone ridge is climbed hop by hop to its top."""
    bins = [(0, 1), (2, 2), (4, 3), (6, 4)]
    raw, r = _run_ok(bins)
    assert raw == to_json(reference(bins))
    assert r["mode_positions"] == [6] and r["raw_modes"] == 1


def test_radius_directive_changes_partition():
    """A tighter radius keeps apart what the default radius merges."""
    bins = [(0, 5), (2, 3)]
    raw_default, r_default = _run_ok(bins)
    raw_tight, r_tight = _run_ok(bins, h=1)
    assert raw_default == to_json(reference(bins))
    assert raw_tight == to_json(reference(bins, h=1))
    assert r_default["raw_modes"] == 1 and r_tight["raw_modes"] == 2


def test_directive_position_irrelevant():
    """radius and sharp lines apply file-wide wherever they appear."""
    bins = ANCHOR_CASCADE
    for pos_ix in (0, 4, 9):
        raw, r = _run_ok(bins, h=2, q=4, directive_pos=pos_ix)
        assert raw == ANCHOR_CASCADE_EXPECTED, f"directive at {pos_ix} changed result"


def test_receiver_must_be_a_survivor_not_a_co_dissolver():
    """Two basins dissolve in the same round and the geometrically closer of
    the pair to each other is not a legal destination for either one, since it
    is dissolving too; both must travel past it to the one mode that actually
    survives the round."""
    bins = [(0, 1), (5, 2), (50, 100)]
    raw, r = _run_ok(bins)
    exp = reference(bins)
    assert raw == to_json(exp)
    assert r["mode_count"] == 1 and r["mode_positions"] == [50]
    assert r["fractions"] == ["1/1"], "both dissolving basins must land on the sole survivor"
    assert r["rounds"] == 1 and r["raw_modes"] == 3


GUARD_ANCHOR = [(0, 100), (5, 5), (20, 15), (1000, 100)]
GUARD_ANCHOR_EXPECTED = (
    '{"n":4,"total_mass":220,"raw_modes":4,"mode_count":2,"rounds":2,'
    '"threshold_final":27,"mode_positions":[0,1000],"fractions":["21/44","23/44"],'
    '"heaviest_mode":1000,"concentration_pct":52,"gap_min":1000,"gap_median":1000,'
    '"gap_max":1000,"raw_span":1000}')


def test_guard_reroutes_once_exhausted():
    """A guarded mode absorbs one basin in round one then a second dissolution
    that is nearer to it must walk past it to the only other survivor once its
    cap is spent. No basin here reaches a majority, so saturation stays inert."""
    raw, r = _run_ok(GUARD_ANCHOR, guards={0: 1})
    assert raw == GUARD_ANCHOR_EXPECTED, f"\n got {raw}\n exp {GUARD_ANCHOR_EXPECTED}"
    assert r == reference(GUARD_ANCHOR, guards={0: 1})
    assert r["heaviest_mode"] == 1000, "the second basin must not reach the exhausted guard"


def test_guard_ignored_without_directive():
    """The same bins with no guard directive let the second basin land on the
    nearer mode instead, proving the guard actually changes the outcome."""
    raw, r = _run_ok(GUARD_ANCHOR)
    exp = reference(GUARD_ANCHOR)
    assert raw == to_json(exp)
    assert r["heaviest_mode"] == 0, "without a guard the nearer mode wins both basins"


FALLBACK_BINS = [(0, 200), (4, 5), (8, 5), (12, 200), (100, 35)]


def test_guard_fallback_when_all_candidates_exhausted():
    """Two guarded modes each spend their one slot in round one on separate
    close basins, then a later basin whose only candidates are those same two
    exhausted modes must still be placed by the plain nearest rule instead of
    being left stranded."""
    guards = {0: 1, 12: 1}
    raw, r = _run_ok(FALLBACK_BINS, guards=guards)
    exp = reference(FALLBACK_BINS, guards=guards)
    assert raw == to_json(exp)
    assert r["mode_count"] == 2 and r["mode_positions"] == [0, 12]
    assert r["fractions"] == ["41/89", "48/89"], "the fallback must still place the third basin"


# The linked pair reroutes a later basin PAST both group members onto a moderate
# unguarded survivor. A separate far bin holds the total mass high enough that
# the bar still dissolves the small basins; it carries a majority and so latches
# saturated, but it sits far from every dissolution and never wins a placement,
# leaving this a clean single-mechanic test of the shared cap.
LINK_BINS = [(0, 60), (3, 5), (10, 60), (13, 22), (20, 80), (100, 300)]


def test_link_shares_smaller_cap_not_own():
    """0 and 10 are linked with individual caps 5 and 1; the shared group cap is
    the smaller number, 1, not either member's own cap and not their sum. Round
    one spends the group's only slot on 0. Round two's dissolution is nearest to
    10, which still shows its own cap of 5 unspent, but the shared group total is
    already exhausted, so it must walk past both linked members to the moderate
    unguarded survivor at 20."""
    guards = {0: 5, 10: 1}
    links = [(0, 10)]
    raw, r = _run_ok(LINK_BINS, h=1, guards=guards, links=links)
    exp = reference(LINK_BINS, h=1, guards=guards, links=links)
    assert raw == to_json(exp)
    assert r["mode_positions"] == [0, 10, 20, 100]
    assert r["fractions"][1] == "60/527", "10 must not absorb the second basin"
    assert r["fractions"][2] == "6/31", "the second basin reroutes past the group onto 20"


def test_link_ignored_without_link_directive():
    """The identical bins and identical individual guard caps, but with no link
    line, let 10 accept the second basin on its own unshared cap, proving the
    link directive is what changes the outcome above."""
    guards = {0: 5, 10: 1}
    raw, r = _run_ok(LINK_BINS, h=1, guards=guards)
    exp = reference(LINK_BINS, h=1, guards=guards)
    assert raw == to_json(exp)
    assert r["mode_positions"] == [0, 10, 20, 100]
    assert r["fractions"][1] == "82/527", "without linking, 10's own cap absorbs the basin"


CHAIN_BINS = [(0, 60), (3, 5), (10, 60), (20, 60), (23, 22), (30, 80), (100, 340)]


def test_link_chain_is_transitive():
    """0 links to 10 and 10 links to 20, so all three share one group even
    though 0 and 20 are never named on the same link line. The group's shared
    cap is the smallest of the three declared caps. Round one spends the
    group's only slot through 0. Round two's dissolution is nearest to 20, a
    member never directly linked to 0, and must still be skipped because the
    shared group total travels through the chain, landing the basin on the
    moderate unguarded survivor at 30."""
    guards = {0: 3, 10: 1, 20: 2}
    links = [(0, 10), (10, 20)]
    raw, r = _run_ok(CHAIN_BINS, h=1, guards=guards, links=links)
    exp = reference(CHAIN_BINS, h=1, guards=guards, links=links)
    assert raw == to_json(exp)
    assert r["mode_positions"] == [0, 10, 20, 30, 100]
    assert r["fractions"][2] == "20/209", "chained group must block 20 with no direct 0-20 link"
    assert r["fractions"][3] == "34/209", "the basin reroutes past the whole chain onto 30"


def test_link_chain_ignored_without_links():
    """The same three caps with no link lines let 20 accept its own nearby
    dissolution normally, on its own individual cap of 2."""
    guards = {0: 3, 10: 1, 20: 2}
    raw, r = _run_ok(CHAIN_BINS, h=1, guards=guards)
    exp = reference(CHAIN_BINS, h=1, guards=guards)
    assert raw == to_json(exp)
    assert r["mode_positions"] == [0, 10, 20, 30, 100]
    assert r["fractions"][2] == "82/627", "without links, 20's own cap absorbs the basin"


OVERRUN_BINS = [(0, 16), (2, 1), (18, 1), (20, 16), (40, 26)]


def test_link_group_overrun_within_one_round():
    """0 and 20 are linked with caps 3 and 1, so the shared group cap is 1. In
    round one TWO separate basins dissolve, one nearest 0 and one nearest 20,
    and both land on their own group member in that single round, driving the
    shared total to two even though the shared cap is only one, because
    eligibility inside a round is judged only against every earlier round
    combined and never against other basins settling in the same round. An
    implementation that bumped the shared tally after each basin in the round
    would send the second basin elsewhere and diverge here."""
    guards = {0: 3, 20: 1}
    links = [(0, 20)]
    raw, r = _run_ok(OVERRUN_BINS, h=1, guards=guards, links=links)
    exp = reference(OVERRUN_BINS, h=1, guards=guards, links=links)
    assert raw == to_json(exp)
    assert r["rounds"] == 1
    assert r["fractions"][0] == "17/60" and r["fractions"][1] == "17/60", (
        "both group members must each absorb their round-one basin")


# ---------------------------------------------------------------------------
# Emergent majority saturation (section 4c) — undeclared by any directive.
# ---------------------------------------------------------------------------

SAT_ANCHOR = [(0, 100), (2, 1), (9, 30), (100, 40)]
SAT_ANCHOR_EXPECTED = (
    '{"n":4,"total_mass":171,"raw_modes":4,"mode_count":3,"rounds":1,'
    '"threshold_final":14,"mode_positions":[0,9,100],'
    '"fractions":["100/171","31/171","40/171"],"heaviest_mode":0,'
    '"concentration_pct":58,"gap_min":9,"gap_median":9,"gap_max":91,"raw_span":100}')


def test_saturation_reroutes_off_the_majority_mode():
    """Mode 0 carries an outright majority of the total mass, so it latches
    saturated and is barred from receiving. The lone dissolving basin sits
    nearest to 0, yet must walk past it to the next nearest survivor at 9. No
    line in the input requests any of this — it emerges from the masses."""
    raw, r = _run_ok(SAT_ANCHOR, h=1)
    assert raw == SAT_ANCHOR_EXPECTED, f"\n got {raw}\n exp {SAT_ANCHOR_EXPECTED}"
    assert r == reference(SAT_ANCHOR, h=1)
    assert r["fractions"][0] == "100/171", "the majority mode must not grow"
    assert r["fractions"][1] == "31/171", "the basin reroutes onto 9"


SAT_CARRY_BINS = [(0, 30), (8, 2), (10, 36), (12, 2), (60, 4)]
SAT_CARRY_EXPECTED = (
    '{"n":5,"total_mass":74,"raw_modes":5,"mode_count":2,"rounds":2,'
    '"threshold_final":9,"mode_positions":[0,10],"fractions":["17/37","20/37"],'
    '"heaviest_mode":10,"concentration_pct":54,"gap_min":10,"gap_median":10,'
    '"gap_max":10,"raw_span":60}')


def test_saturation_is_judged_on_carried_in_mass():
    """Mode 10 carries mass below half into round one and so is NOT saturated
    for that round; both nearby basins land on it in that single round, pushing
    it to a majority. It latches only from round two, where a later dissolution
    that is nearest to it is instead rerouted to 0. Judging saturation mid round
    would strand one of the two round-one basins and diverge."""
    raw, r = _run_ok(SAT_CARRY_BINS, h=1)
    assert raw == SAT_CARRY_EXPECTED, f"\n got {raw}\n exp {SAT_CARRY_EXPECTED}"
    assert r == reference(SAT_CARRY_BINS, h=1)
    assert r["fractions"][1] == "20/37", "both round-one basins must land on 10"


SAT_FALLBACK_BINS = [(0, 20), (2, 1), (90, 5), (100, 55)]
SAT_FALLBACK_EXPECTED = (
    '{"n":4,"total_mass":81,"raw_modes":4,"mode_count":2,"rounds":2,'
    '"threshold_final":10,"mode_positions":[0,100],"fractions":["7/27","20/27"],'
    '"heaviest_mode":100,"concentration_pct":74,"gap_min":100,"gap_median":100,'
    '"gap_max":100,"raw_span":100}')


def test_saturation_fallback_places_on_a_saturated_mode():
    """After the guard at 0 spends its only slot, a later dissolution has no
    eligible survivor at all — 0 is guard exhausted and 100 carries a majority
    and is saturated. The fallback sets BOTH bars aside for that one basin, so
    it lands on the saturated mode 100 rather than being dropped. Removing
    saturated modes from the fallback would misplace it onto 0."""
    guards = {0: 1}
    raw, r = _run_ok(SAT_FALLBACK_BINS, h=1, guards=guards)
    assert raw == SAT_FALLBACK_EXPECTED, f"\n got {raw}\n exp {SAT_FALLBACK_EXPECTED}"
    assert r == reference(SAT_FALLBACK_BINS, h=1, guards=guards)
    assert r["fractions"][1] == "20/27", "the fallback basin must fold into the saturated mode"


def test_gap_statistics():
    """Gaps between consecutive surviving modes: min, lower median, max."""
    bins = [(0, 10), (5, 10), (15, 10), (40, 10)]
    raw, r = _run_ok(bins)
    exp = reference(bins)
    assert raw == to_json(exp)
    assert r["mode_count"] == 4
    assert (r["gap_min"], r["gap_median"], r["gap_max"]) == (5, 10, 25)


def test_heaviest_tie_goes_lower():
    """Two basins of equal mass: the heaviest mode is the lower position."""
    bins = [(0, 5), (10, 5)]
    raw, r = _run_ok(bins)
    assert raw == to_json(reference(bins))
    assert r["heaviest_mode"] == 0 and r["concentration_pct"] == 50


def test_fraction_reduction():
    """Mass fractions are reduced to lowest terms."""
    bins = [(0, 2), (10, 6)]
    raw, r = _run_ok(bins)
    assert raw == to_json(reference(bins))
    assert r["fractions"] == ["1/4", "3/4"]


def test_raw_vs_converged_split():
    """raw_modes and raw_span ignore the consolidation entirely."""
    raw, r = _run_ok(ANCHOR_CASCADE)
    assert r["raw_modes"] == 4 and r["mode_count"] == 2
    assert r["raw_span"] == 21


def test_comments_and_blanks_ignored():
    """Comment and blank lines are skipped and line numbers still count them."""
    text = ("# histogram\n\nb 0 5\nb 1 20\nb 2 5\nb 10 4\nb 11 9\nb 12 4\n"
            "b 16 2\nb 20 1\nb 21 2\n")
    proc, raw = _run(_write_raw(text))
    assert proc.returncode == 0
    assert raw.strip() == ANCHOR_CASCADE_EXPECTED


# ---------------------------------------------------------------------------
# Malformed inputs.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,code,line", [
    ("b 1 1\nb 1 2\n", "duplicate_pos", 2),
    ("b 1 1\nb 2 0\n", "bad_count", 2),
    ("b 1 1\nb 2 2000000000\n", "bad_count", 2),
    ("b 1 1\nb 2000000000 1\n", "bad_pos", 2),
    ("b 1 1\nb -2000000000 1\n", "bad_pos", 2),
    ("b 1 1\nradius 0\n", "bad_radius", 2),
    ("b 1 1\nradius 51\n", "bad_radius", 2),
    ("b 1 1\nradius 2\nradius 3\n", "duplicate_radius", 3),
    ("b 1 1\nsharp 0\n", "bad_sharp", 2),
    ("b 1 1\nsharp 1000001\n", "bad_sharp", 2),
    ("b 1 1\nsharp 2\nsharp 2\n", "duplicate_sharp", 3),
    ("radius 5\n", "no_bins", 0),
    ("b 1 1\nguard 2000000000 1\n", "bad_guard_pos", 2),
    ("b 1 1\nguard -2000000000 1\n", "bad_guard_pos", 2),
    ("b 1 1\nguard 1 0\n", "bad_guard_cap", 2),
    ("b 1 1\nguard 1 2000000000\n", "bad_guard_cap", 2),
    ("b 1 1\nguard 1 1\nguard 1 2\n", "duplicate_guard", 3),
    ("b 1 1\nguard 2 1\n", "unknown_guard", 2),
    ("b 1 1\nb 2 1\nguard 3 1\nguard 4 1\n", "unknown_guard", 3),
    ("b 1 1\nguard 1 1\nlink 2000000000 1\n", "bad_link_pos", 3),
    ("b 1 1\nguard 1 1\nlink 1 -2000000000\n", "bad_link_pos", 3),
    ("b 1 1\nguard 1 1\nlink 1 1\n", "link_self", 3),
    ("b 1 1\nb 2 1\nguard 1 1\nguard 2 1\nlink 1 2\nlink 2 1\n", "duplicate_link", 6),
    ("b 1 1\nb 2 1\nguard 1 1\nguard 2 1\nlink 1 2\nlink 1 2\n", "duplicate_link", 6),
    ("b 1 1\nguard 1 1\nlink 1 2\n", "unknown_link", 3),
    ("b 1 1\nb 2 1\nguard 1 1\nguard 2 1\nlink 1 5\nlink 5 2\n", "unknown_link", 5),
    ("b 1 1\nb 2 1\nguard 1 1\nlink 1 2\n", "link_unguarded", 4),
])
def test_malformed(text, code, line):
    proc, raw = _run(_write_raw(text))
    assert proc.returncode == 0, f"expected exit 0, got {proc.returncode} for {text!r}"
    assert raw is not None
    assert raw.strip() == f'{{"status":"malformed","error":"{code}","line":{line}}}'


# ---------------------------------------------------------------------------
# Exit codes.
# ---------------------------------------------------------------------------

def test_exit_wrong_args():
    if os.path.exists(RESULT):
        os.remove(RESULT)
    proc = subprocess.run([*RUNNER, CONSOLIDATE], capture_output=True, text=True,
                          timeout=60)
    assert proc.returncode == 2
    assert not os.path.exists(RESULT)


def test_exit_unreadable_file():
    if os.path.exists(RESULT):
        os.remove(RESULT)
    proc = subprocess.run([*RUNNER, CONSOLIDATE, os.path.join(WORK, "missing.txt")],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 1
    assert not os.path.exists(RESULT)


@pytest.mark.parametrize("text", [
    "bin 1 1\n",          # unknown keyword
    "b 1\n",              # wrong field count
    "b 1 1 1\n",          # too many fields
    "b 1 1.5\n",          # non-integer count
    "b +1 1\n",           # not a plain decimal integer
    "radius x\n",         # non-integer radius
    "guard 1\n",          # wrong field count
    "guard 1 1 1\n",      # too many fields
    "guard x 1\n",        # non-integer position
    "guard 1 x\n",        # non-integer cap
    "link 1\n",           # wrong field count
    "link 1 2 3\n",       # too many fields
    "link x 1\n",         # non-integer pos1
    "link 1 x\n",         # non-integer pos2
])
def test_exit_parse_errors(text):
    proc, raw = _run(_write_raw(text))
    assert proc.returncode == 3, f"expected exit 3, got {proc.returncode} for {text!r}"
    assert raw is None


def test_exit_non_utf8():
    proc, raw = _run(_write_raw(b"b 1 1\n\xff\xfe radius\n", binary=True))
    assert proc.returncode == 3
    assert raw is None


# ---------------------------------------------------------------------------
# Randomized agreement against the reference (the load-bearing test).
# ---------------------------------------------------------------------------

def test_many_random_agree():
    """320 random histograms must match the independent reference exactly."""
    fired = 0
    for i in range(320):
        n = RNG.randint(3, 30)
        positions = RNG.sample(range(-60, 61), n)
        bins = []
        for p in sorted(positions):
            c = RNG.randint(1, 40)
            if RNG.random() < 0.15:
                c += RNG.randint(100, 900)
            bins.append((p, c))
        h = RNG.choice([None, 1, 2, 3, 5])
        q = RNG.choice([None, 1, 2, 3, 4, 6])
        pos_ix = RNG.randint(0, n)
        guards = {}
        if RNG.random() < 0.5:
            guard_positions = RNG.sample([p for p, _ in bins], RNG.randint(1, min(3, n)))
            guards = {p: RNG.choice([1, 1, 1, 2, 2, 3]) for p in guard_positions}
        links = []
        if len(guards) >= 2 and RNG.random() < 0.65:
            guard_list = list(guards)
            RNG.shuffle(guard_list)
            num_links = RNG.randint(1, len(guard_list) - 1)
            for k in range(num_links):
                links.append((guard_list[k], guard_list[k + 1]))
        trace = {}
        expected = to_json(reference(bins,
                                     h if h is not None else 2,
                                     q if q is not None else 4,
                                     guards, links, _trace=trace))
        if trace.get("fired"):
            fired += 1
        proc, raw = _run(_write_raw(serialize(bins, h, q, pos_ix, guards, links)))
        assert proc.returncode == 0, (
            f"iteration {i}: exit {proc.returncode}\nbins={bins} h={h} q={q} guards={guards} links={links}\n"
            f"{proc.stderr}")
        assert raw is not None, f"iteration {i}: no result.json"
        assert raw.strip() == expected, (
            f"iteration {i} mismatch\nbins={bins} h={h} q={q} guards={guards} links={links}\n"
            f" got {raw.strip()}\n exp {expected}")
    print(f"\n[general sweep] saturation changed a placement in {fired}/320 histograms")


def test_saturation_stress_agree():
    """A sweep biased so an emergent majority mode almost always exists with
    small basins dissolving next to it, exercising the saturation latch far
    more often than the general sweep. The independent reference must still
    match every object, and the fraction of histograms where saturation
    actually changed a placement is reported and asserted to be substantial."""
    fired = 0
    iters = 260
    for i in range(iters):
        n = RNG.randint(4, 24)
        positions = sorted(RNG.sample(range(-60, 61), n))
        bins = [[p, RNG.randint(1, 30)] for p in positions]
        for b in bins:
            if RNG.random() < 0.2:
                b[1] += RNG.randint(100, 900)
        # Plant a dominant bin carrying a strict majority, and force a couple of
        # its nearest neighbours tiny so they dissolve straight toward it.
        di = RNG.randrange(len(bins))
        tot = sum(x for _, x in bins)
        bins[di][1] += tot
        dp = bins[di][0]
        near = sorted(range(len(bins)), key=lambda k: abs(bins[k][0] - dp))
        for k in near[1:3]:
            bins[k][1] = RNG.randint(1, 3)
        bins = [(p, c) for p, c in bins]
        h = RNG.choice([None, 1, 2, 3, 5])
        q = RNG.choice([None, 1, 2, 3, 4, 6])
        pos_ix = RNG.randint(0, n)
        guards = {}
        if RNG.random() < 0.6:
            guard_positions = RNG.sample([p for p, _ in bins], RNG.randint(1, min(3, n)))
            guards = {p: RNG.choice([1, 1, 1, 2, 2, 3]) for p in guard_positions}
        links = []
        if len(guards) >= 2 and RNG.random() < 0.65:
            guard_list = list(guards)
            RNG.shuffle(guard_list)
            num_links = RNG.randint(1, len(guard_list) - 1)
            for k in range(num_links):
                links.append((guard_list[k], guard_list[k + 1]))
        trace = {}
        expected = to_json(reference(bins,
                                     h if h is not None else 2,
                                     q if q is not None else 4,
                                     guards, links, _trace=trace))
        if trace.get("fired"):
            fired += 1
        proc, raw = _run(_write_raw(serialize(bins, h, q, pos_ix, guards, links)))
        assert proc.returncode == 0, (
            f"iteration {i}: exit {proc.returncode}\nbins={bins} h={h} q={q} guards={guards} links={links}\n"
            f"{proc.stderr}")
        assert raw is not None, f"iteration {i}: no result.json"
        assert raw.strip() == expected, (
            f"iteration {i} mismatch\nbins={bins} h={h} q={q} guards={guards} links={links}\n"
            f" got {raw.strip()}\n exp {expected}")
    frac = fired / iters
    print(f"\n[saturation stress] latch changed a placement in {fired}/{iters} = {frac:.2f}")
    assert frac >= 0.6, f"saturation stress sweep only exercised the latch {frac:.2f} of the time"
