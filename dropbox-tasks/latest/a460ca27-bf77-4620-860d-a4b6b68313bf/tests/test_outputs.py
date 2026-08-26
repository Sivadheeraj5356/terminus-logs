"""Behavioral verifier for the haul-permit throttle report.

Each test writes a quarry-config file and a traffic-stream file to a temp
directory, runs report.py in /app as a black box, and asserts the emitted
ledger against the contract in /app/docs/spec.md. The verifier supplies its
own fixtures and an independent reference reducer for a randomized
differential cross-check.
"""

import os
import random
import subprocess
import tempfile

import pytest

APP_DIR = os.environ.get("APP_DIR", "/app")
REPORT = os.path.join(APP_DIR, "report.py")


@pytest.fixture(scope="module", autouse=True)
def check_report():
    """Confirm the data-processing tool is present before exercising it."""
    assert os.path.exists(REPORT), f"report.py not found at {REPORT}"


def run(config_text, events_text):
    """Run the tool on the two input texts; return (rc, stdout, stderr)."""
    d = tempfile.mkdtemp()
    cfg = os.path.join(d, "quarry.cfg")
    ev = os.path.join(d, "traffic.log")
    with open(cfg, "w") as f:
        f.write(config_text)
    with open(ev, "w") as f:
        f.write(events_text)
    try:
        proc = subprocess.run(
            ["python3", REPORT, cfg, ev], capture_output=True, text=True, timeout=60
        )
    finally:
        os.unlink(cfg)
        os.unlink(ev)
        os.rmdir(d)
    return proc.returncode, proc.stdout, proc.stderr


def ledger(config_text, events_text):
    """Run a valid scenario and return its ledger as a list of output lines."""
    rc, out, err = run(config_text, events_text)
    assert rc == 0, f"unexpected nonzero exit ({rc}); stderr={err!r}"
    return out.splitlines()


# ---------------------------------------------------------------------------
# Independent reference reducer (mirrors docs/spec.md) for the differential
# cross-check. Kept deliberately separate from the report under test.
# ---------------------------------------------------------------------------
def reference_ledger(config_text, events_text):
    users, groups, member_of = {}, {}, {}
    for raw in config_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        f = line.split()
        if f[0] == "TRUCK":
            assert len(f) == 5
            soft, hard, grace = int(f[2]), int(f[3]), int(f[4])
            assert soft >= 0 and hard >= 0 and grace >= 0 and hard >= soft
            users[f[1]] = {"soft": soft, "hard": hard, "grace": grace}
        elif f[0] == "QUARRY":
            assert len(f) in (5, 6)
            soft, hard, grace = int(f[2]), int(f[3]), int(f[4])
            reserve = int(f[5]) if len(f) == 6 else 0
            assert soft >= 0 and hard >= 0 and grace >= 0 and reserve >= 0
            assert hard >= soft
            groups[f[1]] = {
                "soft": soft,
                "hard": hard,
                "grace": grace,
                "reserve": reserve,
            }
        elif f[0] == "ASSIGN":
            assert len(f) == 3
            member_of[f[1]] = f[2]
        else:
            raise ValueError("bad directive")
    for u in users:
        assert u in member_of and member_of[u] in groups

    events = []
    for raw in events_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        f = line.split()
        assert len(f) == 4
        tick, kind, user, blocks = int(f[0]), f[1], f[2], int(f[3])
        assert tick >= 0 and user in users and blocks > 0
        assert kind in ("HAUL", "RETURN")
        events.append((tick, kind, user, blocks))

    ust = {u: {"traffic": 0, "run": False, "start": 0, "debt": []} for u in users}
    gst = {g: {"traffic": 0, "run": False, "start": 0, "rused": 0} for g in groups}

    def ceiling(q, traffic, run_, start, tick):
        if traffic > q["soft"] and run_ and tick > start + q["grace"]:
            return q["soft"]
        return q["hard"]

    def update_timer(soft, traffic, st, tick):
        started = False
        if traffic > soft:
            if not st["run"]:
                st["run"] = True
                st["start"] = tick
                started = True
        else:
            st["run"] = False
        return started

    out = []
    for tick, kind, user, blocks in events:
        group = member_of[user]
        uq, gq = users[user], groups[group]
        us, gs = ust[user], gst[group]
        if kind == "RETURN":
            remaining = blocks
            repaid = 0
            while remaining > 0 and us["debt"]:
                top = us["debt"][-1]
                take = min(remaining, top)
                top -= take
                remaining -= take
                repaid += take
                if top == 0:
                    us["debt"].pop()
                else:
                    us["debt"][-1] = top
            if repaid > 0:
                gs["rused"] -= repaid
                out.append("%d REPAY %s %d" % (tick, user, repaid))
            if remaining > 0:
                us["traffic"] = max(0, us["traffic"] - remaining)
                update_timer(uq["soft"], us["traffic"], us, tick)
                gs["traffic"] = max(0, gs["traffic"] - remaining)
                update_timer(gq["soft"], gs["traffic"], gs, tick)
            continue

        n = blocks
        if uq["hard"] - us["traffic"] < n:
            out.append("%d DENY TRUCK_FULL" % tick)
            continue
        if gq["hard"] - gs["traffic"] < n:
            out.append("%d DENY QUARRY_FULL" % tick)
            continue
        uc = ceiling(uq, us["traffic"], us["run"], us["start"], tick)
        gc = ceiling(gq, gs["traffic"], gs["run"], gs["start"], tick)
        user_room = max(0, uc - us["traffic"])
        group_room = max(0, gc - gs["traffic"])
        grant = min(n, user_room, group_room)
        shortfall = n - grant
        if shortfall > 0:
            if gq["reserve"] - gs["rused"] < shortfall:
                out.append("%d DENY RESERVE_EMPTY" % tick)
                continue

        out.append("%d PERMITTED" % tick)
        started_u = started_g = False
        if grant > 0:
            us["traffic"] += grant
            started_u = update_timer(uq["soft"], us["traffic"], us, tick)
            gs["traffic"] += grant
            started_g = update_timer(gq["soft"], gs["traffic"], gs, tick)
        if shortfall > 0:
            gs["rused"] += shortfall
            us["debt"].append(shortfall)
        if started_u:
            out.append("%d SURGE_START TRUCK %s" % (tick, user))
        if started_g:
            out.append("%d SURGE_START QUARRY %s" % (tick, group))
        if shortfall > 0:
            out.append("%d DRAW %s %d" % (tick, user, shortfall))
    return out


# ---------------------------------------------------------------------------
# Core allowance / surge hand fixtures
# ---------------------------------------------------------------------------
def test_cap_blocks_immediately():
    """A traffic event that would exceed the truck cap is denied at once
    and leaves the counter untouched, so a later in-bounds traffic event still
    succeeds."""
    cfg = "TRUCK a 10 12 5\nQUARRY g 1000 2000 5\nASSIGN a g\n"
    ev = "0 HAUL a 13\n0 HAUL a 5\n"
    assert ledger(cfg, ev) == ["0 DENY TRUCK_FULL", "0 PERMITTED"]


def test_group_cap_checked_after_sub():
    """When the truck allowance permits but the quarry cap does not, the
    denial cites QUARRY_FULL."""
    cfg = "TRUCK a 1000 1000 5\nQUARRY g 5 8 5\nASSIGN a g\n"
    ev = "0 HAUL a 9\n"
    assert ledger(cfg, ev) == ["0 DENY QUARRY_FULL"]


def test_throttle_cross_starts_surge_and_allows_within():
    """Crossing the throttle threshold opens a surge window and announces
    SURGE_START; further traffic events within the window and under the cap are
    still granted normally."""
    cfg = "TRUCK a 10 100 3\nQUARRY g 1000 2000 9\nASSIGN a g\n"
    ev = "2 HAUL a 11\n3 HAUL a 1\n"
    assert ledger(cfg, ev) == ["2 PERMITTED", "2 SURGE_START TRUCK a", "3 PERMITTED"]


def test_inclusive_surge_boundary_within_window_allows_normally():
    """While the surge window is open, traffic events up to the cap are granted
    normally with no reserve-pool draw; the far edge is inclusive."""
    cfg = "TRUCK a 10 100 3\nQUARRY g 1000 2000 9\nASSIGN a g\n"
    # window opens at tick 2 -> open through tick 5 inclusive.
    ev = "2 HAUL a 11\n5 HAUL a 1\n"
    assert ledger(cfg, ev) == ["2 PERMITTED", "2 SURGE_START TRUCK a", "5 PERMITTED"]


def test_recross_restarts_full_window_not_resume():
    """After a cancel, re-crossing the throttle threshold opens a FULL new
    window from the later crossing rather than resuming the earlier window's
    remainder."""
    cfg = "TRUCK a 5 100 3\nQUARRY g 1000 2000 50\nASSIGN a g\n"
    # t1 cross (window t1..t4); t2 credit under throttle -> cancel; t3 re-cross
    # -> restart (window t3..t6).
    ev = "1 HAUL a 6\n2 RETURN a 3\n3 HAUL a 3\n"
    assert ledger(cfg, ev) == [
        "1 PERMITTED",
        "1 SURGE_START TRUCK a",
        "3 PERMITTED",
        "3 SURGE_START TRUCK a",
    ]


def test_no_repeat_surge_start_while_staying_over_throttle():
    """Staying over the throttle threshold across several traffic events announces
    SURGE_START only once, at the opening crossing."""
    cfg = "TRUCK a 5 100 9\nQUARRY g 1000 2000 50\nASSIGN a g\n"
    ev = "0 HAUL a 6\n1 HAUL a 1\n2 HAUL a 1\n"
    assert ledger(cfg, ev) == [
        "0 PERMITTED",
        "0 SURGE_START TRUCK a",
        "1 PERMITTED",
        "2 PERMITTED",
    ]


def test_credit_under_throttle_cancels_timer_no_output():
    """A credit that drops traffic back under the throttle threshold cancels the
    running window and emits no line (it repays no pool debt); a later traffic
    event that stays under the throttle threshold is a plain PERMITTED."""
    cfg = "TRUCK a 5 100 2\nQUARRY g 1000 2000 9\nASSIGN a g\n"
    ev = "0 HAUL a 6\n1 RETURN a 3\n9 HAUL a 2\n"
    assert ledger(cfg, ev) == ["0 PERMITTED", "0 SURGE_START TRUCK a", "9 PERMITTED"]


# ---------------------------------------------------------------------------
# Shared reserve pool: borrow, denial, and the decisive LIFO refund-unwind
# ---------------------------------------------------------------------------
def test_surge_expired_borrows_from_pool_without_surge_start():
    """Once an allowance's surge has expired, the shortfall above its throttle
    ceiling is borrowed from the quarry reserve pool instead of denied; the borrow
    draws on a separate pool and does not open a surge window."""
    cfg = "TRUCK a 1000 100000 9\nQUARRY g 5 100 2 20\nASSIGN a g\n"
    # t0 use 6 -> quarry over throttle within surge (window 0..2) -> SURGE_START.
    # t5 use 4 -> quarry surge expired, normal room 0 -> borrow 4 from pool.
    ev = "0 HAUL a 6\n5 HAUL a 4\n"
    assert ledger(cfg, ev) == [
        "0 PERMITTED",
        "0 SURGE_START QUARRY g",
        "5 PERMITTED",
        "5 DRAW a 4",
    ]


def test_no_pool_means_surge_expired_use_is_denied():
    """With the default pool of zero, a traffic event that exceeds the
    throttle-surge ceiling has nowhere to borrow from and is denied as
    pool-exhausted."""
    cfg = "TRUCK a 1000 100000 0\nQUARRY g 5 100 0\nASSIGN a g\n"
    # t0 use 6 over throttle within surge (grace 0 -> window only tick 0).
    # t1 use 1 -> surge expired, room 0, no pool -> RESERVE_EMPTY.
    ev = "0 HAUL a 6\n1 HAUL a 1\n"
    assert ledger(cfg, ev) == [
        "0 PERMITTED",
        "0 SURGE_START QUARRY g",
        "1 DENY RESERVE_EMPTY",
    ]


def test_pool_exhausted_is_all_or_nothing():
    """A shortfall the free pool cannot fully cover denies the whole traffic event
    and changes nothing, so a smaller request that does fit is later allowed and
    borrows."""
    cfg = "TRUCK a 1000 100000 0\nQUARRY g 5 100 0 3\nASSIGN a g\n"
    # t0 use 6 -> over throttle (window tick 0) SURGE_START.
    # t1 use 4 -> shortfall 4 > free pool 3 -> DENY (no partial borrow).
    # t2 use 3 -> shortfall 3 == pool 3 -> PERMITTED + DRAW 3.
    ev = "0 HAUL a 6\n1 HAUL a 4\n2 HAUL a 3\n"
    assert ledger(cfg, ev) == [
        "0 PERMITTED",
        "0 SURGE_START QUARRY g",
        "1 DENY RESERVE_EMPTY",
        "2 PERMITTED",
        "2 DRAW a 3",
    ]


def test_credit_repays_debt_lifo_newest_first():
    """A credit first repays the truck's pool debt, unwinding borrows
    newest-first; the REPAY line reports the total returned to the pool."""
    cfg = "TRUCK a 1000 100000 0\nQUARRY g 5 100 0 20\nASSIGN a g\n"
    # t0 use 6 (over throttle, window tick 0) SURGE_START.
    # t1 borrow 3, t2 borrow 2 -> debt stack [3, 2].
    # t3 credit 4 -> repay 2 (newest) then 2 of the 3 -> repaid 4, debt [1].
    ev = "0 HAUL a 6\n1 HAUL a 3\n2 HAUL a 2\n3 RETURN a 4\n"
    assert ledger(cfg, ev) == [
        "0 PERMITTED",
        "0 SURGE_START QUARRY g",
        "1 PERMITTED",
        "1 DRAW a 3",
        "2 PERMITTED",
        "2 DRAW a 2",
        "3 REPAY a 4",
    ]


def test_credit_repays_debt_first_then_reduces_own_usage():
    """When a credit is larger than the outstanding debt, it settles the debt
    first (returning those hauls to the pool) and only the remainder reduces the
    truck's own traffic, which can in turn cancel a surge window."""
    cfg = "TRUCK a 1000 100000 0\nQUARRY g 5 100 0 20\nASSIGN a g\n"
    # t0 use 6 over throttle SURGE_START (grant 6). t1 borrow 3 (debt [3]).
    # t2 credit 5 -> repay 3 (debt empty), remaining 2 reduces own traffic 6 -> 4.
    #   traffic 4 <= soft 5 -> quarry window cancels (no extra output).
    ev = "0 HAUL a 6\n1 HAUL a 3\n2 RETURN a 5\n"
    assert ledger(cfg, ev) == [
        "0 PERMITTED",
        "0 SURGE_START QUARRY g",
        "1 PERMITTED",
        "1 DRAW a 3",
        "2 REPAY a 3",
    ]


def test_borrowed_unit_credited_to_pool_reenable_a_later_borrow():
    """Repaying debt returns capacity to the shared reserve pool, so a later traffic
    event that would otherwise be pool-exhausted can borrow again."""
    cfg = "TRUCK a 1000 100000 0\nQUARRY g 5 100 0 3\nASSIGN a g\n"
    # t0 use 6 SURGE_START. t1 borrow 3 (pool now full).
    # t2 use 1 -> shortfall 1 > free 0 -> DENY RESERVE_EMPTY.
    # t3 credit 3 -> repay 3 (pool free again). t4 use 2 -> borrow 2.
    ev = "0 HAUL a 6\n1 HAUL a 3\n2 HAUL a 1\n3 RETURN a 3\n4 HAUL a 2\n"
    assert ledger(cfg, ev) == [
        "0 PERMITTED",
        "0 SURGE_START QUARRY g",
        "1 PERMITTED",
        "1 DRAW a 3",
        "2 DENY RESERVE_EMPTY",
        "3 REPAY a 3",
        "4 PERMITTED",
        "4 DRAW a 2",
    ]


def test_contended_pool_is_deterministic_across_users():
    """Two trucks share one quarry pool. Borrows are charged to whoever uses
    data, a contended pool denies the truck who arrives once it is
    exhausted, and a repayment by one truck frees capacity that the other
    can then borrow, all determined by stream order."""
    cfg = (
        "TRUCK a 1000 100000 0\nTRUCK b 1000 100000 0\n"
        "QUARRY g 5 100 0 4\nASSIGN a g\nASSIGN b g\n"
    )
    # t0 a use 6 -> quarry over throttle (window tick 0) SURGE_START.
    # t1 b use 3 -> surge expired, room 0 -> borrow 3 (b's debt, reserve_used 3).
    # t1 a use 2 -> shortfall 2 > free 1 -> DENY RESERVE_EMPTY.
    # t2 b credit 3 -> repay 3 (pool free). t3 a use 2 -> borrow 2.
    ev = "0 HAUL a 6\n1 HAUL b 3\n1 HAUL a 2\n2 RETURN b 3\n3 HAUL a 2\n"
    assert ledger(cfg, ev) == [
        "0 PERMITTED",
        "0 SURGE_START QUARRY g",
        "1 PERMITTED",
        "1 DRAW b 3",
        "1 DENY RESERVE_EMPTY",
        "2 REPAY b 3",
        "3 PERMITTED",
        "3 DRAW a 2",
    ]


def test_lifo_unwind_across_interleaved_borrows_and_credit():
    """Interleaving borrows of different sizes and then crediting exactly one
    borrow's worth pops only the newest borrow off the debt stack, leaving the
    older ones intact (a later credit then unwinds those oldest-last)."""
    cfg = "TRUCK a 1000 100000 0\nQUARRY g 5 100 0 30\nASSIGN a g\n"
    # t0 use 6 SURGE_START (grant 6, over throttle). debt [].
    # t1 borrow 4, t2 borrow 7, t3 borrow 2 -> debt [4, 7, 2], reserve_used 13.
    # t4 credit 2 -> repays exactly the newest borrow (2) -> debt [4, 7].
    # t5 credit 7 -> repays the 7 -> debt [4].
    # t6 credit 10 -> repays the 4 (debt empty), remaining 6 reduces traffic 6 -> 0.
    ev = (
        "0 HAUL a 6\n1 HAUL a 4\n2 HAUL a 7\n3 HAUL a 2\n"
        "4 RETURN a 2\n5 RETURN a 7\n6 RETURN a 10\n"
    )
    assert ledger(cfg, ev) == [
        "0 PERMITTED",
        "0 SURGE_START QUARRY g",
        "1 PERMITTED",
        "1 DRAW a 4",
        "2 PERMITTED",
        "2 DRAW a 7",
        "3 PERMITTED",
        "3 DRAW a 2",
        "4 REPAY a 2",
        "5 REPAY a 7",
        "6 REPAY a 4",
    ]


def test_credit_cancel_then_recross_grants_normally_not_denied():
    """A credit that drops a quarry back to or under the throttle threshold cancels
    its window; once the window is cancelled the allowance is no longer
    surge-expired, so a later traffic event that crosses the throttle threshold
    again is granted normally (opening a fresh window) instead of being held to
    the throttle ceiling or denied."""
    cfg = "TRUCK u 7 15 1\nQUARRY g 5 12 4\nASSIGN u g\n"
    # t3 use 6 -> quarry over throttle (window 3..7) SURGE_START.
    # t4 credit 3 -> quarry traffic 6 -> 3 (<= soft 5) -> window cancels (no output).
    # t8 use 5 -> quarry traffic 3 -> 8: under-throttle start means ceiling is cap,
    #   so all 5 granted normally and the crossing opens a fresh window. The
    #   quarry is NOT surge-expired here and is well under its cap (12).
    ev = "3 HAUL u 6\n4 RETURN u 3\n8 HAUL u 5\n"
    assert ledger(cfg, ev) == [
        "3 PERMITTED",
        "3 SURGE_START QUARRY g",
        "8 PERMITTED",
        "8 SURGE_START TRUCK u",
        "8 SURGE_START QUARRY g",
    ]


def test_multiuser_credit_cancel_then_recross_and_cap_after_window():
    """A longer multi-truck timeline that interleaves a quarry window
    cancelled by a credit, a later normal re-grant that reopens the window, pool
    exhaustion, and cap denials. The quarry traffic must be tracked exactly across
    all of this so that a traffic event the cancelled window would otherwise hold
    back is granted, and later denials cite the correct (truck vs quarry) cap
    reason."""
    cfg = (
        "QUARRY g0 5 12 4\nQUARRY g1 2 7 0\n"
        "TRUCK u0 7 15 1\nASSIGN u0 g0\nTRUCK u1 8 10 2\nASSIGN u1 g0\n"
    )
    ev = (
        "1 RETURN u1 6\n3 HAUL u0 6\n3 RETURN u1 3\n7 HAUL u1 2\n8 HAUL u0 5\n"
        "12 HAUL u0 2\n13 HAUL u0 7\n15 HAUL u0 7\n18 HAUL u1 6\n21 RETURN u1 6\n"
    )
    assert ledger(cfg, ev) == [
        "3 PERMITTED",
        "3 SURGE_START QUARRY g0",
        "7 PERMITTED",
        "8 PERMITTED",
        "8 SURGE_START TRUCK u0",
        "8 SURGE_START QUARRY g0",
        "12 DENY RESERVE_EMPTY",
        "13 DENY TRUCK_FULL",
        "15 DENY TRUCK_FULL",
        "18 DENY QUARRY_FULL",
    ]


def test_two_user_group_window_cancel_and_independent_recross():
    """Two trucks share a quarry whose window is opened by one truck's
    traffic and then cancelled when that truck credits back under the quarry
    throttle; a second truck crossing the quarry throttle afterwards opens a
    fresh window and is granted normally rather than treated as still over an
    expired window."""
    cfg = "TRUCK x 6 20 1\nTRUCK y 6 20 1\nQUARRY h 8 14 2 5\nASSIGN x h\nASSIGN y h\n"
    ev = "0 HAUL x 10\n1 HAUL y 4\n3 RETURN x 10\n4 HAUL y 6\n"
    assert ledger(cfg, ev) == [
        "0 PERMITTED",
        "0 SURGE_START TRUCK x",
        "0 SURGE_START QUARRY h",
        "1 PERMITTED",
        "4 PERMITTED",
        "4 SURGE_START TRUCK y",
        "4 SURGE_START QUARRY h",
    ]


def test_borrowed_unit_excluded_from_usage_on_later_use():
    """Borrowed hauls are parked in the reserve pool and never counted in traffic, so
    a later traffic event's cap check sees only the granted traffic; a traffic event
    that would appear to exceed the cap if borrowed hauls were counted is in fact
    allowed and borrows again."""
    cfg = "TRUCK u 1000 100000 0\nQUARRY g 5 10 0 20\nASSIGN u g\n"
    # t0 use 6 -> quarry traffic 6 (window tick 0) SURGE_START.
    # t1 use 4 -> surge expired, room 0 -> borrow 4 (parked; quarry traffic stays 6).
    # t2 use 3 -> quarry traffic 6 + 3 = 9 <= cap 10 (borrowed 4 NOT counted, or
    #   6 + 4 + 3 = 13 > 10 would wrongly deny) -> borrow 3.
    ev = "0 HAUL u 6\n1 HAUL u 4\n2 HAUL u 3\n"
    assert ledger(cfg, ev) == [
        "0 PERMITTED",
        "0 SURGE_START QUARRY g",
        "1 PERMITTED",
        "1 DRAW u 4",
        "2 PERMITTED",
        "2 DRAW u 3",
    ]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "cfg,ev",
    [
        ("TRUCK a 10 5 3\nQUARRY g 100 200 3\nASSIGN a g\n", "0 HAUL a 1\n"),
        ("TRUCK a 10 20 3\nQUARRY g 100 200 3\nASSIGN a g\n", "0 HAUL zz 1\n"),
        ("TRUCK a 10 20 3\nQUARRY g 100 200 3\n", "0 HAUL a 1\n"),
        ("TRUCK a 10 20 3\nQUARRY g 100 200 3\nASSIGN a g\n", "0 HAUL a 0\n"),
        ("TRUCK a 10 20 3\nQUARRY g 100 200 3\nASSIGN a g\n", "0 HAUL a\n"),
        ("TRUCK a -1 20 3\nQUARRY g 100 200 3\nASSIGN a g\n", "0 HAUL a 1\n"),
        ("TRUCK a 10 20 3\nQUARRY g 100 200 3 -5\nASSIGN a g\n", "0 HAUL a 1\n"),
        ("BOGUS a 10 20 3\n", "0 HAUL a 1\n"),
    ],
)
def test_invalid_inputs_exit_nonzero_with_no_stdout(cfg, ev):
    """Structurally invalid inputs (including a negative reserve pool) cause a
    nonzero exit and no ledger on standard output."""
    rc, out, err = run(cfg, ev)
    assert rc != 0, f"expected nonzero exit; out={out!r}"
    assert out == "", f"expected no stdout on error; got {out!r}"


# ---------------------------------------------------------------------------
# Randomized differential cross-check against the independent reference
# ---------------------------------------------------------------------------
def _random_scenario(rng):
    ngroups = rng.randint(1, 2)
    nusers = rng.randint(1, 3)
    groups = ["g%d" % i for i in range(ngroups)]
    users = ["u%d" % i for i in range(nusers)]
    cfg = []
    for g in groups:
        soft = rng.randint(0, 8)
        hard = soft + rng.randint(0, 10)
        grace = rng.randint(0, 4)
        reserve = rng.randint(0, 8)
        if rng.random() < 0.5:
            cfg.append("QUARRY %s %d %d %d %d" % (g, soft, hard, grace, reserve))
        else:
            cfg.append("QUARRY %s %d %d %d" % (g, soft, hard, grace))
    for u in users:
        soft = rng.randint(0, 8)
        cfg.append(
            "TRUCK %s %d %d %d" % (u, soft, soft + rng.randint(0, 10), rng.randint(0, 4))
        )
        cfg.append("ASSIGN %s %s" % (u, rng.choice(groups)))
    cfg_text = "\n".join(cfg) + "\n"
    nevents = rng.randint(1, 16)
    tick = 0
    evs = []
    for _ in range(nevents):
        tick += rng.randint(0, 4)
        kind = rng.choice(["HAUL", "HAUL", "RETURN"])
        evs.append("%d %s %s %d" % (tick, kind, rng.choice(users), rng.randint(1, 7)))
    return cfg_text, "\n".join(evs) + "\n"


def _build_differential_cases():
    """Draw the fixed differential corpus once, in order, from a single seed so
    every case is stable across runs and can be exercised individually."""
    rng = random.Random(20260624)
    return [_random_scenario(rng) for _ in range(800)]


_DIFFERENTIAL_CASES = _build_differential_cases()


@pytest.mark.parametrize(
    "cfg_text,ev_text",
    _DIFFERENTIAL_CASES,
    ids=[f"seed{i}" for i in range(len(_DIFFERENTIAL_CASES))],
)
def test_differential_against_reference(cfg_text, ev_text):
    """One randomized scenario at a time: report.py's ledger must match an
    independent reference reducer line for line, exercising the surge lifecycle,
    the truck/quarry conjunction, reserve-pool borrowing, the LIFO refund-
    unwind, and the canonical output ordering together."""
    expected = reference_ledger(cfg_text, ev_text)
    rc, out, err = run(cfg_text, ev_text)
    assert rc == 0, (
        f"nonzero exit on valid scenario; stderr={err!r}\n"
        f"cfg={cfg_text!r}\nev={ev_text!r}"
    )
    assert out.splitlines() == expected, (
        f"ledger mismatch\ncfg={cfg_text!r}\nev={ev_text!r}\n"
        f"got={out.splitlines()!r}\nwant={expected!r}"
    )
