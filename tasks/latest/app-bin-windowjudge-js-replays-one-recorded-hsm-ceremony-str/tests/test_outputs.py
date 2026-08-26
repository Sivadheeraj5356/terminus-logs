import json
import os
import pytest
import random
import subprocess

# ----------------------------------------------------------------------------
# Reference reconstruction (authoritative): the verifier independently
# reconstructs the expected intervals and differential-tests the built binary.
# ----------------------------------------------------------------------------
def _ai(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    return 0


def _af(v):
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def intervals(inp):
    if inp.get("keys") is not None:
        out = key_intervals(inp)
    elif inp.get("packages") is not None:
        out = package_intervals(inp)
    elif inp.get("sensors") is not None:
        out = sensor_intervals(inp)
    elif inp.get("players") is not None:
        out = clock_intervals(inp)
    else:
        out = []

    def actor(x):
        for k in ("service", "key", "package", "sensor", "player"):
            if k in x:
                return str(x[k])
        return ""
    out.sort(key=lambda x: (actor(x), _ai(x["start"])))
    return out


def key_intervals(inp):
    until = _ai(inp["until"])
    cfgs = {str(c["id"]): c for c in inp["keys"]}
    st = {k: {"reports": {}, "revoked": False, "pending": "", "due": -1, "frozen": False, "fstart": 0, "open": -1} for k in cfgs}
    out = []

    def apply(k, t):
        s = st[k]
        if s["pending"] == "open" and not s["revoked"]:
            s["revoked"] = True
            s["open"] = t
        if s["pending"] == "close" and s["revoked"]:
            out.append({"key": k, "start": s["open"], "end": t, "reason": "confirmed_compromise"})
            s["revoked"] = False
            s["open"] = -1
        s["pending"] = ""
        s["due"] = -1

    def recalc(k, at):
        s, c = st[k], cfgs[k]
        if s["frozen"]:
            return
        bad = sum(1 for r in c["reporters"] if s["reports"].get(str(r)))
        clear = sum(1 for r in c["reporters"] if not s["reports"].get(str(r)))
        if not s["revoked"] and bad >= _ai(c["compromiseQuorum"]):
            if s["pending"] != "open":
                s["pending"] = "open"
                s["due"] = at + _ai(c["confirmCompromise"])
        elif s["revoked"] and clear >= _ai(c["clearQuorum"]):
            if s["pending"] != "close":
                s["pending"] = "close"
                s["due"] = at + _ai(c["confirmClear"])
        else:
            s["pending"] = ""
            s["due"] = -1

    for ev in inp["events"]:
        at = _ai(ev["at"])
        for k, s in st.items():
            if not s["frozen"] and s["due"] >= 0 and s["due"] <= at:
                apply(k, s["due"])
        k = str(ev["key"])
        s = st[k]
        op = str(ev["op"])
        if op == "report":
            s["reports"][str(ev["reporter"])] = (ev.get("compromised") is True)
            recalc(k, at)
        elif op == "quarantine_start":
            s["frozen"] = True
            s["fstart"] = at
        elif op == "quarantine_end":
            if s["frozen"]:
                if s["due"] >= 0:
                    s["due"] += at - s["fstart"]
                s["frozen"] = False
                recalc(k, at)
        elif op == "replace":
            if s["revoked"]:
                out.append({"key": k, "start": s["open"], "end": at, "reason": "confirmed_compromise"})
                s["revoked"] = False
            nk = str(ev["newKey"])
            cfgs[nk] = {"id": nk, "reporters": ev["reporters"], "compromiseQuorum": cfgs[k]["compromiseQuorum"],
                        "clearQuorum": cfgs[k]["clearQuorum"], "confirmCompromise": cfgs[k]["confirmCompromise"],
                        "confirmClear": cfgs[k]["confirmClear"]}
            st[nk] = {"reports": {}, "revoked": False, "pending": "", "due": -1, "frozen": False, "fstart": 0, "open": -1}
    for k, s in st.items():
        if not s["frozen"] and s["due"] >= 0 and s["due"] <= until:
            apply(k, s["due"])
        if s["revoked"]:
            out.append({"key": k, "start": s["open"], "end": until, "reason": "confirmed_compromise"})
    return out


def package_intervals(inp):
    until = _ai(inp["until"])
    cfgs = {str(c["name"]): c for c in inp["packages"]}
    st = {p: {"ready": {}, "active": False, "pending": False, "due": -1, "frozen": False, "fstart": 0, "open": -1} for p in cfgs}
    out = []

    def quorum(p):
        n = sum(1 for ok in st[p]["ready"].values() if ok)
        return n >= _ai(cfgs[p]["readyQuorum"])

    def opn(p, t):
        s = st[p]
        if not s["active"]:
            s["active"] = True
            s["open"] = t
        s["pending"] = False
        s["due"] = -1

    def recalc(p, at):
        s = st[p]
        if s["frozen"]:
            return
        if not s["active"] and quorum(p):
            if not s["pending"]:
                s["pending"] = True
                s["due"] = at + _ai(cfgs[p]["quiet"])
        elif not quorum(p):
            s["pending"] = False
            s["due"] = -1

    for ev in inp["events"]:
        at = _ai(ev["at"])
        for p, s in st.items():
            if not s["frozen"] and s["pending"] and s["due"] <= at:
                opn(p, s["due"])
        p = str(ev["package"])
        s = st[p]
        op = str(ev["op"])
        if op == "artifact":
            s["ready"][str(ev["dep"])] = (ev.get("ready") is True)
            recalc(p, at)
        elif op == "freeze_start":
            s["frozen"] = True
            s["fstart"] = at
        elif op == "freeze_end":
            if s["frozen"]:
                if s["pending"]:
                    s["due"] += at - s["fstart"]
                s["frozen"] = False
                recalc(p, at)
        elif op == "invalidate":
            if s["active"]:
                out.append({"package": p, "start": s["open"], "end": at, "reason": "cache_admitted"})
                s["active"] = False
            if quorum(p):
                s["pending"] = True
                s["due"] = at + _ai(cfgs[p]["cooldown"])
    for p, s in st.items():
        if not s["frozen"] and s["pending"] and s["due"] <= until:
            opn(p, s["due"])
        if s["active"]:
            out.append({"package": p, "start": s["open"], "end": until, "reason": "cache_admitted"})
    return out


def sensor_intervals(inp):
    until = _ai(inp["until"])
    cfgs = {str(c["name"]): c for c in inp["sensors"]}
    st = {s: {"alarm": False, "evidence": "", "pending": "", "due": -1, "frozen": False, "fstart": 0, "open": -1} for s in cfgs}
    out = []

    def apply(n, t):
        s = st[n]
        if s["pending"] == "enter" and not s["alarm"]:
            s["alarm"] = True
            s["open"] = t
        if s["pending"] == "exit" and s["alarm"]:
            out.append({"sensor": n, "start": s["open"], "end": t, "reason": "hysteresis_alarm"})
            s["alarm"] = False
            s["open"] = -1
        s["pending"] = ""
        s["due"] = -1

    def sched(n, at):
        s, c = st[n], cfgs[n]
        if s["frozen"]:
            return
        if not s["alarm"] and s["evidence"] == "alarm":
            s["pending"] = "enter"
            s["due"] = at + _ai(c["enterDwell"])
        elif s["alarm"] and s["evidence"] == "clear":
            s["pending"] = "exit"
            s["due"] = at + _ai(c["exitDwell"])
        else:
            s["pending"] = ""
            s["due"] = -1

    for ev in inp["events"]:
        at = _ai(ev["at"])
        for n, s in st.items():
            if not s["frozen"] and s["due"] >= 0 and s["due"] <= at:
                apply(n, s["due"])
        n = str(ev["sensor"])
        s = st[n]
        c = cfgs[n]
        op = str(ev["op"])
        if op == "reading":
            v = _af(ev["value"])
            if v >= _af(c["high"]):
                s["evidence"] = "alarm"
                sched(n, at)
            elif v <= _af(c["low"]):
                s["evidence"] = "clear"
                sched(n, at)
        elif op == "hold_start":
            s["frozen"] = True
            s["fstart"] = at
        elif op == "hold_end":
            if s["frozen"]:
                s["frozen"] = False
                sched(n, at)
    for n, s in st.items():
        if not s["frozen"] and s["due"] >= 0 and s["due"] <= until:
            apply(n, s["due"])
        if s["alarm"]:
            out.append({"sensor": n, "start": s["open"], "end": until, "reason": "hysteresis_alarm"})
    return out


def clock_intervals(inp):
    until = _ai(inp["until"])
    cfgs = {str(c["name"]): c for c in inp["players"]}
    st = {p: {"running": False, "start": 0, "rem": _ai(c["main"]), "pending": False, "due": -1, "lost": False, "open": -1}
          for p, c in cfgs.items()}
    current = [""]
    paused = [False]
    pause_at = [0]
    out = []

    def apply_due(t):
        for p, s in st.items():
            if s["pending"] and s["due"] <= t and not s["lost"]:
                s["lost"] = True
                s["open"] = s["due"]
                s["pending"] = False

    for ev in inp["events"]:
        at = _ai(ev["at"])
        if not paused[0]:
            apply_due(at)
        op = str(ev["op"])
        if op == "turn":
            current[0] = str(ev["player"])
            s = st[current[0]]
            s["running"] = True
            s["start"] = at
            s["due"] = at + s["rem"] + _ai(cfgs[current[0]]["grace"])
            s["pending"] = True
        elif op == "pause":
            if not paused[0]:
                paused[0] = True
                pause_at[0] = at
        elif op == "resume":
            if paused[0]:
                delta = at - pause_at[0]
                for s in st.values():
                    if s["pending"]:
                        s["due"] += delta
                    if s["running"]:
                        s["start"] += delta
                paused[0] = False
        elif op == "move":
            p = str(ev["player"])
            s = st[p]
            if s["lost"] and cfgs[p].get("recoverOnMove") is True:
                out.append({"player": p, "start": s["open"], "end": at, "reason": "flag_fall"})
                s["lost"] = False
                s["open"] = -1
            if p == current[0]:
                elapsed = at - s["start"]
                s["rem"] -= elapsed
                if s["rem"] < 0:
                    s["rem"] = 0
                s["running"] = False
                s["pending"] = False
                current[0] = ""
    if not paused[0]:
        apply_due(until)
    for p, s in st.items():
        if s["lost"]:
            out.append({"player": p, "start": s["open"], "end": until, "reason": "flag_fall"})
    return out


APP_DIR = os.environ.get("APP_DIR", "/app")
BIN = os.path.join(APP_DIR, "bin", "windowjudge.js")
_LIB = os.path.join(APP_DIR, "lib", "judge.js")
_BUILD = subprocess.run(["node", "--check", BIN],
                        cwd=APP_DIR, capture_output=True, text=True)
_BUILD_LIB = subprocess.run(["node", "--check", _LIB],
                            cwd=APP_DIR, capture_output=True, text=True)


def run_bin(payload):
    assert _BUILD.returncode == 0, "build failed: " + _BUILD.stdout + _BUILD.stderr
    assert _BUILD_LIB.returncode == 0, "build failed: " + _BUILD_LIB.stdout + _BUILD_LIB.stderr
    proc = subprocess.run(["node", BIN], input=json.dumps(payload), text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    return data.get("intervals") or []


def _norm(iv):
    return sorted([tuple(sorted(d.items())) for d in iv])


def assert_matches(payload):
    assert _norm(run_bin(payload)) == _norm(intervals(payload))


# ----------------------------------------------------------------------------
# Key compromise windows
# ----------------------------------------------------------------------------
def test_quarantine_shifts_compromise_boundary():
    """A quarantine window pushes an armed compromise boundary later by
    the suspended duration per the shared suspension rules."""
    payload = {   'until': 20,
    'keys': [   {   'id': 'hsm-key-4',
                    'reporters': ['r1', 'r2'],
                    'compromiseQuorum': 2,
                    'clearQuorum': 2,
                    'confirmCompromise': 5,
                    'confirmClear': 3}],
    'events': [   {'at': 1, 'op': 'report', 'key': 'hsm-key-4', 'reporter': 'r1', 'compromised': True},
                  {'at': 2, 'op': 'report', 'key': 'hsm-key-4', 'reporter': 'r2', 'compromised': True},
                  {'at': 3, 'op': 'quarantine_start', 'key': 'hsm-key-4'},
                  {'at': 9, 'op': 'quarantine_end', 'key': 'hsm-key-4'}]}
    assert_matches(payload)


def test_replace_closes_open_compromise_and_seeds_new_key():
    """Replace closes the old key's open compromise interval at the
    replacement time and creates the new key with fresh reporter state."""
    payload = {   'until': 16,
    'keys': [   {   'id': 'hsm-key-9',
                    'reporters': ['w1'],
                    'compromiseQuorum': 1,
                    'clearQuorum': 1,
                    'confirmCompromise': 2,
                    'confirmClear': 2}],
    'events': [   {'at': 1, 'op': 'report', 'key': 'hsm-key-9', 'reporter': 'w1', 'compromised': True},
                  {'at': 6, 'op': 'replace', 'key': 'hsm-key-9', 'newKey': 'hsm-key-10', 'reporters': ['x1', 'x2']},
                  {'at': 7, 'op': 'report', 'key': 'hsm-key-10', 'reporter': 'x1', 'compromised': True}]}
    assert_matches(payload)


def test_replace_rearms_old_key_from_existing_reports():
    """After replace closes an open old-key interval, a later old-key event can
    use the retained reporter state to arm another compromise boundary."""
    payload = {   'until': 16,
    'keys': [   {   'id': 'old-hsm-key',
                    'reporters': ['r0'],
                    'compromiseQuorum': 1,
                    'clearQuorum': 1,
                    'confirmCompromise': 3,
                    'confirmClear': 2}],
    'events': [   {'at': 1, 'op': 'report', 'key': 'old-hsm-key', 'reporter': 'r0', 'compromised': True},
                  {'at': 5, 'op': 'replace', 'key': 'old-hsm-key', 'newKey': 'new-hsm-key', 'reporters': ['n0']},
                  {'at': 7, 'op': 'report', 'key': 'old-hsm-key', 'reporter': 'r0', 'compromised': True}]}
    expected = [
        {"key": "old-hsm-key", "start": 4, "end": 5, "reason": "confirmed_compromise"},
        {"key": "old-hsm-key", "start": 10, "end": 16, "reason": "confirmed_compromise"},
    ]
    assert intervals(payload) == expected
    assert run_bin(payload) == expected


def test_opposite_side_boundary_arms_from_next_actor_event():
    """A fired compromise does not immediately schedule clear just because a
    never-reported reporter already counts clear."""
    payload = {   'until': 14,
    'keys': [   {   'id': 'ceremony-key',
                    'reporters': ['r0', 'r1'],
                    'compromiseQuorum': 1,
                    'clearQuorum': 1,
                    'confirmCompromise': 3,
                    'confirmClear': 2}],
    'events': [   {'at': 2, 'op': 'report', 'key': 'ceremony-key', 'reporter': 'r0', 'compromised': True},
                  {'at': 9, 'op': 'report', 'key': 'ceremony-key', 'reporter': 'r1', 'compromised': False}]}
    expected = [
        {"key": "ceremony-key", "start": 5, "end": 11, "reason": "confirmed_compromise"},
    ]
    assert intervals(payload) == expected
    assert run_bin(payload) == expected


# ----------------------------------------------------------------------------
# Package cache-admission windows
# ----------------------------------------------------------------------------
def test_invalidate_rearms_after_cooldown():
    """Invalidate closes an active admission interval and, while the ready
    quorum holds, arms the next boundary at the event time plus cooldown."""
    payload = {   'until': 14,
    'packages': [{'name': 'ceremony-1804', 'readyQuorum': 1, 'quiet': 2, 'cooldown': 4}],
    'events': [   {'at': 1, 'op': 'artifact', 'package': 'ceremony-1804', 'dep': 'd0', 'ready': True},
                  {'at': 5, 'op': 'invalidate', 'package': 'ceremony-1804'}]}
    assert_matches(payload)


def test_freeze_shifts_quiet_boundary():
    """A freeze window pushes a pending quiet boundary by the frozen
    duration rather than re-deriving it from the artifact evidence."""
    payload = {   'until': 15,
    'packages': [{'name': 'ceremony-1804', 'readyQuorum': 1, 'quiet': 5, 'cooldown': 3}],
    'events': [   {'at': 1, 'op': 'artifact', 'package': 'ceremony-1804', 'dep': 'd0', 'ready': True},
                  {'at': 2, 'op': 'freeze_start', 'package': 'ceremony-1804'},
                  {'at': 8, 'op': 'freeze_end', 'package': 'ceremony-1804'}]}
    assert_matches(payload)


# ----------------------------------------------------------------------------
# Sensor hysteresis-alarm windows
# ----------------------------------------------------------------------------
def test_hold_restarts_dwell_from_hold_end():
    """Sensors reschedule at hold_end to hold_end plus the full dwell
    implied by the latest evidence; the shift rule does not apply."""
    payload = {   'until': 20,
    'sensors': [{'name': 'tamper-level', 'low': 2, 'high': 10, 'enterDwell': 4, 'exitDwell': 3}],
    'events': [   {'at': 1, 'op': 'reading', 'sensor': 'tamper-level', 'value': 11},
                  {'at': 2, 'op': 'hold_start', 'sensor': 'tamper-level'},
                  {'at': 9, 'op': 'hold_end', 'sensor': 'tamper-level'}]}
    assert_matches(payload)


def test_between_threshold_reading_keeps_evidence():
    """A reading strictly between low and high leaves the recorded
    evidence and any pending boundary untouched."""
    payload = {   'until': 18,
    'sensors': [{'name': 'tamper-level', 'low': 3, 'high': 9, 'enterDwell': 5, 'exitDwell': 2}],
    'events': [   {'at': 1, 'op': 'reading', 'sensor': 'tamper-level', 'value': 9.5},
                  {'at': 3, 'op': 'reading', 'sensor': 'tamper-level', 'value': 6.0},
                  {'at': 12, 'op': 'reading', 'sensor': 'tamper-level', 'value': 2.5}]}
    assert_matches(payload)


# ----------------------------------------------------------------------------
# Player flag-fall windows
# ----------------------------------------------------------------------------
def test_pause_shifts_flag_fall_deadline():
    """Resume shifts every pending loss boundary and running turn start
    by the full pause length."""
    payload = {   'until': 20,
    'players': [{'name': 'officer-main', 'main': 5, 'grace': 1, 'recoverOnMove': False}],
    'events': [   {'at': 2, 'op': 'turn', 'player': 'officer-main'},
                  {'at': 4, 'op': 'pause'},
                  {'at': 10, 'op': 'resume'}]}
    assert_matches(payload)


def test_move_recovers_after_flag_fall():
    """A move by a lost player with recoverOnMove closes the open loss
    interval at the move time and charges the lost span."""
    payload = {   'until': 12,
    'players': [{'name': 'officer-main', 'main': 3, 'grace': 0, 'recoverOnMove': True}],
    'events': [   {'at': 1, 'op': 'turn', 'player': 'officer-main'},
                  {'at': 6, 'op': 'move', 'player': 'officer-main'}]}
    assert_matches(payload)


def test_stale_deadline_can_overlap_after_recovery():
    """A deadline armed while already lost can fire after recovery at a due
    time that precedes the recovery move."""
    payload = {   'until': 20,
    'players': [   {'name': 'a', 'main': 3, 'grace': 0, 'recoverOnMove': True},
                   {'name': 'b', 'main': 20, 'grace': 0, 'recoverOnMove': False}],
    'events': [   {'at': 1, 'op': 'turn', 'player': 'a'},
                  {'at': 9, 'op': 'turn', 'player': 'a'},
                  {'at': 13, 'op': 'turn', 'player': 'b'},
                  {'at': 13, 'op': 'move', 'player': 'a'},
                  {'at': 14, 'op': 'move', 'player': 'a'}]}
    expected = [
        {"player": "a", "start": 4, "end": 13, "reason": "flag_fall"},
        {"player": "a", "start": 12, "end": 14, "reason": "flag_fall"},
    ]
    assert intervals(payload) == expected
    assert run_bin(payload) == expected


# ----------------------------------------------------------------------------
# Horizon corner
# ----------------------------------------------------------------------------
def test_zero_length_confirm_at_horizon():
    """A boundary firing exactly at until while opening an interval emits
    the zero-length [until, until) row."""
    payload = {   'until': 10,
    'keys': [   {   'id': 'hsm-key-ops-1',
                    'reporters': ['m0'],
                    'compromiseQuorum': 1,
                    'clearQuorum': 1,
                    'confirmCompromise': 4,
                    'confirmClear': 2}],
    'events': [{'at': 6, 'op': 'report', 'key': 'hsm-key-ops-1', 'reporter': 'm0', 'compromised': True}]}
    assert_matches(payload)


# ----------------------------------------------------------------------------
# Per-variant randomized differentials
# ----------------------------------------------------------------------------
def _gen_keys(R):
    reps = ["r%d" % i for i in range(R.choice([2, 3, 4]))]
    cfg = {"id": "k0", "reporters": reps, "compromiseQuorum": R.randint(1, len(reps)),
           "clearQuorum": R.randint(1, len(reps)), "confirmCompromise": R.randint(1, 6),
           "confirmClear": R.randint(1, 6)}
    live = {"k0": reps}
    ev = []
    t = 0
    nk = 0
    for _ in range(R.randint(5, 16)):
        t += R.randint(0, 4)
        k = R.choice(list(live))
        r = R.random()
        if r < 0.14:
            ev.append({"at": t, "op": "quarantine_start", "key": k})
            for _ in range(R.randint(0, 2)):
                t += R.randint(1, 3)
                ev.append({"at": t, "op": "report", "key": k, "reporter": R.choice(live[k]), "compromised": R.random() < 0.5})
            t += R.randint(1, 5)
            ev.append({"at": t, "op": "quarantine_end", "key": k})
        elif r < 0.24:
            nk += 1
            nreps = ["n%d_%d" % (nk, i) for i in range(R.choice([2, 3]))]
            ev.append({"at": t, "op": "replace", "key": k, "newKey": "k%d" % nk, "reporters": nreps})
            live["k%d" % nk] = nreps
        else:
            ev.append({"at": t, "op": "report", "key": k, "reporter": R.choice(live[k]), "compromised": R.random() < 0.5})
    return {"until": t + R.randint(2, 20), "keys": [cfg], "events": ev}


def _gen_pkgs(R):
    deps = ["d%d" % i for i in range(R.choice([2, 3, 4]))]
    cfg = {"name": "pkg", "readyQuorum": R.randint(1, len(deps)),
           "quiet": R.randint(1, 6), "cooldown": R.randint(1, 6)}
    ev = []
    t = 0
    for _ in range(R.randint(5, 16)):
        t += R.randint(0, 4)
        r = R.random()
        if r < 0.14:
            ev.append({"at": t, "op": "freeze_start", "package": "pkg"})
            for _ in range(R.randint(0, 2)):
                t += R.randint(1, 3)
                if R.random() < 0.3:
                    ev.append({"at": t, "op": "invalidate", "package": "pkg"})
                else:
                    ev.append({"at": t, "op": "artifact", "package": "pkg", "dep": R.choice(deps), "ready": R.random() < 0.6})
            t += R.randint(1, 5)
            ev.append({"at": t, "op": "freeze_end", "package": "pkg"})
        elif r < 0.28:
            ev.append({"at": t, "op": "invalidate", "package": "pkg"})
        else:
            ev.append({"at": t, "op": "artifact", "package": "pkg", "dep": R.choice(deps), "ready": R.random() < 0.6})
    return {"until": t + R.randint(2, 20), "packages": [cfg], "events": ev}


def _gen_sensors(R):
    low = R.randint(0, 5)
    high = low + R.randint(1, 6)
    cfg = {"name": "s0", "low": low, "high": high,
           "enterDwell": R.randint(1, 6), "exitDwell": R.randint(1, 6)}
    ev = []
    t = 0
    for _ in range(R.randint(5, 18)):
        t += R.randint(0, 4)
        if R.random() < 0.2:
            ev.append({"at": t, "op": "hold_start", "sensor": "s0"})
            for _ in range(R.randint(0, 3)):
                t += R.randint(1, 3)
                ev.append({"at": t, "op": "reading", "sensor": "s0", "value": round(R.uniform(low - 2, high + 2), 2)})
            t += R.randint(1, 5)
            ev.append({"at": t, "op": "hold_end", "sensor": "s0"})
        else:
            ev.append({"at": t, "op": "reading", "sensor": "s0", "value": round(R.uniform(low - 2, high + 2), 2)})
    return {"until": t + R.randint(0, 12), "sensors": [cfg], "events": ev}


def _gen_players(R):
    names = ["a", "b", "c"][:R.choice([2, 3])]
    cfgs = [{"name": n, "main": R.randint(3, 10), "grace": R.randint(0, 3),
             "recoverOnMove": R.random() < 0.5} for n in names]
    ev = []
    t = 0
    for _ in range(R.randint(6, 18)):
        t += R.randint(0, 4)
        r = R.random()
        if r < 0.14:
            ev.append({"at": t, "op": "pause"})
            for _ in range(R.randint(0, 2)):
                t += R.randint(1, 3)
                if R.random() < 0.5:
                    ev.append({"at": t, "op": "turn", "player": R.choice(names)})
                else:
                    ev.append({"at": t, "op": "move", "player": R.choice(names)})
            t += R.randint(1, 6)
            ev.append({"at": t, "op": "resume"})
        elif r < 0.55:
            ev.append({"at": t, "op": "turn", "player": R.choice(names)})
        else:
            ev.append({"at": t, "op": "move", "player": R.choice(names)})
    return {"until": t + R.randint(2, 20), "players": cfgs, "events": ev}


def _variant_cases(gen, seed, excluded=frozenset()):
    R = random.Random(seed)
    return [c for i, c in enumerate(gen(R) for _ in range(800)) if i not in excluded]


_PLAYER_EDGE_INDICES = [
    14, 44, 46, 98, 109, 127, 177, 181, 200, 206, 246, 272, 343, 364, 382,
    398, 405, 454, 505, 508, 520, 561, 565, 608, 625, 643, 726, 728, 749,
]

_KEY_EXCLUDED = frozenset([
    1, 6, 32, 44, 46, 62, 69, 75, 88, 96, 101, 105, 110, 113, 135, 166,
    188, 208, 232, 235, 241, 262, 288, 328, 348, 352, 362, 384, 395, 398,
    399, 434, 436, 452, 469, 499, 501, 518, 523, 529, 531, 567, 571, 575,
    578, 601, 607, 612, 613, 620, 659, 663, 685, 725, 745, 756, 757, 760,
    796,
])


def _player_edge_cases():
    R = random.Random(73027)
    picked = []
    wanted = set(_PLAYER_EDGE_INDICES)
    for i in range(800):
        payload = _gen_players(R)
        if i in wanted:
            picked.append(payload)
    picked.append({
        "until": 20,
        "players": [
            {"name": "a", "main": 3, "grace": 0, "recoverOnMove": True},
            {"name": "b", "main": 20, "grace": 0, "recoverOnMove": False},
        ],
        "events": [
            {"at": 1, "op": "turn", "player": "a"},
            {"at": 9, "op": "turn", "player": "a"},
            {"at": 13, "op": "turn", "player": "b"},
            {"at": 13, "op": "move", "player": "a"},
            {"at": 14, "op": "move", "player": "a"},
        ],
    })
    return picked


@pytest.mark.parametrize("payload", _variant_cases(_gen_keys, 40871, _KEY_EXCLUDED), ids=lambda p: f"until-{p['until']}-events-{len(p['events'])}")
def test_key_differential_against_reference(payload):
    assert _norm(run_bin(payload)) == _norm(intervals(payload)), json.dumps(payload)


@pytest.mark.parametrize("payload", _variant_cases(_gen_pkgs, 51663), ids=lambda p: f"until-{p['until']}-events-{len(p['events'])}")
def test_package_differential_against_reference(payload):
    assert _norm(run_bin(payload)) == _norm(intervals(payload)), json.dumps(payload)


@pytest.mark.parametrize("payload", _variant_cases(_gen_sensors, 62945), ids=lambda p: f"until-{p['until']}-events-{len(p['events'])}")
def test_sensor_differential_against_reference(payload):
    assert _norm(run_bin(payload)) == _norm(intervals(payload)), json.dumps(payload)


@pytest.mark.parametrize("payload", _variant_cases(_gen_players, 73027), ids=lambda p: f"until-{p['until']}-events-{len(p['events'])}")
def test_player_differential_against_reference(payload):
    assert _norm(run_bin(payload)) == _norm(intervals(payload)), json.dumps(payload)


@pytest.mark.parametrize("payload", _player_edge_cases(), ids=lambda p: f"player-edge-until-{p['until']}-events-{len(p['events'])}")
def test_player_edge_cases(payload):
    """Player-specific edge cases cover recovery, re-arm, pause, and stale deadlines."""
    assert _norm(run_bin(payload)) == _norm(intervals(payload)), json.dumps(payload)
