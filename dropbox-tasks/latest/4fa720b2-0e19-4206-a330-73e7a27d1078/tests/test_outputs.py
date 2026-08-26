"""Behavioral verifier for the cryostat boil-off warden.

Each test feeds a JSON event stream to the /app/cryoctl binary over stdin,
parses the JSON result, and asserts a single facet of the continuous-time
interval semantics. Every asserted contract is derivable from /app/docs/spec.md.

Ground truth was produced by an independent reference implementation of the
spec (active-time allowance accrual, purge-frozen boil-off clock, computed
boil-off-interval boundaries, zero-length suppression) and cross-checked against
a second implementation over differential fuzz cases. The tests are
discriminating: the naive starting build measures the allowance timer in wall
time, decides boil-off intervals only at explicit events, and omits zero-length
suppression, so it produces the wrong interval set or exposed total for the
boundary and purge-freeze cases below.
"""
import json
import subprocess

BINARY = "/app/cryoctl"


def run(grace, events):
    """Run the warden binary on an event stream and return the parsed JSON."""
    payload = json.dumps({"grace": grace, "events": events})
    proc = subprocess.run(
        [BINARY],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"binary exited {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout)


def boiloff(out):
    """Normalize boil-off intervals to a list of (cryostat, start, end) tuples."""
    return [(r["cryostat"], r["start"], r["end"]) for r in out["boiloff"]]


def exposed(out, cryostat):
    return out["cryostats"][cryostat]["exposed"]


def PH(cryostat, t):
    return {"type": "press_high", "cryostat": cryostat, "t": t}


def PL(cryostat, t):
    return {"type": "press_low", "cryostat": cryostat, "t": t}


def PON(cryostat, t):
    return {"type": "purge_on", "cryostat": cryostat, "t": t}


def POFF(cryostat, t):
    return {"type": "purge_off", "cryostat": cryostat, "t": t}


def RPT(cryostat, t):
    return {"type": "report", "cryostat": cryostat, "t": t}


# --------------------------------------------------------------------------
# Output shape
# --------------------------------------------------------------------------

def test_top_level_keys_exact():
    """The result is one object whose top-level keys are exactly audit, boiloff,
    and cryostats — no missing or extra fields."""
    out = run(30, [PH("a", 100), PON("a", 110), POFF("a", 160), PL("a", 200)])
    assert set(out.keys()) == {"audit", "boiloff", "cryostats"}


def test_nested_keys_exact():
    """Each nested object carries exactly the keys the spec pins — no missing or
    extra fields. Audit entries are {index, type, cryostat, t, status}; boil-off
    entries are {cryostat, start, end}; each cryostat value is {exposed}."""
    # An event stream that exercises every nested object shape at once: a boil-off
    # interval (populates boiloff), an accepted and a rejected audit entry, and a
    # cryostat value.
    out = run(30, [
        PH("a", 100),
        {"type": "frobnicate", "cryostat": "a", "t": 150},
        PL("a", 200),
    ])
    assert out["boiloff"], "expected at least one boil-off interval to check its schema"
    for entry in out["audit"]:
        assert set(entry.keys()) == {"index", "type", "cryostat", "t", "status"}
    for entry in out["boiloff"]:
        assert set(entry.keys()) == {"cryostat", "start", "end"}
    for value in out["cryostats"].values():
        assert set(value.keys()) == {"exposed"}


# --------------------------------------------------------------------------
# Headline behavior
# --------------------------------------------------------------------------

def test_basic_boiloff():
    """A plain at-risk stretch longer than the allowance produces one boil-off
    interval starting G active seconds after the press_high."""
    out = run(30, [PH("a", 100), PL("a", 200)])
    assert boiloff(out) == [("a", 130, 200)]
    assert exposed(out, "a") == 100


def test_short_stretch_no_boiloff():
    """An at-risk stretch shorter than the allowance yields no boil-off interval
    but still accrues active exposed time."""
    out = run(30, [PH("a", 100), PL("a", 120)])
    assert boiloff(out) == []
    assert exposed(out, "a") == 20


def test_report_closes_open_interval():
    """A cryostat still at risk at the report horizon has its boil-off interval
    closed at the report instant."""
    out = run(30, [PH("a", 100), RPT("a", 300)])
    assert boiloff(out) == [("a", 130, 300)]
    assert exposed(out, "a") == 200


def test_report_allowance_unmet_no_boiloff():
    """A cryostat whose at-risk time has not yet reached the allowance at the
    report horizon produces no boil-off interval."""
    out = run(30, [PH("a", 290), RPT("a", 300)])
    assert boiloff(out) == []
    assert exposed(out, "a") == 10


def test_two_separate_stretches_one_cryostat():
    """Two independent at-risk stretches on one cryostat yield two boil-off
    intervals, each measured from its own press_high event."""
    out = run(10, [PH("a", 0), PL("a", 30), PH("a", 100), PL("a", 140)])
    assert boiloff(out) == [("a", 10, 30), ("a", 110, 140)]
    assert exposed(out, "a") == 70


def test_two_cryostats_independent():
    """Each cryostat tracks its own state; a short at-risk stretch on one and a
    long one on the other are scored independently and sorted by name."""
    out = run(10, [PH("c1", 0), PH("c2", 5), PL("c2", 12), PL("c1", 40)])
    assert boiloff(out) == [("c1", 10, 40)]
    assert exposed(out, "c1") == 40
    assert exposed(out, "c2") == 7


# --------------------------------------------------------------------------
# Computed boundary strictly between events
# --------------------------------------------------------------------------

def test_interval_opens_between_events():
    """The boil-off start is the computed allowance-crossing instant even though no
    event lands there: press_high@100, press_low@155, G=30 -> interval [130,155]."""
    out = run(30, [PH("a", 100), PL("a", 155)])
    assert boiloff(out) == [("a", 130, 155)]
    assert exposed(out, "a") == 55


def test_allowance_zero_interval_from_press_high():
    """With allowance zero the boil-off interval begins at the press_high instant
    itself."""
    out = run(0, [PH("a", 100), PL("a", 200)])
    assert boiloff(out) == [("a", 100, 200)]
    assert exposed(out, "a") == 100


# --------------------------------------------------------------------------
# Zero-length suppression
# --------------------------------------------------------------------------

def test_zero_length_at_press_low_suppressed():
    """At risk for exactly G active seconds then settle at that instant: the
    interval start equals its end, so it is omitted."""
    out = run(30, [PH("a", 100), PL("a", 130)])
    assert boiloff(out) == []
    assert exposed(out, "a") == 30


def test_zero_length_at_report_suppressed():
    """Same zero-length suppression when the closing event is a report."""
    out = run(30, [PH("a", 100), RPT("a", 130)])
    assert boiloff(out) == []
    assert exposed(out, "a") == 30


def test_zero_length_at_allowance_zero_suppressed():
    """Allowance zero, press_high and press_low at the same instant: zero-length,
    omitted."""
    out = run(0, [PH("a", 100), PL("a", 100)])
    assert boiloff(out) == []
    assert exposed(out, "a") == 0


# --------------------------------------------------------------------------
# Transfer-line purge freeze: active time vs wall time
# --------------------------------------------------------------------------

def test_purge_freezes_allowance_timer():
    """A purge window inside an at-risk stretch freezes the allowance timer; the
    boil-off start shifts later in wall time by the frozen duration.
    press_high@100, purge[110,160], press_low@200, G=30 -> start at 180."""
    out = run(30, [PH("a", 100), PON("a", 110), POFF("a", 160), PL("a", 200)])
    assert boiloff(out) == [("a", 180, 200)]
    assert exposed(out, "a") == 50


def test_allowance_resumes_after_purge_not_restart():
    """The allowance timer resumes (does not restart) after a purge window:
    press_high@100, purge[120,150], press_low@200, G=30. 20 active seconds before
    the window, 10 after -> interval opens at 160."""
    out = run(30, [PH("a", 100), PON("a", 120), POFF("a", 150), PL("a", 200)])
    assert boiloff(out) == [("a", 160, 200)]
    assert exposed(out, "a") == 70


def test_purge_at_exact_boundary_instant_defers_open():
    """A purge that opens exactly when the allowance would be crossed freezes the
    boil-off clock before the interval fires; the interval opens after the window.
    press_high@100, purge[130,150], press_low@200, G=30 -> start at 150."""
    out = run(30, [PH("a", 100), PON("a", 130), POFF("a", 150), PL("a", 200)])
    assert boiloff(out) == [("a", 150, 200)]
    assert exposed(out, "a") == 80


def test_purge_covers_entire_allowance():
    """A purge window that opens at the press_high and runs long defers all
    allowance accrual until it closes. press_high@100, purge[100,500],
    press_low@600, G=30 -> start at 530."""
    out = run(30, [PH("a", 100), PON("a", 100), POFF("a", 500), PL("a", 600)])
    assert boiloff(out) == [("a", 530, 600)]
    assert exposed(out, "a") == 100


def test_press_high_inside_purge_window():
    """A cryostat that goes at risk while a purge window is already open accrues no
    allowance until the window closes. purge@50, press_high@80, purge_off@120,
    press_low@200, G=15 -> start at 135."""
    out = run(15, [PON("a", 50), PH("a", 80), POFF("a", 120), PL("a", 200)])
    assert boiloff(out) == [("a", 135, 200)]
    assert exposed(out, "a") == 80


def test_two_purges_split_allowance():
    """Two purge windows within one at-risk stretch each freeze the timer; the
    allowance is consumed in active time across both. press_high@100, purge[110,130],
    purge[200,220], press_low@400, G=30 -> 10 active before first window, then 20
    more active reaches G at wall 150 -> interval [150,400]."""
    out = run(30, [PH("a", 100), PON("a", 110), POFF("a", 130),
                   PON("a", 200), POFF("a", 220), PL("a", 400)])
    assert boiloff(out) == [("a", 150, 400)]
    assert exposed(out, "a") == 260


def test_zero_length_after_purge_resume():
    """Allowance satisfied exactly at the closing press_low instant after a purge
    window is still zero-length and suppressed. press_high@100, purge[120,150],
    press_low@160, G=30 -> 20 active before, 10 after reaches G at 160 == press_low
    -> omit."""
    out = run(30, [PH("a", 100), PON("a", 120), POFF("a", 150), PL("a", 160)])
    assert boiloff(out) == []
    assert exposed(out, "a") == 30


def test_purge_while_settled_does_not_count():
    """A purge window opened while the cryostat is settled freezes allowance time
    for the at-risk stretch that follows until the window closes. purge@50,
    press_high@100, purge_off@110, press_low@200, G=20 -> exposed starts accruing at
    110, interval [130,200]."""
    out = run(20, [PON("a", 50), PH("a", 100), POFF("a", 110), PL("a", 200)])
    assert boiloff(out) == [("a", 130, 200)]
    assert exposed(out, "a") == 90


def test_nested_purge_on_does_not_stack():
    """A purge window is a single open/closed state, not a nesting counter: a second
    purge_on while a window is already open has no effect, and the single purge_off
    closes the window. press_high@100, purge_on@110, purge_on@120 (redundant),
    purge_off@150, press_low@200, G=30 -> the window spans [110,150] regardless of
    the redundant purge_on (10 active before, 50 after), so the interval opens 20
    active seconds past resume at 170 -> interval [170,200], exposed 60."""
    out = run(30, [PH("a", 100), PON("a", 110), PON("a", 120),
                   POFF("a", 150), PL("a", 200)])
    assert boiloff(out) == [("a", 170, 200)]
    assert exposed(out, "a") == 60


def test_redundant_purge_off_while_clear_ignored():
    """A purge_off while no window is open has no effect — the purge state does not
    go 'negative' and a later real purge still works normally. press_high@100,
    purge_off@110 (redundant, nothing to close), press_low@200, G=30 -> a plain
    at-risk stretch with no active purge, interval [130,200], exposed 100."""
    out = run(30, [PH("a", 100), POFF("a", 110), PL("a", 200)])
    assert boiloff(out) == [("a", 130, 200)]
    assert exposed(out, "a") == 100


# --------------------------------------------------------------------------
# Robustness / audit
# --------------------------------------------------------------------------

def test_unknown_event_rejected_but_continues():
    """An unrecognized event type is rejected, has no effect, and does not halt
    the run."""
    events = [PH("a", 0), {"type": "frobnicate", "cryostat": "a", "t": 5}, PL("a", 30)]
    out = run(10, events)
    statuses = [(e["index"], e["status"]) for e in out["audit"]]
    assert statuses == [(0, "accepted"), (1, "rejected"), (2, "accepted")]
    assert boiloff(out) == [("a", 10, 30)]
    assert exposed(out, "a") == 30


def test_redundant_press_high_ignored():
    """A second press_high while already at risk does not reset the at-risk
    stretch."""
    out = run(10, [PH("a", 0), PH("a", 5), PL("a", 30)])
    assert boiloff(out) == [("a", 10, 30)]
    assert exposed(out, "a") == 30


def test_redundant_press_low_ignored():
    """A press_low while already settled has no effect on later exposed
    accounting."""
    out = run(10, [PL("a", 0), PH("a", 10), PL("a", 40)])
    assert boiloff(out) == [("a", 20, 40)]
    assert exposed(out, "a") == 30


def test_audit_echoes_every_event_in_order():
    """The audit log has one entry per event, in order, echoing index/type/t."""
    events = [PH("a", 100), PON("a", 110), POFF("a", 160), PL("a", 200)]
    out = run(30, events)
    assert [e["index"] for e in out["audit"]] == [0, 1, 2, 3]
    assert [e["type"] for e in out["audit"]] == [
        "press_high", "purge_on", "purge_off", "press_low"
    ]
    assert all(e["status"] == "accepted" for e in out["audit"])
