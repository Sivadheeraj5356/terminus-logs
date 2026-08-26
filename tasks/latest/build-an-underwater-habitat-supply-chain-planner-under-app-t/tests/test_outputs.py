"""Underwater habitat supply chain planner tests with independent reference."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from cli_runner import run, run_checked

assert subprocess.__name__

APP = Path("/app")
BIN_INGEST = APP / "bin" / "habitat-resupply-ingest"
BIN_EXPORT = APP / "bin" / "habitat-resupply-export"
STATE = APP / "state"
OUTPUT = APP / "output"
TIDE_SNAPSHOT = STATE / "tide-snapshot.json"
ROV_INDEX = STATE / "rov-index.json"
BERTH_STAGING = STATE / "berth-staging.json"
EXPORT_BIND = STATE / "export-bind.json"
TRANSFER_CERT = STATE / "transfer-cert.json"
INGEST_MANIFEST = STATE / "ingest-manifest.json"
O2_FREEZE = STATE / "o2-priority-freeze.json"
EXPORT_SEAL = STATE / "export-seal.json"
RESUPPLY_PLAN = OUTPUT / "resupply-plan.json"
UTIL_REPORT = OUTPUT / "utilization-report.json"
DEFAULT_MISSION = APP / "data" / "mission"
HIDDEN = Path("/opt/verifier-fixtures")
TIDE_TRAP = HIDDEN / "tide_ms_trap"
SURGE_TRAP = HIDDEN / "surge_cargo_trap"
LANE_TRAP = HIDDEN / "lane_window_trap"
WAVE_TRAP = HIDDEN / "wave_buffer_trap"
BAND_TRAP = HIDDEN / "berth_band_trap"
OFFLINE_TRAP = HIDDEN / "rov_offline_trap"
PSI_TRAP = HIDDEN / "psi_boundary_trap"
HANDOFF_TRAP = HIDDEN / "handoff_pad_trap"


def _clear_state() -> None:
    for p in (STATE, OUTPUT):
        if p.is_dir():
            shutil.rmtree(p)
    STATE.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)


def _load_mission(root: Path) -> tuple[list[dict], dict]:
    cargo = [json.loads(line) for line in (root / "cargo.jsonl").read_text().splitlines() if line.strip()]
    cargo.sort(key=lambda e: e["cargo_id"])
    habitat = json.loads((root / "habitat.json").read_text())
    return cargo, habitat


def _mission_hash(cargo: list[dict], habitat: dict) -> str:
    body = {"cargo": cargo, "habitat": {k: habitat[k] for k in sorted(habitat) if k != "schema_version"}}
    return hashlib.sha256(json.dumps(body, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def _digest(obj: dict, fields: list[str]) -> str:
    """Documented digest: SHA-256 hex of compact sort_keys JSON over the named fields only."""
    body = {k: obj[k] for k in fields}
    return hashlib.sha256(json.dumps(body, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def reference_plan(root: Path) -> dict:
    cargo, habitat = _load_mission(root)
    mh = _mission_hash(cargo, habitat)
    acts = []
    for c in cargo:
        start = c["dock_min"] + c["tide_ms"] / 60000
        dur = c["base_min"] * c["wave_m"]
        score = c["priority"] - c["wave_m"] * 2 - abs(c["tide_ms"]) / 60000
        nr = c.get("needs_rov") or c["lane"] != habitat["primary_lane"]
        acts.append(
            {
                "cargo_id": c["cargo_id"],
                "dock_min": c["dock_min"],
                "tide_ms": c["tide_ms"],
                "berth_start": round(start, 6),
                "transfer_min": round(dur, 6),
                "berth_end": round(start + dur, 6),
                "psi": c["psi"],
                "wave_m": c["wave_m"],
                "score": round(score, 6),
                "lane": c["lane"],
                "needs_rov": nr,
                "m3": c["m3"],
                "cold": c["cold"],
                "o2": c["o2"],
            }
        )
    band = habitat.get("berth_clock_band")
    if band:
        for act in acts:
            bs = min(max(act["berth_start"], band["min"]), band["max"])
            act["berth_start"] = round(bs, 6)
            act["berth_end"] = round(act["berth_start"] + act["transfer_min"], 6)
    windows = habitat.get("lane_window_min") or {}
    for act in acts:
        offset = windows.get(act["lane"], 0)
        if offset:
            act["berth_start"] = round(act["berth_start"] + offset, 6)
            act["berth_end"] = round(act["berth_start"] + act["transfer_min"], 6)
    wave_thresh = habitat.get("wave_buffer_threshold")
    wave_buf = habitat.get("wave_buffer_min", 0)
    if wave_thresh is not None:
        for act in acts:
            if act["wave_m"] >= wave_thresh:
                act["transfer_min"] = round(act["transfer_min"] + wave_buf, 6)
                act["berth_end"] = round(act["berth_start"] + act["transfer_min"], 6)
    tide = {"schema_version": 1, "mission_hash": mh, "acts": acts}
    tide["tide_hash"] = hashlib.sha256(
        json.dumps({k: tide[k] for k in tide if k != "tide_hash"}, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()

    lead = habitat["rov_lead_min"]
    turn = habitat["rov_turn_min"]
    bays = habitat["rov_bays"]
    offline = set(habitat.get("rov_bays_offline") or [])
    eligible = [i for i in range(bays) if (i + 1) not in offline]
    free = [0.0] * bays
    slots = []
    for a in sorted(acts, key=lambda e: (e["berth_start"], e["cargo_id"])):
        if not a["needs_rov"]:
            continue
        need = a["berth_start"] - lead
        pick = min(eligible, key=lambda i: (max(free[i], need), i))
        s = max(free[pick], need)
        e = a["berth_start"]
        free[pick] = e + turn
        slots.append({"cargo_id": a["cargo_id"], "rov_id": f"R{pick + 1}", "start": round(s, 6), "end": round(e, 6)})
    rov = {"schema_version": 1, "tide_hash": tide["tide_hash"], "slots": slots}
    rov["rov_hash"] = hashlib.sha256(json.dumps(rov, separators=(",", ":"), sort_keys=True).encode()).hexdigest()

    gap = habitat["psi_gap"]
    buf = habitat["berth_gap_min"]
    surge_id = habitat.get("surge_cargo_id")
    by = {a["cargo_id"]: a for a in acts}
    surge = by.pop(surge_id, None) if surge_id else None
    order = sorted(by.values(), key=lambda e: (e["o2"], -e["score"], e["cargo_id"]))
    state = {b["berth_id"]: {"end": 0.0, "psi": None, "n": 0, "spec": b} for b in habitat["berths"]}
    assign = []
    ok = True

    def place(act: dict, *, surge_row: bool = False) -> bool:
        nonlocal ok
        opts = []
        for b in habitat["berths"]:
            bid = b["berth_id"]
            spec = state[bid]["spec"]
            if not spec["psi_min"] <= act["psi"] <= spec["psi_max"]:
                continue
            le = state[bid]["end"]
            lp = state[bid]["psi"]
            gap_used = lp is not None and abs(act["psi"] - lp) < gap
            start = act["berth_start"] if not surge_row else le + buf
            if gap_used and not surge_row:
                start = max(start, le + buf)
            if surge_row:
                start = max(start, le + buf)
                gap_used = True
            end = start + act["transfer_min"]
            opts.append((state[bid]["n"], start, bid, gap_used, end))
        if not opts:
            ok = False
            return False
        _, start, bid, gap_used, end = min(opts, key=lambda t: (t[0], t[1], t[2]))
        assign.append(
            {
                "cargo_id": act["cargo_id"],
                "berth_id": bid,
                "seq": 0,
                "gap_used": gap_used,
                "start": round(start, 6),
                "end": round(end, 6),
                "m3": act["m3"],
                "cold": act["cold"],
                **({"surge": True} if surge_row else {}),
            }
        )
        state[bid]["end"] = end
        state[bid]["psi"] = act["psi"]
        state[bid]["n"] += 1
        return True

    for act in order:
        if not place(act):
            break
    if surge is not None and ok and not place(surge, surge_row=True):
        ok = False
    assign.sort(key=lambda e: (e["start"], e["cargo_id"]))
    for i, row in enumerate(assign, 1):
        row["seq"] = i
    cold_m3 = sum(r["m3"] for r in assign if r.get("cold"))
    cap_ok = cold_m3 <= habitat["cold_cap_m3"] + 1e-9
    if not cap_ok:
        ok = False
    staging = {
        "schema_version": 1,
        "tide_hash": tide["tide_hash"],
        "assignments": assign,
        "feasible": ok,
        "cold_m3_used": round(cold_m3, 6),
        "cold_cap_ok": cap_ok,
    }
    staging["staging_hash"] = hashlib.sha256(
        json.dumps({k: staging[k] for k in staging if k != "staging_hash"}, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()

    pad = float(habitat.get("handoff_pad_min") or 0)
    by_berth: dict[str, list] = {}
    for row in assign:
        by_berth.setdefault(row["berth_id"], []).append(dict(row))
    windows = []
    for bid, rows in by_berth.items():
        rows.sort(key=lambda e: (e["start"], e["cargo_id"]))
        for i, row in enumerate(rows):
            start = row["start"]
            end = row["end"]
            handoff = False
            if i > 0 and row.get("gap_used") and pad:
                dur = end - start
                start = round(start + pad, 6)
                end = round(start + dur, 6)
                handoff = True
            windows.append(
                {
                    "cargo_id": row["cargo_id"],
                    "berth_id": bid,
                    "seq": 0,
                    "start": round(start, 6),
                    "end": round(end, 6),
                    "handoff": handoff,
                }
            )
    windows.sort(key=lambda e: (e["start"], e["cargo_id"]))
    for i, w in enumerate(windows, 1):
        w["seq"] = i
    cert = {
        "schema_version": 1,
        "tide_hash": staging["tide_hash"],
        "staging_hash": staging["staging_hash"],
        "windows": windows,
    }
    cert["cert_hash"] = hashlib.sha256(
        json.dumps({k: cert[k] for k in cert if k != "cert_hash"}, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()

    bind = {
        "schema_version": 1,
        "mission_hash": mh,
        "tide_hash": tide["tide_hash"],
        "staging_hash": staging["staging_hash"],
        "cert_hash": cert["cert_hash"],
        "feasible": staging["feasible"],
        "cold_cap_ok": staging["cold_cap_ok"],
        "cold_m3_used": staging["cold_m3_used"],
        "mission_label": habitat["mission_label"],
        "rov_bays": habitat["rov_bays"],
        "berth_ids": sorted(b["berth_id"] for b in habitat["berths"]),
        "rov_hash": rov["rov_hash"],
    }
    bind["bind_hash"] = hashlib.sha256(json.dumps(bind, separators=(",", ":"), sort_keys=True).encode()).hexdigest()

    slot_by = {s["cargo_id"]: s for s in slots}
    o2_by = {a["cargo_id"]: a["o2"] for a in sorted(acts, key=lambda e: (e["o2"], -e["score"], e["cargo_id"]))}
    surge_ids = {r["cargo_id"] for r in assign if r.get("surge")}
    lines = []
    for row in windows:
        slot = slot_by.get(row["cargo_id"])
        lines.append(
            {
                "cargo_id": row["cargo_id"],
                "berth_id": row["berth_id"],
                "seq": row["seq"],
                "start": row["start"],
                "end": row["end"],
                "rov_id": slot["rov_id"] if slot else None,
                "surge": row["cargo_id"] in surge_ids,
                "o2": o2_by[row["cargo_id"]],
            }
        )
    plan = {
        "schema_version": 1,
        "mission_label": habitat["mission_label"],
        "lines": lines,
        "tide_hash": tide["tide_hash"],
        "staging_hash": staging["staging_hash"],
    }
    report = {
        "schema_version": 1,
        "rov_bays": habitat["rov_bays"],
        "cold_m3_used": staging["cold_m3_used"],
        "berth_load": {b["berth_id"]: sum(1 for line in lines if line["berth_id"] == b["berth_id"]) for b in habitat["berths"]},
        "fingerprint": hashlib.sha256(json.dumps(plan, separators=(",", ":"), sort_keys=True).encode()).hexdigest(),
    }
    return {"tide": tide, "rov": rov, "staging": staging, "cert": cert, "bind": bind, "plan": plan, "report": report, "habitat": habitat}


def reference_export_from_state() -> dict:
    """Expected export outputs from /app/state only (no mission directory reads)."""
    tide = json.loads(TIDE_SNAPSHOT.read_text())
    rov = json.loads(ROV_INDEX.read_text())
    stg = json.loads(BERTH_STAGING.read_text())
    cert = json.loads(TRANSFER_CERT.read_text())
    bind = json.loads(EXPORT_BIND.read_text())
    man = json.loads(INGEST_MANIFEST.read_text())
    freeze = json.loads(O2_FREEZE.read_text())
    if bind["bind_hash"] != man.get("bind_hash", ""):
        raise AssertionError("bind_hash mismatch between export-bind and ingest-manifest")
    if bind.get("rov_hash") != man.get("rov_hash", ""):
        raise AssertionError("rov_hash mismatch between export-bind and ingest-manifest")
    if bind.get("cert_hash") != cert.get("cert_hash", ""):
        raise AssertionError("cert_hash mismatch between export-bind and transfer-cert")
    if not stg.get("feasible"):
        raise AssertionError("berth-staging feasible is false")
    if not stg.get("cold_cap_ok"):
        raise AssertionError("berth-staging cold_cap_ok is false")
    slots = {s["cargo_id"]: s for s in rov["slots"]}
    o2_by = {e["cargo_id"]: e["o2"] for e in freeze["entries"]}
    surge_ids = {r["cargo_id"] for r in stg["assignments"] if r.get("surge")}
    lines = []
    for row in cert["windows"]:
        slot = slots.get(row["cargo_id"])
        lines.append(
            {
                "cargo_id": row["cargo_id"],
                "berth_id": row["berth_id"],
                "seq": row["seq"],
                "start": row["start"],
                "end": row["end"],
                "rov_id": slot["rov_id"] if slot else None,
                "surge": row["cargo_id"] in surge_ids,
                "o2": o2_by[row["cargo_id"]],
            }
        )
    plan = {
        "schema_version": 1,
        "mission_label": bind["mission_label"],
        "lines": lines,
        "tide_hash": tide["tide_hash"],
        "staging_hash": stg["staging_hash"],
    }
    plan_body = json.dumps(plan, separators=(",", ":"), sort_keys=True)
    berth_load = {bid: sum(1 for line in lines if line["berth_id"] == bid) for bid in bind["berth_ids"]}
    report = {
        "schema_version": 1,
        "rov_bays": bind["rov_bays"],
        "cold_m3_used": stg["cold_m3_used"],
        "berth_load": berth_load,
        "fingerprint": hashlib.sha256(plan_body.encode()).hexdigest(),
    }
    return {"plan": plan, "report": report, "bind": bind}


def _pipeline(root: Path = DEFAULT_MISSION, *, env: dict[str, str] | None = None) -> None:
    _clear_state()
    if root == DEFAULT_MISSION:
        run_checked([str(BIN_INGEST)], env=env)
    else:
        run_checked([str(BIN_INGEST), str(root)], env=env)
    run_checked([str(BIN_EXPORT)], env=env)


def test_reference_independent_for_bundled_mission() -> None:
    """Verify reference independent for bundled mission per instruction and docs contracts."""
    ref = reference_plan(DEFAULT_MISSION)
    assert len(ref["plan"]["lines"]) == 8


def test_ingest_writes_tide_snapshot_staging() -> None:
    """Verify ingest writes tide snapshot staging per instruction and docs contracts."""
    _pipeline()
    ref = reference_plan(DEFAULT_MISSION)
    tide = json.loads(TIDE_SNAPSHOT.read_text())
    assert tide["tide_hash"] == ref["tide"]["tide_hash"]


def test_export_reads_staging_not_cargo_jsonl() -> None:
    """Verify export reads staging not cargo jsonl per instruction and docs contracts."""
    _pipeline()
    ref = reference_export_from_state()
    plan = json.loads(RESUPPLY_PLAN.read_text())
    assert plan == ref["plan"]
    bind = json.loads(EXPORT_BIND.read_text())
    assert bind["mission_label"] == ref["bind"]["mission_label"]
    assert bind["rov_bays"] == ref["bind"]["rov_bays"]
    assert bind["berth_ids"] == ref["bind"]["berth_ids"]


def test_export_succeeds_without_mission_directory() -> None:
    """Export must publish from staging when mission inputs are unavailable."""
    _clear_state()
    run_checked([str(BIN_INGEST)])
    ref = reference_export_from_state()
    hidden = APP / "data" / "mission.staged-away"
    if hidden.exists():
        shutil.rmtree(hidden)
    shutil.move(str(DEFAULT_MISSION), str(hidden))
    try:
        run_checked([str(BIN_EXPORT)])
        plan = json.loads(RESUPPLY_PLAN.read_text())
        report = json.loads(UTIL_REPORT.read_text())
        assert plan == ref["plan"]
        assert report == ref["report"]
    finally:
        if hidden.exists() and not DEFAULT_MISSION.exists():
            shutil.move(str(hidden), str(DEFAULT_MISSION))


def test_export_ignores_tampered_mission_label() -> None:
    """Export must not re-read habitat.json after ingest."""
    _clear_state()
    run_checked([str(BIN_INGEST)])
    ref = reference_export_from_state()
    hab_path = DEFAULT_MISSION / "habitat.json"
    original = hab_path.read_text()
    try:
        hab = json.loads(original)
        hab["mission_label"] = "tampered-label-should-not-appear"
        hab_path.write_text(json.dumps(hab, indent=2) + "\n")
        run_checked([str(BIN_EXPORT)])
        plan = json.loads(RESUPPLY_PLAN.read_text())
        ref = reference_export_from_state()
        assert plan["mission_label"] == ref["bind"]["mission_label"]
        assert plan["mission_label"] != "tampered-label-should-not-appear"
    finally:
        hab_path.write_text(original)


def test_signed_tide_ms_in_berth_start() -> None:
    """Verify signed tide ms in berth start per instruction and docs contracts."""
    _pipeline()
    ref = reference_plan(DEFAULT_MISSION)
    tide = json.loads(TIDE_SNAPSHOT.read_text())
    assert tide["acts"] == ref["tide"]["acts"]


def test_negative_tide_ms_preserved() -> None:
    """Verify negative tide ms preserved per instruction and docs contracts."""
    _pipeline()
    tide = json.loads(TIDE_SNAPSHOT.read_text())
    by = {a["cargo_id"]: a for a in tide["acts"]}
    assert by["uh-c03"]["tide_ms"] == -180000


def test_wave_m_scales_transfer_min() -> None:
    """Verify wave m scales transfer min per instruction and docs contracts."""
    _pipeline()
    ref = reference_plan(DEFAULT_MISSION)
    tide = json.loads(TIDE_SNAPSHOT.read_text())
    by = {a["cargo_id"]: a for a in tide["acts"]}
    ref_by = {a["cargo_id"]: a for a in ref["tide"]["acts"]}
    assert by["uh-c06"]["transfer_min"] == ref_by["uh-c06"]["transfer_min"]


def test_rov_slots_honor_lead_time() -> None:
    """Verify rov slots honor lead time per instruction and docs contracts."""
    _pipeline()
    ref = reference_plan(DEFAULT_MISSION)
    rov = json.loads(ROV_INDEX.read_text())
    assert rov["slots"] == ref["rov"]["slots"]


def test_berth_assignments_use_o2_priority_not_lex() -> None:
    """Verify berth assignments use o2 priority not lex per instruction and docs contracts."""
    _pipeline()
    ref = reference_plan(DEFAULT_MISSION)
    stg = json.loads(BERTH_STAGING.read_text())
    assert stg["assignments"] == ref["staging"]["assignments"]


def test_pressure_gap_applied_on_close_psi() -> None:
    """Verify pressure gap applied on close psi per instruction and docs contracts."""
    _pipeline()
    stg = json.loads(BERTH_STAGING.read_text())
    assert any(r.get("gap_used") for r in stg["assignments"])


def test_cold_cap_ok_on_bundled_mission() -> None:
    """Verify cold cap ok on bundled mission per instruction and docs contracts."""
    _pipeline()
    stg = json.loads(BERTH_STAGING.read_text())
    assert stg["cold_cap_ok"] is True
    assert stg["cold_m3_used"] == reference_plan(DEFAULT_MISSION)["staging"]["cold_m3_used"]


def test_export_bind_written_on_ingest() -> None:
    """Verify export bind written on ingest per instruction and docs contracts."""
    _pipeline()
    bind = json.loads(EXPORT_BIND.read_text())
    assert bind["bind_hash"]


def test_ingest_manifest_records_run_sequence() -> None:
    """Verify ingest manifest records run sequence per instruction and docs contracts."""
    _pipeline()
    man = json.loads(INGEST_MANIFEST.read_text())
    assert man["run_sequence"] >= 1


def test_re_ingest_keeps_mission_hash() -> None:
    """Verify re ingest keeps mission hash per instruction and docs contracts."""
    _pipeline()
    first = json.loads(TIDE_SNAPSHOT.read_text())["mission_hash"]
    run_checked([str(BIN_INGEST)])
    second = json.loads(TIDE_SNAPSHOT.read_text())["mission_hash"]
    assert first == second


def test_re_ingest_advances_run_sequence() -> None:
    """Verify re ingest advances run sequence per instruction and docs contracts."""
    _pipeline()
    seq1 = json.loads(INGEST_MANIFEST.read_text())["run_sequence"]
    run_checked([str(BIN_INGEST)])
    seq2 = json.loads(INGEST_MANIFEST.read_text())["run_sequence"]
    assert seq2 == seq1 + 1


def test_publish_writes_plan_and_report() -> None:
    """Verify publish writes plan and report per instruction and docs contracts."""
    _pipeline()
    ref = reference_export_from_state()
    plan = json.loads(RESUPPLY_PLAN.read_text())
    report = json.loads(UTIL_REPORT.read_text())
    assert plan == ref["plan"]
    assert report == ref["report"]


def test_export_matches_state_only_reference() -> None:
    """Export outputs must match reference built only from /app/state artifacts."""
    _pipeline()
    ref = reference_export_from_state()
    assert json.loads(RESUPPLY_PLAN.read_text()) == ref["plan"]
    assert json.loads(UTIL_REPORT.read_text()) == ref["report"]


def test_export_util_report_rov_bays_from_bind() -> None:
    """Export must read rov_bays from export-bind.json, not habitat.json."""
    _clear_state()
    run_checked([str(BIN_INGEST)])
    hab_path = DEFAULT_MISSION / "habitat.json"
    original = hab_path.read_text()
    try:
        hab = json.loads(original)
        hab["rov_bays"] = hab["rov_bays"] + 99
        hab_path.write_text(json.dumps(hab, indent=2) + "\n")
        run_checked([str(BIN_EXPORT)])
        ref = reference_export_from_state()
        report = json.loads(UTIL_REPORT.read_text())
        assert report["rov_bays"] == ref["bind"]["rov_bays"]
        assert report["rov_bays"] != hab["rov_bays"]
    finally:
        hab_path.write_text(original)


def test_repeat_export_byte_identical_plan() -> None:
    """Verify repeat export byte identical plan per instruction and docs contracts."""
    _pipeline()
    first = RESUPPLY_PLAN.read_bytes()
    run_checked([str(BIN_EXPORT)])
    assert RESUPPLY_PLAN.read_bytes() == first


def test_resupply_mission_dir_override() -> None:
    """Verify resupply mission dir override per instruction and docs contracts."""
    env = {"RESUPPLY_MISSION_DIR": str(TIDE_TRAP)}
    _pipeline(TIDE_TRAP, env=env)
    plan = json.loads(RESUPPLY_PLAN.read_text())
    assert any(line["cargo_id"] == "uh-w01" for line in plan["lines"])


def test_hidden_tide_ms_trap_matches_reference() -> None:
    """Hidden /opt/verifier-fixtures/tide_ms_trap requires signed tide_ms in tide snapshot."""
    env = {"RESUPPLY_MISSION_DIR": str(TIDE_TRAP)}
    _pipeline(TIDE_TRAP, env=env)
    ref = reference_plan(TIDE_TRAP)
    tide = json.loads(TIDE_SNAPSHOT.read_text())
    assert tide["acts"] == ref["tide"]["acts"]


def test_hidden_surge_cargo_trap_schedules_last() -> None:
    """Hidden /opt/verifier-fixtures/surge_cargo_trap must schedule surge_cargo_id last."""
    env = {"RESUPPLY_MISSION_DIR": str(SURGE_TRAP)}
    _pipeline(SURGE_TRAP, env=env)
    stg = json.loads(BERTH_STAGING.read_text())
    surge = [r for r in stg["assignments"] if r.get("surge")]
    assert len(surge) == 1 and surge[0]["cargo_id"] == "uh-s04"


def test_export_fails_without_staging() -> None:
    """Verify export fails without staging per instruction and docs contracts."""
    _clear_state()
    proc = run([str(BIN_EXPORT)])
    assert proc.returncode != 0


def test_export_fails_when_cold_cap_exceeded() -> None:
    """Export must fail when cold_cap_ok is false on berth staging."""
    _pipeline()
    stg = json.loads(BERTH_STAGING.read_text())
    stg["cold_cap_ok"] = False
    BERTH_STAGING.write_text(json.dumps(stg, indent=2) + "\n")
    proc = run([str(BIN_EXPORT)])
    assert proc.returncode != 0


def test_staging_feasible_true_bundled() -> None:
    """Verify staging feasible true bundled per instruction and docs contracts."""
    _pipeline()
    stg = json.loads(BERTH_STAGING.read_text())
    assert stg["feasible"] is True


def test_all_seven_ingest_state_files_exist_after_ingest() -> None:
    """Verify all seven ingest state files exist after ingest per cli.md."""
    _pipeline()
    for path in (TIDE_SNAPSHOT, ROV_INDEX, BERTH_STAGING, TRANSFER_CERT, EXPORT_BIND, O2_FREEZE, INGEST_MANIFEST):
        assert path.is_file()


def test_plan_has_eight_lines_bundled() -> None:
    """Verify plan has eight lines bundled per instruction and docs contracts."""
    _pipeline()
    plan = json.loads(RESUPPLY_PLAN.read_text())
    assert len(plan["lines"]) == 8


def test_util_report_berth_load_matches_reference() -> None:
    """Verify util report berth load matches reference per instruction and docs contracts."""
    _pipeline()
    ref = reference_export_from_state()
    report = json.loads(UTIL_REPORT.read_text())
    assert report["berth_load"] == ref["report"]["berth_load"]


def test_publish_rejects_missing_bind_hash_alignment() -> None:
    """Verify publish rejects missing bind hash alignment per instruction and docs contracts."""
    _pipeline()
    man = json.loads(INGEST_MANIFEST.read_text())
    man["bind_hash"] = "0" * 64
    INGEST_MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
    proc = run([str(BIN_EXPORT)])
    assert proc.returncode != 0


def test_instruction_output_paths_exist() -> None:
    """Verify instruction output paths exist per instruction and docs contracts."""
    assert DEFAULT_MISSION == Path("/app/data/mission")
    assert DEFAULT_MISSION.is_dir()
    _pipeline()
    assert RESUPPLY_PLAN == Path("/app/output/resupply-plan.json")
    assert UTIL_REPORT == Path("/app/output/utilization-report.json")
    assert TIDE_SNAPSHOT == Path("/app/state/tide-snapshot.json")
    assert ROV_INDEX == Path("/app/state/rov-index.json")
    assert BERTH_STAGING == Path("/app/state/berth-staging.json")
    assert TRANSFER_CERT == Path("/app/state/transfer-cert.json")
    assert EXPORT_BIND == Path("/app/state/export-bind.json")
    assert O2_FREEZE == Path("/app/state/o2-priority-freeze.json")
    assert INGEST_MANIFEST == Path("/app/state/ingest-manifest.json")
    assert EXPORT_SEAL == Path("/app/state/export-seal.json")
    for path in (
        RESUPPLY_PLAN,
        UTIL_REPORT,
        TIDE_SNAPSHOT,
        ROV_INDEX,
        BERTH_STAGING,
        TRANSFER_CERT,
        EXPORT_BIND,
        O2_FREEZE,
        INGEST_MANIFEST,
        EXPORT_SEAL,
    ):
        assert path.is_file()


def test_tide_snapshot_schema_version_one() -> None:
    """Verify tide snapshot schema version one per instruction and docs contracts."""
    _pipeline()
    assert json.loads(TIDE_SNAPSHOT.read_text())["schema_version"] == 1


def test_staging_hash_matches_reference() -> None:
    """Verify staging hash matches reference per instruction and docs contracts."""
    _pipeline()
    ref = reference_plan(DEFAULT_MISSION)
    stg = json.loads(BERTH_STAGING.read_text())
    assert stg["staging_hash"] == ref["staging"]["staging_hash"]


def test_rov_hash_matches_reference() -> None:
    """Verify rov hash matches reference per instruction and docs contracts."""
    _pipeline()
    ref = reference_plan(DEFAULT_MISSION)
    rov = json.loads(ROV_INDEX.read_text())
    assert rov["rov_hash"] == ref["rov"]["rov_hash"]


def test_mission_label_on_plan() -> None:
    """Verify mission label on plan per instruction and docs contracts."""
    _pipeline()
    plan = json.loads(RESUPPLY_PLAN.read_text())
    assert plan["mission_label"] == "hadal-trench-resupply-4471"


def test_fingerprint_stable_on_reexport() -> None:
    """Verify fingerprint stable on reexport per instruction and docs contracts."""
    _pipeline()
    fp1 = json.loads(UTIL_REPORT.read_text())["fingerprint"]
    run_checked([str(BIN_EXPORT)])
    fp2 = json.loads(UTIL_REPORT.read_text())["fingerprint"]
    assert fp1 == fp2


def test_resupply_mission_dir_absolute_required() -> None:
    """Verify resupply mission dir absolute required per instruction and docs contracts."""
    proc = run([str(BIN_INGEST), "relative/path"])
    assert proc.returncode != 0


def test_bind_includes_rov_hash_after_ingest() -> None:
    """export-bind must freeze rov_hash from rov-index during ingest."""
    _pipeline()
    bind = json.loads(EXPORT_BIND.read_text())
    rov = json.loads(ROV_INDEX.read_text())
    man = json.loads(INGEST_MANIFEST.read_text())
    assert bind.get("rov_hash") == rov["rov_hash"]
    assert man.get("rov_hash") == rov["rov_hash"]


def test_export_seal_written_after_publish() -> None:
    """Successful export must persist export-seal.json per export-seal.md."""
    _pipeline()
    assert EXPORT_SEAL.is_file()
    seal = json.loads(EXPORT_SEAL.read_text())
    man = json.loads(INGEST_MANIFEST.read_text())
    bind = json.loads(EXPORT_BIND.read_text())
    assert seal["run_sequence"] == man["run_sequence"]
    assert seal["bind_hash"] == bind["bind_hash"]
    assert seal["rov_hash"] == bind["rov_hash"]


def test_export_seal_fingerprint_matches_report() -> None:
    """export-seal plan_fingerprint must match utilization-report fingerprint."""
    _pipeline()
    seal = json.loads(EXPORT_SEAL.read_text())
    report = json.loads(UTIL_REPORT.read_text())
    assert seal["plan_fingerprint"] == report["fingerprint"]


def test_repeat_export_preserves_export_seal() -> None:
    """Repeat export without re-ingest must leave export-seal byte-identical."""
    _pipeline()
    first = EXPORT_SEAL.read_bytes()
    run_checked([str(BIN_EXPORT)])
    assert EXPORT_SEAL.read_bytes() == first


def test_publish_rejects_rov_hash_chain_break() -> None:
    """publish_gate must fail when export-bind rov_hash does not match rov-index."""
    _pipeline()
    bind = json.loads(EXPORT_BIND.read_text())
    bind["rov_hash"] = "0" * 64
    EXPORT_BIND.write_text(json.dumps(bind, indent=2) + "\n")
    proc = run([str(BIN_EXPORT)])
    assert proc.returncode != 0


def test_hidden_lane_window_trap_matches_reference() -> None:
    """Hidden lane_window_trap requires lane_window_min offsets before ROV scheduling."""
    env = {"RESUPPLY_MISSION_DIR": str(LANE_TRAP)}
    _pipeline(LANE_TRAP, env=env)
    ref = reference_plan(LANE_TRAP)
    tide = json.loads(TIDE_SNAPSHOT.read_text())
    assert tide["acts"] == ref["tide"]["acts"]
    rov = json.loads(ROV_INDEX.read_text())
    assert rov["slots"] == ref["rov"]["slots"]


def test_wave_buffer_extends_high_wave_transfer() -> None:
    """Bundled mission applies wave_buffer_min when wave_m meets habitat threshold."""
    _pipeline()
    ref = reference_plan(DEFAULT_MISSION)
    tide = json.loads(TIDE_SNAPSHOT.read_text())
    by = {a["cargo_id"]: a for a in tide["acts"]}
    assert by["uh-c06"]["transfer_min"] == ref["tide"]["acts"][5]["transfer_min"]


def test_o2_priority_freeze_written_on_ingest() -> None:
    """Ingest must write o2-priority-freeze.json with ledger order per o2-priority-freeze.md."""
    _pipeline()
    ref = reference_plan(DEFAULT_MISSION)
    freeze = json.loads(O2_FREEZE.read_text())
    ranked = sorted(ref["tide"]["acts"], key=lambda e: (e["o2"], -e["score"], e["cargo_id"]))
    expected = [{"cargo_id": r["cargo_id"], "o2": r["o2"]} for r in ranked]
    assert freeze["tide_hash"] == ref["tide"]["tide_hash"]
    assert freeze["entries"] == expected
    assert freeze["freeze_hash"]


def test_export_fails_when_o2_freeze_tampered() -> None:
    """Export must reject when o2-priority-freeze entries change without a matching freeze_hash."""
    _pipeline()
    freeze = json.loads(O2_FREEZE.read_text())
    freeze["entries"][0]["o2"] = 99
    O2_FREEZE.write_text(json.dumps(freeze, indent=2) + "\n")
    proc = run([str(BIN_EXPORT)])
    assert proc.returncode != 0


def test_hidden_wave_buffer_trap_matches_reference() -> None:
    """Hidden wave_buffer_trap requires wave_buffer_min padding on high wave_m cargo."""
    env = {"RESUPPLY_MISSION_DIR": str(WAVE_TRAP)}
    _pipeline(WAVE_TRAP, env=env)
    ref = reference_plan(WAVE_TRAP)
    tide = json.loads(TIDE_SNAPSHOT.read_text())
    assert tide["acts"] == ref["tide"]["acts"]
    rov = json.loads(ROV_INDEX.read_text())
    assert rov["slots"] == ref["rov"]["slots"]


def test_bind_hash_recomputed_matches_reference() -> None:
    """export-bind bind_hash is the documented digest over its fields and equals the reference."""
    _pipeline()
    ref = reference_plan(DEFAULT_MISSION)
    bind = json.loads(EXPORT_BIND.read_text())
    fields = [
        "schema_version",
        "mission_hash",
        "tide_hash",
        "staging_hash",
        "cert_hash",
        "feasible",
        "cold_cap_ok",
        "cold_m3_used",
        "mission_label",
        "rov_bays",
        "berth_ids",
        "rov_hash",
    ]
    assert _digest(bind, fields) == bind["bind_hash"]
    assert bind["bind_hash"] == ref["bind"]["bind_hash"]


def test_manifest_hash_recomputed_matches_reference() -> None:
    """ingest-manifest manifest_hash is the documented digest over its fields per ingest-manifest.md."""
    _pipeline()
    ref = reference_plan(DEFAULT_MISSION)
    man = json.loads(INGEST_MANIFEST.read_text())
    fields = [
        "schema_version",
        "mission_hash",
        "bind_hash",
        "rov_hash",
        "run_sequence",
        "feasible",
        "cold_cap_ok",
    ]
    assert _digest(man, fields) == man["manifest_hash"]
    assert man["mission_hash"] == ref["bind"]["mission_hash"]
    assert man["bind_hash"] == ref["bind"]["bind_hash"]
    assert man["rov_hash"] == ref["rov"]["rov_hash"]


def test_freeze_hash_recomputed_matches_reference() -> None:
    """o2-priority-freeze freeze_hash is the documented digest over schema_version, tide_hash, entries."""
    _pipeline()
    ref = reference_plan(DEFAULT_MISSION)
    freeze = json.loads(O2_FREEZE.read_text())
    ranked = sorted(ref["tide"]["acts"], key=lambda e: (e["o2"], -e["score"], e["cargo_id"]))
    expected_entries = [{"cargo_id": r["cargo_id"], "o2": r["o2"]} for r in ranked]
    assert freeze["tide_hash"] == ref["tide"]["tide_hash"]
    assert freeze["entries"] == expected_entries
    assert _digest(freeze, ["schema_version", "tide_hash", "entries"]) == freeze["freeze_hash"]


def test_export_seal_hash_recomputed_matches_reference() -> None:
    """export-seal seal_hash is the documented digest over its fields per export-seal.md."""
    _pipeline()
    ref = reference_plan(DEFAULT_MISSION)
    seal = json.loads(EXPORT_SEAL.read_text())
    man = json.loads(INGEST_MANIFEST.read_text())
    assert seal["run_sequence"] == man["run_sequence"]
    assert seal["bind_hash"] == ref["bind"]["bind_hash"]
    assert seal["rov_hash"] == ref["rov"]["rov_hash"]
    assert seal["plan_fingerprint"] == ref["report"]["fingerprint"]
    fields = ["schema_version", "run_sequence", "bind_hash", "rov_hash", "plan_fingerprint"]
    assert _digest(seal, fields) == seal["seal_hash"]


def test_export_fails_when_rov_index_tide_hash_broken() -> None:
    """publish_gate must reject when rov-index tide_hash no longer matches tide-snapshot tide_hash."""
    _pipeline()
    rov = json.loads(ROV_INDEX.read_text())
    rov["tide_hash"] = "0" * 64
    ROV_INDEX.write_text(json.dumps(rov, indent=2) + "\n")
    proc = run([str(BIN_EXPORT)])
    assert proc.returncode != 0


def test_export_fails_when_staging_infeasible() -> None:
    """publish_gate must reject when berth-staging feasible is false even if cold_cap_ok is true."""
    _pipeline()
    stg = json.loads(BERTH_STAGING.read_text())
    assert stg["cold_cap_ok"] is True
    stg["feasible"] = False
    BERTH_STAGING.write_text(json.dumps(stg, indent=2) + "\n")
    proc = run([str(BIN_EXPORT)])
    assert proc.returncode != 0


def test_hidden_berth_clock_band_clamps_before_lane_window() -> None:
    """Hidden berth_band_trap clamps berth_start into berth_clock_band on tide acts.

    Band clamping is checked here in isolation via act values and band bounds.
    Digest-chain coverage for tide_hash lives in the bundled recompute/hash tests.
    lane_window_min is covered by test_hidden_lane_window_trap_matches_reference
    so this trap does not stack both optional clock policies into one combination.
    """
    env = {"RESUPPLY_MISSION_DIR": str(BAND_TRAP)}
    _pipeline(BAND_TRAP, env=env)
    ref = reference_plan(BAND_TRAP)
    tide = json.loads(TIDE_SNAPSHOT.read_text())
    assert tide["acts"] == ref["tide"]["acts"]
    band = json.loads((BAND_TRAP / "habitat.json").read_text())["berth_clock_band"]
    for act in tide["acts"]:
        assert band["min"] <= act["berth_start"] <= band["max"]


def test_hidden_berth_clock_band_plan_matches_reference() -> None:
    """Hidden berth_band_trap export plan must match the state-only reference after clamping."""
    env = {"RESUPPLY_MISSION_DIR": str(BAND_TRAP)}
    _pipeline(BAND_TRAP, env=env)
    ref = reference_export_from_state()
    plan = json.loads(RESUPPLY_PLAN.read_text())
    report = json.loads(UTIL_REPORT.read_text())
    assert plan == ref["plan"]
    assert report == ref["report"]


def test_hidden_rov_bays_offline_masks_bays() -> None:
    """Hidden rov_offline_trap must skip offline ROV bays when selecting slots."""
    env = {"RESUPPLY_MISSION_DIR": str(OFFLINE_TRAP)}
    _pipeline(OFFLINE_TRAP, env=env)
    ref = reference_plan(OFFLINE_TRAP)
    rov = json.loads(ROV_INDEX.read_text())
    assert rov["slots"] == ref["rov"]["slots"]
    assert rov["rov_hash"] == ref["rov"]["rov_hash"]
    assert all(slot["rov_id"] != "R1" for slot in rov["slots"])


def test_hidden_psi_gap_strict_boundary() -> None:
    """Hidden psi_boundary_trap: psi difference exactly equal to psi_gap must not set gap_used."""
    env = {"RESUPPLY_MISSION_DIR": str(PSI_TRAP)}
    _pipeline(PSI_TRAP, env=env)
    ref = reference_plan(PSI_TRAP)
    stg = json.loads(BERTH_STAGING.read_text())
    assert stg["assignments"] == ref["staging"]["assignments"]
    assert stg["staging_hash"] == ref["staging"]["staging_hash"]
    assert all(row.get("gap_used") is False for row in stg["assignments"])


def test_transfer_cert_written_on_ingest() -> None:
    """Ingest must write transfer-cert.json with windows and cert_hash per transfer-cert.md."""
    _pipeline()
    ref = reference_plan(DEFAULT_MISSION)
    cert = json.loads(TRANSFER_CERT.read_text())
    assert cert["windows"] == ref["cert"]["windows"]
    assert cert["cert_hash"] == ref["cert"]["cert_hash"]
    assert cert["staging_hash"] == ref["staging"]["staging_hash"]


def test_export_reads_transfer_cert_not_staging_times() -> None:
    """Plan line start/end/seq must match transfer-cert windows, not berth-staging assignments."""
    _pipeline()
    plan = json.loads(RESUPPLY_PLAN.read_text())
    cert = json.loads(TRANSFER_CERT.read_text())
    stg = json.loads(BERTH_STAGING.read_text())
    by_cert = {w["cargo_id"]: w for w in cert["windows"]}
    for line in plan["lines"]:
        w = by_cert[line["cargo_id"]]
        assert line["start"] == w["start"]
        assert line["end"] == w["end"]
        assert line["seq"] == w["seq"]
    # Staging may share times when pad is zero, but export must still be cert-backed.
    assert {a["cargo_id"] for a in stg["assignments"]} == {w["cargo_id"] for w in cert["windows"]}


def test_export_plan_o2_from_freeze_not_tide() -> None:
    """Plan line o2 values must match o2-priority-freeze entries."""
    _pipeline()
    plan = json.loads(RESUPPLY_PLAN.read_text())
    freeze = json.loads(O2_FREEZE.read_text())
    by = {e["cargo_id"]: e["o2"] for e in freeze["entries"]}
    for line in plan["lines"]:
        assert line["o2"] == by[line["cargo_id"]]


def test_publish_rejects_cert_hash_chain_break() -> None:
    """publish_gate must fail when export-bind cert_hash does not match transfer-cert."""
    _pipeline()
    bind = json.loads(EXPORT_BIND.read_text())
    bind["cert_hash"] = "0" * 64
    EXPORT_BIND.write_text(json.dumps(bind, indent=2) + "\n")
    proc = run([str(BIN_EXPORT)])
    assert proc.returncode != 0


def test_export_fails_without_transfer_cert() -> None:
    """Export must fail when transfer-cert.json is missing."""
    _pipeline()
    TRANSFER_CERT.unlink()
    proc = run([str(BIN_EXPORT)])
    assert proc.returncode != 0


def test_cert_hash_recomputed_matches_reference() -> None:
    """transfer-cert cert_hash is the documented digest over its fields."""
    _pipeline()
    ref = reference_plan(DEFAULT_MISSION)
    cert = json.loads(TRANSFER_CERT.read_text())
    assert _digest(cert, ["schema_version", "tide_hash", "staging_hash", "windows"]) == cert["cert_hash"]
    assert cert["cert_hash"] == ref["cert"]["cert_hash"]


def test_hidden_handoff_pad_trap_matches_reference() -> None:
    """Hidden handoff_pad_trap pads gap_used same-berth windows; staging-copy cert fails."""
    env = {"RESUPPLY_MISSION_DIR": str(HANDOFF_TRAP)}
    _pipeline(HANDOFF_TRAP, env=env)
    ref = reference_plan(HANDOFF_TRAP)
    cert = json.loads(TRANSFER_CERT.read_text())
    assert cert["windows"] == ref["cert"]["windows"]
    assert any(w["handoff"] for w in cert["windows"])
    plan = json.loads(RESUPPLY_PLAN.read_text())
    report = json.loads(UTIL_REPORT.read_text())
    state_ref = reference_export_from_state()
    assert plan == state_ref["plan"]
    assert report == state_ref["report"]
    assert plan["lines"] == ref["plan"]["lines"]
    stg = json.loads(BERTH_STAGING.read_text())
    stg_by = {r["cargo_id"]: r for r in stg["assignments"]}
    assert any(w["start"] != stg_by[w["cargo_id"]]["start"] for w in cert["windows"] if w["handoff"])
