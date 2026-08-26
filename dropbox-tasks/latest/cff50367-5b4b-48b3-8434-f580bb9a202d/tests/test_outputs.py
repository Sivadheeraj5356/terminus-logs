import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

APP = Path("/app")
ENV = APP / "environment"
OUT = APP / "output"
TRACE = OUT / "freshness-report.json"
FIXTURES = ENV / "fixtures"
LAYOUT = json.loads((ENV / "runtime" / "layout.json").read_text())
HEX64 = re.compile(r"[0-9a-f]{64}")

COMPANIONS = (
    "hold.json",
    "hold.replay.json",
    "hold.shadow.json",
    "hold.spill.json",
    "hold.retract.json",
)
RANK = {
    "hold.json": 0,
    "hold.replay.json": 1,
    "hold.shadow.json": 2,
    "hold.spill.json": 3,
    "hold.retract.json": 4,
}
SEED_RANK = -1
SCOPE_ORDER = ("cache", "tenant", "issuer")
CARRY_MARK = 0.5
PROFILES = ("amber", "beryl", "onyx")

# Verifier-owned inputs snapshotted before each mux run. Expected traces must
# be derived from the pre-run snapshot for that profile so a submitted binary
# cannot mutate journals or inflate the pre-run seal and have the oracle follow.
_PRE_RUN_SNAP = None
_PROFILE_SNAPS = {}


def _state_dir(profile):
    return OUT / "state" / profile


def _read_bytes(path):
    try:
        return Path(path).read_bytes()
    except OSError:
        return None


def _read_rows_bytes(raw):
    if raw is None:
        return []
    try:
        value = json.loads(raw.decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    return value if isinstance(value, list) else []


def _read_rows(path):
    return _read_rows_bytes(_read_bytes(path))


def _snapshot_verifier_owned():
    """Capture fixtures, layout, realms, companion journals, and pre-run seals."""
    files = {}
    for path in sorted(FIXTURES.rglob("*")):
        if path.is_file():
            files[str(path)] = path.read_bytes()
    for path in sorted((ENV / "realms").glob("*.toml")):
        files[str(path)] = path.read_bytes()
    layout_path = ENV / "runtime" / "layout.json"
    files[str(layout_path)] = layout_path.read_bytes()
    config_path = ENV / "runtime" / "config.toml"
    if config_path.is_file():
        files[str(config_path)] = config_path.read_bytes()
    for profile in PROFILES:
        state = _state_dir(profile)
        for name in COMPANIONS:
            path = state / name
            files[str(path)] = _read_bytes(path)
        files[str(state / "epoch.json")] = _read_bytes(state / "epoch.json")
    return files


def _assert_inputs_unchanged(before):
    """Companion journals, fixtures, layout, and realms must not change during mux.

    epoch.json is both an input (pre-run seal) and an output (reseal), so it is
    excluded from the post-run equality check. Expected accounting still uses the
    pre-run seal bytes from the snapshot.
    """
    after = _snapshot_verifier_owned()
    for key, value in before.items():
        if key.endswith("/epoch.json"):
            continue
        assert after.get(key) == value, f"verifier-owned input mutated: {key}"


def _profile_runs(profile, snap=None):
    import tomllib

    path = ENV / "realms" / f"{profile}.toml"
    if snap is not None:
        raw = snap.get(str(path))
        if raw is None:
            return []
        data = tomllib.loads(raw.decode())
    else:
        data = tomllib.loads(path.read_text())
    return list(data["runs"])


def _parse_line(line, scope, origin, seq, layout, run_id):
    row = {
        "seq": seq,
        "value": "",
        "epoch": layout["seed_epoch"],
        "generation": layout["seed_generation"],
        "mark": layout["seed_mark"],
        "phase": "apply",
        "run_id": run_id,
        "scope": scope,
        "origin": origin,
    }
    if line.endswith("!"):
        row["op"] = "delete"
        row["key"] = line[:-1].strip()
        return row
    if "+=" in line:
        idx = line.index("+=")
        row["op"] = "append"
        row["key"] = line[:idx].strip()
        row["value"] = line[idx + 2:].strip()
        return row
    if "-=" in line:
        idx = line.index("-=")
        row["op"] = "remove"
        row["key"] = line[:idx].strip()
        row["value"] = line[idx + 2:].strip()
        return row
    idx = line.index("=")
    row["op"] = "set"
    row["key"] = line[:idx].strip()
    row["value"] = line[idx + 1:].strip()
    return row


def _fixtures(profile, snap=None):
    layout = LAYOUT[profile]
    runs = _profile_runs(profile, snap=snap)
    run_id = runs[0] if runs else ""
    root = FIXTURES / f"{profile}_scopes"
    rows = []
    seq = 0
    for scope in SCOPE_ORDER:
        scope_dir = root / scope
        if not scope_dir.is_dir():
            continue
        for path in sorted(scope_dir.iterdir(), key=lambda p: p.name):
            if path.is_dir():
                continue
            if snap is not None:
                raw = snap.get(str(path))
                if raw is None:
                    continue
                text = raw.decode()
            else:
                text = path.read_text()
            for raw_line in text.split("\n"):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                seq += 1
                rows.append(_parse_line(line, scope, path.name, seq, layout, run_id))
    return rows


def _canonical_rows(profile, snap=None):
    chosen = {}
    counter = {"n": 0}

    def consider(rec, rank):
        owner = rec.get("profile")
        if owner not in (None, "", profile):
            counter["n"] += 1
            return
        key = (rec["seq"], rec["run_id"], rec["phase"], rec["key"], rec["op"])
        score = (rec["epoch"], rank, counter["n"])
        prior = chosen.get(key)
        if prior is None or score >= prior[0]:
            chosen[key] = (score, rec)
        counter["n"] += 1

    for rec in _fixtures(profile, snap=snap):
        consider(rec, SEED_RANK)
    for name in COMPANIONS:
        path = _state_dir(profile) / name
        if snap is not None:
            journal_rows = _read_rows_bytes(snap.get(str(path)))
        else:
            journal_rows = _read_rows(path)
        for rec in journal_rows:
            consider(rec, RANK[name])
    return sorted(
        (item[1] for item in chosen.values()),
        key=lambda r: (r["seq"], r["run_id"], r["phase"], r["key"], r.get("op", "")),
    )


def _generation_floor(profile):
    return LAYOUT[profile].get("generation_floor", 0)


def _active_rows(profile, rows=None):
    rows = _canonical_rows(profile) if rows is None else rows
    floor = _generation_floor(profile)
    return [r for r in rows if r.get("generation", 0) >= floor]


def _segments(rows, run_id, phase):
    return [r for r in rows if r["run_id"] == run_id and r["phase"] == phase]


def _mk(rec, value):
    return {
        "key": rec["key"],
        "value": value,
        "epoch": rec["epoch"],
        "generation": rec.get("generation", 0),
        "mark": rec.get("mark", 0.0),
        "scope": rec.get("scope", ""),
        "origin": rec.get("origin", ""),
    }


def _reconcile(records, base=None):
    rules = {k: dict(v) for k, v in (base or {}).items()}
    pending = {}
    ordered = sorted(records, key=lambda r: (r["seq"], r["key"]))
    for rec in ordered:
        for key, eff in list(pending.items()):
            if eff < rec["seq"]:
                rules.pop(key, None)
                del pending[key]
        op = rec["op"]
        if op in ("delete", "retract"):
            eff = rec.get("effective_seq", 0)
            if eff == 0:
                rules.pop(rec["key"], None)
            else:
                pending[rec["key"]] = eff
            continue
        prev = rules.get(rec["key"])
        if op == "set" or prev is None:
            rules[rec["key"]] = _mk(rec, rec["value"])
            continue
        parts = [p for p in prev["value"].split(",") if p]
        if op == "append":
            parts.append(rec["value"])
        elif op == "remove":
            parts = [p for p in parts if p != rec["value"]]
        else:
            rules[rec["key"]] = _mk(rec, rec["value"])
            continue
        rules[rec["key"]] = _mk(rec, ",".join(parts))
    return [rules[k] for k in sorted(rules)]


def _inherit(profile, snap=None):
    meta = LAYOUT.get(profile, {})
    parent = meta.get("inherits_from")
    shared = meta.get("shared_keys", [])
    if not parent or not shared:
        return {}
    parent_runs = _profile_runs(parent, snap=snap)
    if not parent_runs:
        return {}
    last = parent_runs[-1]
    settle = _phase_rules(_canonical_rows(parent, snap=snap), parent, last, "settle", snap=snap)
    return {r["key"]: r for r in settle if r["key"] in shared}


def _carry_base(rows, profile, run_id, snap=None):
    runs = _profile_runs(profile, snap=snap)
    if run_id not in runs or runs.index(run_id) == 0:
        return {}
    prev = runs[runs.index(run_id) - 1]
    prev_settle = _phase_rules(rows, profile, prev, "settle", snap=snap)
    return {r["key"]: r for r in prev_settle if r.get("mark", 0) >= CARRY_MARK}


def _phase_rules(rows, profile, run_id, phase, snap=None):
    active = _active_rows(profile, rows)
    segment = _segments(active, run_id, phase)
    runs = _profile_runs(profile, snap=snap)
    first = bool(runs) and run_id == runs[0]
    if phase == "apply":
        base = _carry_base(rows, profile, run_id, snap=snap)
        if first:
            base = {**_inherit(profile, snap=snap), **base}
        return _reconcile(segment, base)
    apply_seg = _segments(active, run_id, "apply")
    if first:
        apply_base = {**_inherit(profile, snap=snap), **_carry_base(rows, profile, run_id, snap=snap)}
    else:
        apply_base = _carry_base(rows, profile, run_id, snap=snap)
    apply_rules = _reconcile(apply_seg, apply_base)
    base = {r["key"]: r for r in apply_rules}
    return _reconcile(segment, base)


def _tree_digest(entries):
    payload = [
        {"key": r["key"], "value": r["value"], "source_scope": r["scope"]}
        for r in sorted(entries, key=lambda r: r["key"])
    ]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def _observed_digest(entry):
    payload = {
        "key": entry["key"],
        "value": entry["value"],
        "epoch": entry["epoch"],
        "generation": entry.get("generation", 0),
        "source_scope": entry["scope"],
        "origin": entry["origin"],
    }
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def _persisted_seal(profile, snap=None):
    path = _state_dir(profile) / "epoch.json"
    if snap is not None:
        raw = snap.get(str(path))
        if raw is None:
            return {}
        try:
            return json.loads(raw.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _span_bounds(segment):
    if not segment:
        return 0, 0, 0, 0, 0, 0
    seqs = [r["seq"] for r in segment]
    epochs = [r["epoch"] for r in segment]
    gens = [r.get("generation", 0) for r in segment]
    return min(seqs), max(seqs), min(epochs), max(epochs), min(gens), max(gens)


def _expected_trace(profile, snap=None):
    if snap is None:
        snap = _PROFILE_SNAPS.get(profile)
    if snap is None:
        snap = _PRE_RUN_SNAP
    rows = _canonical_rows(profile, snap=snap)
    active = _active_rows(profile, rows)
    layout = LAYOUT[profile]
    persisted = _persisted_seal(profile, snap=snap)
    max_epoch = max(
        [layout["epoch"], persisted.get("epoch", 0), *(r["epoch"] for r in rows)],
        default=layout["epoch"],
    )
    max_generation = max([0, *(r.get("generation", 0) for r in rows)], default=0)
    counter = max(
        layout["counter"],
        persisted.get("counter", 0),
        len(rows),
        max_generation,
        persisted.get("seal_rev", 0),
        layout.get("seal_rev", 0),
    )
    runs = []
    entries = []
    checkpoints = []
    previous = ""
    for run_id in _profile_runs(profile, snap=snap):
        apply_rules = _phase_rules(rows, profile, run_id, "apply", snap=snap)
        settle_rules = _phase_rules(rows, profile, run_id, "settle", snap=snap)
        apply_digest = _tree_digest(apply_rules)
        settle_digest = _tree_digest(settle_rules)
        runs.append({"run_id": run_id, "phase": "apply", "scope_digest": apply_digest, "previous_digest": previous})
        runs.append({"run_id": run_id, "phase": "settle", "scope_digest": settle_digest, "previous_digest": apply_digest})
        previous = settle_digest
        for phase, rules_, digest in (("apply", apply_rules, apply_digest), ("settle", settle_rules, settle_digest)):
            segment = _segments(active, run_id, phase)
            first_seq, last_seq, epoch_floor, epoch_ceil, gen_floor, gen_ceil = _span_bounds(segment)
            checkpoints.append(
                {
                    "run_id": run_id,
                    "phase": phase,
                    "first_seq": first_seq,
                    "last_seq": last_seq,
                    "record_count": len(segment),
                    "epoch_floor": epoch_floor,
                    "epoch_ceil": epoch_ceil,
                    "generation_floor": gen_floor,
                    "generation_ceil": gen_ceil,
                    "scope_digest": digest,
                }
            )
            for rule in rules_:
                entries.append(
                    {
                        "key": rule["key"],
                        "value": rule["value"],
                        "phase": phase,
                        "epoch": rule["epoch"],
                        "source_scope": rule["scope"],
                        "origin": rule["origin"],
                        "observed_digest": _observed_digest(rule),
                    }
                )
    runs.sort(key=lambda r: (r["run_id"], r["phase"]))
    entries.sort(
        key=lambda e: (
            e["key"],
            e["epoch"],
            e["phase"],
            e["value"],
            e["source_scope"],
            e["origin"],
            e["observed_digest"],
        )
    )
    checkpoints.sort(key=lambda c: (c["run_id"], c["phase"]))
    return {
        "profile": profile,
        "epoch": max_epoch,
        "counter": counter,
        "runs": runs,
        "entries": entries,
        "checkpoints": checkpoints,
    }


VERIFY = Path("/tests/verify_mux_audit.sh")


def _run_mux(args, timeout=180):
    global _PRE_RUN_SNAP
    before = _snapshot_verifier_owned()
    _PRE_RUN_SNAP = before
    # Remember the pre-run snapshot for the audited profile so later expected
    # comparisons (after other profiles run) still use that profile's inputs.
    if len(args) >= 2 and args[0] == "audit" and args[1] == "--profile":
        _PROFILE_SNAPS[args[2]] = before
    elif len(args) >= 2 and args[0] == "pulse":
        _PROFILE_SNAPS[args[1]] = before
    subprocess.run(
        ["bash", str(VERIFY), *args],
        cwd=ENV,
        check=True,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    _assert_inputs_unchanged(before)


def _run_inspect(profile, reset=True):
    if reset:
        shutil.rmtree(OUT, ignore_errors=True)
    _run_mux(["audit", "--profile", profile])
    return json.loads(TRACE.read_text())


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":")) + "\n")


def _entry_map(entries, phase=None):
    out = {}
    for row in entries:
        if phase is not None and row["phase"] != phase:
            continue
        out[row["key"]] = row
    return out


def _assert_seal(profile, trace):
    seal = json.loads((_state_dir(profile) / "epoch.json").read_text())
    assert seal["epoch"] == trace["epoch"]
    assert seal["counter"] == trace["counter"]
    assert seal["seal_rev"] >= LAYOUT[profile].get("seal_rev", 0)
    assert isinstance(seal.get("tag", ""), str)


def _assert_no_booleans(value):
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = key.lower()
            if lowered.endswith(("_ok", "_valid", "_green", "_passes")):
                raise AssertionError(key)
            if isinstance(child, bool):
                raise AssertionError(key)
            _assert_no_booleans(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_booleans(child)


def _assert_trace_shape(trace):
    assert set(trace) == {"profile", "epoch", "counter", "runs", "entries", "checkpoints"}
    assert isinstance(trace["profile"], str)
    assert isinstance(trace["epoch"], int)
    assert isinstance(trace["counter"], int)
    _assert_no_booleans(trace)
    for run in trace["runs"]:
        assert set(run) == {"run_id", "phase", "scope_digest", "previous_digest"}
        assert run["phase"] in {"apply", "settle"}
        assert HEX64.fullmatch(run["scope_digest"])
        assert run["previous_digest"] == "" or HEX64.fullmatch(run["previous_digest"])
    for entry in trace["entries"]:
        assert set(entry) == {"key", "value", "phase", "epoch", "source_scope", "origin", "observed_digest"}
        assert entry["phase"] in {"apply", "settle"}
        assert isinstance(entry["epoch"], int)
        assert HEX64.fullmatch(entry["observed_digest"])
    for point in trace["checkpoints"]:
        assert set(point) == {
            "run_id",
            "phase",
            "first_seq",
            "last_seq",
            "record_count",
            "epoch_floor",
            "epoch_ceil",
            "generation_floor",
            "generation_ceil",
            "scope_digest",
        }
        assert point["phase"] in {"apply", "settle"}
        assert point["first_seq"] <= point["last_seq"] or not point["record_count"]
        assert point["epoch_floor"] <= point["epoch_ceil"] or not point["record_count"]
        assert point["generation_floor"] <= point["generation_ceil"] or not point["record_count"]
        assert HEX64.fullmatch(point["scope_digest"])


def test_sequential_inheritance_deferred_tombstone():
    """Beryl then onyx without reset: onyx inherits PeerKid, deferred tombstone keeps ChainDepth past its window."""
    beryl = _run_inspect("beryl")
    assert beryl == _expected_trace("beryl")
    onyx = _run_inspect("onyx", reset=False)
    assert onyx == _expected_trace("onyx")
    _assert_trace_shape(onyx)
    onyx_settle = {e["key"]: e["value"] for e in onyx["entries"] if e["phase"] == "settle"}
    assert "PeerKid" in onyx_settle
    assert onyx_settle["PeerKid"] == "4"
    rows = _fixtures("onyx")
    state = _state_dir("onyx")
    retract = dict(rows[0], seq=20, epoch=9, generation=5, op="retract", effective_seq=21, phase="apply", run_id="run-a", value="")
    trigger = dict(rows[1], seq=21, epoch=9, generation=5, op="set", value="fast", phase="apply", run_id="run-a", mark=0.4)
    _write_json(state / "hold.retract.json", [retract])
    _write_json(state / "hold.spill.json", [trigger])
    rerun = _run_inspect("onyx", reset=False)
    assert rerun == _expected_trace("onyx")
    survivors = {e["key"] for e in rerun["entries"] if e["phase"] == "apply"}
    assert "ChainDepth" in survivors
    late = dict(rows[0], seq=22, epoch=10, generation=6, op="set", value="24", phase="apply", run_id="run-a", mark=0.4)
    _write_json(state / "hold.shadow.json", [late])
    final = _run_inspect("onyx", reset=False)
    assert final == _expected_trace("onyx")
    final_apply = {e["key"]: e["value"] for e in final["entries"] if e["phase"] == "apply"}
    assert final_apply.get(rows[0]["key"]) == "24"


def test_triple_profile_epoch_revision_counter_chain():
    """Amber, beryl, and onyx in one session: seal_rev and generation-aware counter converge with a stale seal and spill."""
    amber = _run_inspect("amber")
    beryl = _run_inspect("beryl", reset=False)
    onyx = _run_inspect("onyx", reset=False)
    assert amber == _expected_trace("amber")
    assert beryl == _expected_trace("beryl")
    assert onyx == _expected_trace("onyx")
    _write_json(
        _state_dir("onyx") / "epoch.json",
        {"epoch": 1, "counter": 1, "seal_rev": 0, "tag": "stale-onyx"},
    )
    rows = _fixtures("onyx")
    spill = dict(rows[0], seq=30, epoch=9, generation=8, op="set", value="40", phase="settle", run_id="run-a", mark=0.44)
    _write_json(_state_dir("onyx") / "hold.spill.json", [spill])
    rerun = _run_inspect("onyx", reset=False)
    assert rerun == _expected_trace("onyx")
    _assert_seal("onyx", rerun)
    assert rerun["counter"] >= max(8, LAYOUT["onyx"]["seal_rev"])
    assert rerun["epoch"] == 9


def test_mark_half_forward_deferred_cascade_beryl():
    """Depot run-b carries mark=0.5 entries and honors a deferred tombstone that fires only after a strictly later seq."""
    first = _run_inspect("beryl")
    assert first == _expected_trace("beryl")
    rows = _canonical_rows("beryl")
    state = _state_dir("beryl")
    half = dict(rows[0], seq=12, epoch=7, generation=5, op="set", value="carrytoken", mark=0.5, phase="settle", run_id="run-a")
    deferred = dict(rows[0], seq=13, epoch=7, generation=5, op="retract", effective_seq=15, phase="settle", run_id="run-b", value="", mark=0.0)
    bridge = dict(rows[1], seq=14, epoch=7, generation=5, op="set", value="bridged", phase="settle", run_id="run-b", mark=0.39)
    _write_json(state / "hold.shadow.json", [half])
    _write_json(state / "hold.retract.json", [deferred])
    _write_json(state / "hold.spill.json", [bridge])
    second = _run_inspect("beryl", reset=False)
    assert second == _expected_trace("beryl")
    carried = _carry_base(_canonical_rows("beryl"), "beryl", "run-b")
    assert any(r.get("mark", 0) == 0.5 for r in carried.values())
    # Bridge seq 14 does not strictly exceed effective_seq 15, so the carried key must survive settle.
    settle_vals = {e["key"]: e["value"] for e in second["entries"] if e["phase"] == "settle"}
    assert settle_vals.get(half["key"]) == "carrytoken"
    assert settle_vals.get(bridge["key"]) == "bridged"
    # A later trigger past effective_seq must activate the deferred retract on run-b.
    # Entries omit run_id, so probe the run-b settle view directly rather than the flat entry list.
    trigger = dict(rows[1], seq=16, epoch=7, generation=5, op="set", value="late", phase="settle", run_id="run-b", mark=0.39)
    _write_json(state / "hold.spill.json", [bridge, trigger])
    third = _run_inspect("beryl", reset=False)
    assert third == _expected_trace("beryl")
    run_b_settle = {r["key"] for r in _phase_rules(_canonical_rows("beryl"), "beryl", "run-b", "settle")}
    assert half["key"] not in run_b_settle


def test_companion_corruption_inheritance_idempotent():
    """Corrupt onyx primary, out-of-order spill, alien residue, inherited PeerKid, and three stable reruns."""
    _run_inspect("beryl")
    _run_inspect("onyx", reset=False)
    state = _state_dir("onyx")
    rows = _canonical_rows("onyx")
    (state / "hold.json").write_text("{")
    spill = list(reversed(rows)) + rows
    alien = dict(rows[0], profile="amber", seq=40, epoch=50, generation=20, value="999", phase="settle", run_id="run-a")
    _write_json(state / "hold.spill.json", spill + [alien])
    _write_json(state / "epoch.json", {"epoch": 0, "counter": 0, "seal_rev": 0, "tag": "broken"})
    first = _run_inspect("onyx", reset=False)
    second = _run_inspect("onyx", reset=False)
    third = _run_inspect("onyx", reset=False)
    expected = _expected_trace("onyx")
    assert first == expected
    assert second == expected
    assert third == expected
    assert "PeerKid" in {e["key"] for e in first["entries"]}
    assert all(e["epoch"] != 50 for e in first["entries"])


def test_pulse_advisory_deferred_spill_refresh():
    """Advisory pulse probe stays green while a deferred tombstone plus generation spill forces a reseal."""
    _run_inspect("beryl")
    _run_mux(["pulse", "onyx"], timeout=120)
    rows = _fixtures("onyx")
    state = _state_dir("onyx")
    _write_json(state / "epoch.json", {"epoch": 1, "counter": 1, "seal_rev": 0, "tag": "old-onyx"})
    retract = dict(rows[0], seq=25, epoch=8, generation=7, op="retract", effective_seq=27, phase="apply", run_id="run-a", value="", mark=0.0)
    spill = [
        dict(rows[1], seq=26, epoch=8, generation=7, op="set", value="fast", phase="apply", run_id="run-a", mark=0.46),
        dict(rows[0], seq=28, epoch=9, generation=8, op="set", value="48", phase="settle", run_id="run-a", mark=0.41),
    ]
    _write_json(state / "hold.retract.json", [retract])
    _write_json(state / "hold.spill.json", spill)
    trace = _run_inspect("onyx", reset=False)
    probe = json.loads((state / "pulse.json").read_text())
    assert set(probe) >= {"state", "tag"}
    assert probe["state"] == "green"
    assert trace == _expected_trace("onyx")
    _assert_seal("onyx", trace)
    assert trace["epoch"] == 9
    assert trace["counter"] >= 8
    spill_point = next(p for p in trace["checkpoints"] if p["phase"] == "settle" and p["generation_ceil"] == 8)
    assert spill_point["epoch_ceil"] == 9


def test_generation_floor_shadow_rank_tie_deferred():
    """Below-floor rows stay out, at-floor rows reconcile, shadow/spill ties break on rank, and deferred tombstones wait."""
    _run_inspect("beryl")
    _run_inspect("onyx", reset=False)
    rows = _fixtures("onyx")
    state = _state_dir("onyx")
    floor = LAYOUT["onyx"]["generation_floor"]
    below = dict(rows[0], seq=31, epoch=6, generation=0, op="set", value="ignored", phase="apply", run_id="run-a", mark=0.4)
    spill_row = dict(rows[1], seq=32, epoch=6, generation=3, op="set", value="lowrank", phase="settle", run_id="run-a", mark=0.42)
    shadow_row = dict(rows[1], seq=32, epoch=6, generation=3, op="set", value="highrank", phase="settle", run_id="run-a", mark=0.42)
    deferred = dict(rows[1], seq=33, epoch=6, generation=3, op="retract", effective_seq=33, phase="settle", run_id="run-a", value="", mark=0.0)
    trigger = dict(rows[0], seq=34, epoch=6, generation=3, op="set", value="ping", phase="settle", run_id="run-a", mark=0.4)
    at_floor = dict(rows[0], seq=35, epoch=6, generation=floor, op="set", key="FloorKid", value="atfloor", phase="settle", run_id="run-a", mark=0.4)
    _write_json(state / "hold.spill.json", [spill_row, below, trigger, at_floor])
    _write_json(state / "hold.shadow.json", [shadow_row])
    _write_json(state / "hold.retract.json", [deferred])
    trace = _run_inspect("onyx", reset=False)
    expected = _expected_trace("onyx")
    assert trace == expected
    assert "ignored" not in {e["value"] for e in trace["entries"]}
    settle_vals = {e["key"]: e["value"] for e in trace["entries"] if e["phase"] == "settle"}
    assert settle_vals.get("FloorKid") == "atfloor"


def test_malformed_primary_inherited_empty_phase_spans():
    """Malformed primary with apply-only companions still yields inherited PeerKid and zero-span settle checkpoints."""
    _run_inspect("beryl")
    _run_inspect("onyx", reset=False)
    state = _state_dir("onyx")
    rows = [r for r in _canonical_rows("onyx") if r["phase"] != "settle"]
    (state / "hold.json").write_text("[")
    _write_json(state / "hold.replay.json", rows)
    _write_json(
        state / "hold.shadow.json",
        [dict(rows[0], profile="amber", seq=50, epoch=12, generation=15, value="500", phase="settle")],
    )
    _write_json(state / "hold.spill.json", list(reversed(rows)))
    trace = _run_inspect("onyx", reset=False)
    expected = _expected_trace("onyx")
    assert trace == expected
    _assert_seal("onyx", trace)
    assert "PeerKid" in {e["key"] for e in trace["entries"]}
    inherited = _phase_rules(_canonical_rows("onyx"), "onyx", "run-a", "settle")
    settle_points = [p for p in trace["checkpoints"] if p["phase"] == "settle"]
    assert settle_points == [
        {
            "run_id": "run-a",
            "phase": "settle",
            "first_seq": 0,
            "last_seq": 0,
            "record_count": 0,
            "epoch_floor": 0,
            "epoch_ceil": 0,
            "generation_floor": 0,
            "generation_ceil": 0,
            "scope_digest": _tree_digest(inherited),
        }
    ]


def test_fixture_tier_append_remove_delete():
    """Amber baseline resolves weak-to-strong scope order, list append, override, and tombstone with no journal overlays."""
    trace = _run_inspect("amber")
    assert trace == _expected_trace("amber")
    _assert_trace_shape(trace)
    got = _entry_map(trace["entries"], phase="settle")
    assert "StaleKid" not in got
    assert got["KidAllow"]["value"] == "core,metrics,admin"
    assert got["KidAllow"]["source_scope"] == "issuer"
    assert got["KidAllow"]["origin"] == "20-final.jwks"
    assert got["RotatePort"]["value"] == "9090"
    assert got["RotatePort"]["source_scope"] == "issuer"
    assert got["RotatePort"]["origin"] == "20-final.jwks"
    assert got["AuthSkew"]["value"] == "3"
    assert got["AuthSkew"]["source_scope"] == "tenant"
    assert got["AuthSkew"]["origin"] == "10-net.jwks"
