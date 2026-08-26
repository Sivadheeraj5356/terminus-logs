"""Behavioral verifier for the LNG tank boil-off reconciler."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/app")
BIN = ROOT / "bin" / "lng-boiloff-reconciler"
AMBIENT_TEMP_C = 25.0


def ts(v: str) -> datetime:
    return datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(timezone.utc)


def r3(v: float) -> float:
    return round(v + 1e-9, 3)


def rcsv(p: Path) -> list[dict[str, str]]:
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def wcsv(p: Path, rows: list[dict[str, str]]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def copy_inputs(dst: Path) -> None:
    shutil.copytree(ROOT / "data", dst, dirs_exist_ok=True)


def hjson(v) -> str:
    s = json.dumps(v, separators=(",", ":"))
    s = re.sub(r"(?<=[\[:,])(-?\d+)\.0(?=[,\]}])", r"\1", s)
    return hashlib.sha256(s.encode()).hexdigest()


def shash(d: Path) -> str:
    h = hashlib.sha256()
    for rel in [
        "tanks.csv",
        "tank_readings.csv",
        "transfer_events.csv",
        "inventory_snapshots.csv",
        "maintenance_events.csv",
        "config/boiloff-profiles.json",
    ]:
        h.update(rel.encode())
        h.update(b"\0")
        h.update((d / rel).read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def seal(stage: dict) -> str:
    return hjson(
        {
            "version": stage["version"],
            "source_hash": stage["source_hash"],
            "stage_hash": stage["stage_hash"],
            "tanks": stage["tanks"],
        }
    )


def wetted_area_m2(diameter_m: float, level_mm: float) -> float:
    h = level_mm / 1000.0
    return math.pi * diameter_m * diameter_m / 4.0 + math.pi * diameter_m * h


def delta_t_kelvin(liquid_temp_c: float) -> float:
    ambient_k = AMBIENT_TEMP_C + 273.15
    liquid_k = liquid_temp_c + 273.15
    return ambient_k - liquid_k


def bog_rate_tph(tank: dict, reading: dict, profile: dict) -> float:
    area = wetted_area_m2(float(tank["diameter_m"]), float(reading["level_mm"]))
    dt = delta_t_kelvin(float(reading["liquid_temp_c"]))
    if dt <= 0:
        return 0.0
    q_w = float(profile["heat_leak_w_m2"]) * area * dt
    kg_per_s = q_w / (float(profile["latent_heat_kj_kg"]) * 1000.0)
    return r3(kg_per_s * 3600.0 / 1000.0)


def maintenance_intervals(tank_id: str, maint: list[dict]) -> list[tuple[datetime, datetime]]:
    out: list[tuple[datetime, datetime]] = []
    for m in maint:
        if m["tank_id"] != tank_id:
            continue
        out.append((ts(m["timestamp_start"]), ts(m["timestamp_end"])))
    return out


def reading_excluded(t: datetime, intervals: list[tuple[datetime, datetime]]) -> bool:
    for start, end in intervals:
        if start <= t < end:
            return True
    return False


def heat_leak_bog(tank: dict, readings: list[dict], maint: list[dict], profile: dict) -> float:
    intervals = maintenance_intervals(tank["tank_id"], maint)
    eligible = []
    for r in readings:
        if r["tank_id"] != tank["tank_id"]:
            continue
        if reading_excluded(ts(r["timestamp"]), intervals):
            continue
        eligible.append(r)
    if not eligible:
        return 0.0
    eligible.sort(key=lambda x: ts(x["timestamp"]))
    if len(eligible) == 1:
        return r3(bog_rate_tph(tank, eligible[0], profile) * 0.001)
    total = 0.0
    for i in range(len(eligible) - 1):
        t0 = ts(eligible[i]["timestamp"])
        t1 = ts(eligible[i + 1]["timestamp"])
        dt_h = (t1 - t0).total_seconds() / 3600.0
        r0 = bog_rate_tph(tank, eligible[i], profile)
        r1 = bog_rate_tph(tank, eligible[i + 1], profile)
        total += (r0 + r1) / 2.0 * dt_h
    return r3(total)


def relief_bog(tank_id: str, transfers: list[dict]) -> float:
    return r3(
        sum(
            float(t["mass_tonnes"])
            for t in transfers
            if t["tank_id"] == tank_id and t["event_type"] == "relief"
        )
    )


def transaction_delta(tank_id: str, transfers: list[dict]) -> float:
    delta = 0.0
    for t in transfers:
        if t["tank_id"] != tank_id:
            continue
        m = float(t["mass_tonnes"])
        if t["event_type"] == "delivery":
            delta += m
        elif t["event_type"] in ("withdrawal", "regas"):
            delta -= m
    return r3(delta)


def snapshots_for_tank(tank_id: str, snaps: list[dict]) -> tuple[dict, dict]:
    mine = [s for s in snaps if s["tank_id"] == tank_id]
    mine.sort(key=lambda x: ts(x["timestamp"]))
    if not mine:
        return {}, {}
    return mine[0], mine[-1]


def violations(profile: dict, imbalance_pct: float, heat: float, relief: float) -> list[str]:
    v: list[str] = []
    if abs(imbalance_pct) > float(profile["allowable_imbalance_pct"]):
        v.append("IMBALANCE_HIGH")
    if heat > 120.0:
        v.append("BOG_RATE_HIGH")
    if relief > 15.0:
        v.append("RELIEF_EXCESSIVE")
    return v


def ref(inp: Path) -> tuple[dict, dict, str]:
    tanks = rcsv(inp / "tanks.csv")
    readings = rcsv(inp / "tank_readings.csv")
    transfers = rcsv(inp / "transfer_events.csv")
    snaps = rcsv(inp / "inventory_snapshots.csv")
    maint = rcsv(inp / "maintenance_events.csv")
    prof = {p["insulation_class"]: p for p in json.loads((inp / "config" / "boiloff-profiles.json").read_text())}
    src = shash(inp)
    st_rows = []
    for tank in sorted(tanks, key=lambda x: x["tank_id"]):
        p = prof[tank["insulation_class"]]
        opening, closing = snapshots_for_tank(tank["tank_id"], snaps)
        heat = heat_leak_bog(tank, readings, maint, p)
        relief = relief_bog(tank["tank_id"], transfers)
        delta = transaction_delta(tank["tank_id"], transfers)
        open_m = float(opening["gauged_mass_tonnes"])
        close_g = float(closing["gauged_mass_tonnes"])
        expected = r3(open_m + delta - heat - relief)
        imbalance = 0.0
        if close_g != 0:
            imbalance = r3((close_g - expected) / close_g * 100.0)
        vio = violations(p, imbalance, heat, relief)
        status = "imbalanced" if vio else "balanced"
        st_rows.append(
            {
                "tank_id": tank["tank_id"],
                "terminal_id": tank["terminal_id"],
                "insulation_class": tank["insulation_class"],
                "status": status,
                "opening_mass_tonnes": open_m,
                "closing_gauged_tonnes": close_g,
                "expected_closing_tonnes": expected,
                "heat_leak_bog_tonnes": heat,
                "relief_bog_tonnes": relief,
                "transaction_delta_tonnes": delta,
                "imbalance_pct": imbalance,
                "violations": vio,
            }
        )
    stage = {"version": "boiloff-stage-v1", "source_hash": src, "tanks": st_rows}
    stage["stage_hash"] = hjson({"version": stage["version"], "source_hash": src, "tanks": st_rows})
    stage["stage_seal"] = seal(stage)
    amap = {
        "IMBALANCE_HIGH": ("investigate_gauging", "inventory imbalance above profile tolerance", "imbalance_pct"),
        "BOG_RATE_HIGH": ("inspect_insulation", "heat-leak boil-off above review threshold", "heat_leak_bog_tonnes"),
        "RELIEF_EXCESSIVE": ("review_relief_valve", "relief vent mass above terminal limit", "relief_bog_tonnes"),
    }
    acts = []
    lines_out = []
    for row in st_rows:
        lines_out.append(
            {
                "tank_id": row["tank_id"],
                "status": row["status"],
                "heat_leak_bog_tonnes": row["heat_leak_bog_tonnes"],
                "relief_bog_tonnes": row["relief_bog_tonnes"],
                "imbalance_pct": row["imbalance_pct"],
                "violations": row["violations"],
            }
        )
        for v in row["violations"]:
            action, reason, field = amap[v]
            acts.append(
                {
                    "tank_id": row["tank_id"],
                    "action": action,
                    "reason": reason,
                    "value": f"{row[field]:.3f}",
                }
            )
    acts.sort(key=lambda x: (x["tank_id"], x["action"]))
    rep = {
        "version": "boiloff-report-v1",
        "source_hash": src,
        "stage_hash": stage["stage_hash"],
        "total_tanks": len(st_rows),
        "balanced_tanks": sum(1 for b in st_rows if b["status"] == "balanced"),
        "imbalanced_tanks": sum(1 for b in st_rows if b["status"] == "imbalanced"),
        "tanks": lines_out,
        "corrective_actions": acts,
    }
    rep["report_hash"] = hjson(rep)
    tsv = "tank_id\taction\treason\tvalue\n" + "".join(
        f"{a['tank_id']}\t{a['action']}\t{a['reason']}\t{a['value']}\n" for a in acts
    )
    return stage, rep, tsv


def _sanitized_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """PATH for the product binary must not include verifier Python tooling."""
    env = os.environ.copy()
    path_parts = [
        p
        for p in env.get("PATH", "").split(":")
        if p
        and "verifier-venv" not in p
        and "verifier-private" not in p
        and p != "/tests"
        and not p.endswith("/tests")
    ]
    env["PATH"] = ":".join(path_parts)
    if extra:
        env.update(extra)
    return env


AGENT_USER = os.environ.get("BOILOFF_RUN_USER", "boiloff")

RAW_INPUT_BASENAMES = (
    "tanks.csv",
    "tank_readings.csv",
    "transfer_events.csv",
    "inventory_snapshots.csv",
    "maintenance_events.csv",
    "boiloff-profiles.json",
)


def _chmod_tree_writable(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    resolved = path.resolve()
    for p in [resolved, *resolved.parents]:
        if p == Path("/"):
            break
        try:
            mode = p.stat().st_mode
            os.chmod(p, mode | 0o777)
        except OSError:
            pass
    for root, dirs, files in os.walk(resolved):
        try:
            os.chmod(root, 0o777)
        except OSError:
            pass
        for name in dirs:
            try:
                os.chmod(Path(root) / name, 0o777)
            except OSError:
                pass
        for name in files:
            try:
                os.chmod(Path(root) / name, 0o666)
            except OSError:
                pass


def _agent_cmd(argv: list[str]) -> list[str]:
    return ["runuser", "-u", AGENT_USER, "--", *argv]


def _trace_line_banned_verifier(line: str) -> bool:
    """Detect opens/execs of verifier trees including relative and /proc aliases."""
    if "open(" not in line and "openat(" not in line and "execve(" not in line:
        return False
    low = line.lower().replace("\\", "/")
    if "execve(" in line and "python" in low:
        return True
    markers = (
        "/tests",
        "verifier-private",
        "verifier-venv",
        "test_outputs.py",
        "tests/test_outputs",
    )
    if "open(" in line or "openat(" in line:
        if any(m in low or m in line for m in markers):
            return True
        if "/proc/" in line and any(m in line for m in ("/tests", "verifier-private", "verifier-venv")):
            return True
    return False


def _trace_line_raw_input(line: str, input_dirs: list[Path]) -> bool:
    if "open(" not in line and "openat(" not in line:
        return False
    candidates: list[str] = [
        "/app/data/tanks.csv",
        "/app/data/tank_readings.csv",
        "/app/data/transfer_events.csv",
        "/app/data/inventory_snapshots.csv",
        "/app/data/maintenance_events.csv",
        "/app/data/config/boiloff-profiles.json",
    ]
    for d in input_dirs:
        for name in RAW_INPUT_BASENAMES:
            rel = d / name if name != "boiloff-profiles.json" else d / "config" / name
            candidates.append(str(rel))
            try:
                candidates.append(str(rel.resolve()))
            except OSError:
                pass
    for c in candidates:
        if c and c in line:
            return True
    if any(b in line for b in RAW_INPUT_BASENAMES) and (
        "/app/data" in line or any(str(d) in line for d in input_dirs)
    ):
        return True
    return False


def _reseal_stage(stage: dict) -> dict:
    payload = {
        "version": stage["version"],
        "source_hash": stage["source_hash"],
        "tanks": stage["tanks"],
    }
    stage = dict(stage)
    stage["stage_hash"] = hjson(payload)
    stage["stage_seal"] = seal(stage)
    return stage


def run(
    inp: Path,
    out: Path,
    state: Path,
    stage_only: bool = False,
    check: bool = True,
    trace_path: Path | None = None,
):
    _chmod_tree_writable(inp.parent)
    _chmod_tree_writable(inp)
    _chmod_tree_writable(out)
    _chmod_tree_writable(state)
    env = _sanitized_env(
        {
            "BOILOFF_INPUT_DIR": str(inp),
            "BOILOFF_OUTPUT_DIR": str(out),
            "BOILOFF_STATE_DIR": str(state),
        }
    )
    if stage_only:
        env["BOILOFF_EXPORT_FROM_STAGE_ONLY"] = "true"
    inner = [str(BIN)]
    if trace_path is not None:
        _chmod_tree_writable(trace_path.parent)
        # Same-user strace avoids Docker seccomp PTRACE_SEIZE denials from strace -u.
        cmd = _agent_cmd(
            [
                "strace",
                "-f",
                "-e",
                "trace=open,openat,execve",
                "-o",
                str(trace_path),
                *inner,
            ]
        )
    else:
        cmd = _agent_cmd(inner)
    return subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, check=check)


def assert_all(inp: Path, out: Path, state: Path) -> dict:
    es, er, et = ref(inp)
    assert json.loads((state / "boiloff-stage.json").read_text()) == es
    assert json.loads((out / "boiloff-report.json").read_text()) == er
    assert (out / "corrective-actions.tsv").read_text() == et
    return er


def test_default_inputs_match_reference(tmp_path: Path) -> None:
    """Bundled LNG tanks must match independent boil-off reference outputs."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    run(inp, out, state)
    rep = assert_all(inp, out, state)
    assert rep["imbalanced_tanks"] >= 2


def test_transfer_and_profile_changes_refresh_hash(tmp_path: Path) -> None:
    """Changing transfer events or profiles must change source and stage hashes."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    run(inp, out, state)
    first = json.loads((out / "boiloff-report.json").read_text())
    transfers = rcsv(inp / "transfer_events.csv")
    transfers.append(
        {
            "tank_id": "TANK-C",
            "timestamp": "2026-06-20T16:30:00Z",
            "event_type": "relief",
            "mass_tonnes": "5.0",
        }
    )
    wcsv(inp / "transfer_events.csv", transfers)
    profiles = json.loads((inp / "config" / "boiloff-profiles.json").read_text())
    profiles[0]["allowable_imbalance_pct"] = 5.0
    (inp / "config" / "boiloff-profiles.json").write_text(json.dumps(profiles, indent=2) + "\n")
    run(inp, out, state)
    second = assert_all(inp, out, state)
    assert first["source_hash"] != second["source_hash"]
    assert first["stage_hash"] != second["stage_hash"]


def test_stage_only_export_and_tamper_rejection(tmp_path: Path) -> None:
    """Stage-only export must work offline and reject tampered boiloff-stage.json."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    run(inp, out, state)
    expected = json.loads((out / "boiloff-report.json").read_text())
    shutil.rmtree(inp)
    shutil.rmtree(out)
    out.mkdir()
    run(inp, out, state, stage_only=True)
    assert json.loads((out / "boiloff-report.json").read_text()) == expected
    p = state / "boiloff-stage.json"
    st = json.loads(p.read_text())
    st["tanks"][0]["heat_leak_bog_tonnes"] = float(st["tanks"][0]["heat_leak_bog_tonnes"]) + 50.0
    p.write_text(json.dumps(st, indent=2) + "\n")
    res = run(inp, out, state, stage_only=True, check=False)
    assert res.returncode != 0 and "stage" in res.stderr.lower()


def test_corrective_action_tsv_maps_violations(tmp_path: Path) -> None:
    """Corrective TSV rows must map violation codes to catalog actions."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    run(inp, out, state)
    assert_all(inp, out, state)
    t = (out / "corrective-actions.tsv").read_text()
    assert "tank_id\taction\treason\tvalue\n" in t
    assert "\tinvestigate_gauging\t" in t or "\treview_relief_valve\t" in t


def test_generated_variant_prevents_hardcoding(tmp_path: Path) -> None:
    """Mutated transfer events must change computed imbalance and compliance."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    transfers = rcsv(inp / "transfer_events.csv")
    for row in transfers:
        if row["tank_id"] == "TANK-A" and row["event_type"] == "withdrawal":
            row["mass_tonnes"] = "800"
    wcsv(inp / "transfer_events.csv", transfers)
    run(inp, out, state)
    rep = assert_all(inp, out, state)
    tank_a = next(b for b in rep["tanks"] if b["tank_id"] == "TANK-A")
    assert tank_a["status"] == "imbalanced" and "IMBALANCE_HIGH" in tank_a["violations"]


def test_maintenance_exclusion_ignores_spike_readings(tmp_path: Path) -> None:
    """High readings during maintenance must not affect heat leak integration."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    run(inp, out, state)
    rep = assert_all(inp, out, state)
    tank_b = next(b for b in rep["tanks"] if b["tank_id"] == "TANK-B")
    assert tank_b["heat_leak_bog_tonnes"] < 4.0
    assert tank_b["status"] == "balanced"


def test_kelvin_correction_affects_heat_leak(tmp_path: Path) -> None:
    """Heat leak integration must use kelvin temperature difference."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    rows = rcsv(inp / "tank_readings.csv")
    for row in rows:
        if row["tank_id"] == "TANK-A":
            row["liquid_temp_c"] = "-140.0"
    wcsv(inp / "tank_readings.csv", rows)
    run(inp, out, state)
    rep = assert_all(inp, out, state)
    tank_a = next(b for b in rep["tanks"] if b["tank_id"] == "TANK-A")
    assert tank_a["heat_leak_bog_tonnes"] > 4.5


def test_source_hash_includes_all_input_files(tmp_path: Path) -> None:
    """source_hash must change when any of the six input files changes."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    run(inp, out, state)
    first_hash = json.loads((state / "boiloff-stage.json").read_text())["source_hash"]
    maint = rcsv(inp / "maintenance_events.csv")
    maint.append(
        {
            "tank_id": "TANK-A",
            "timestamp_start": "2026-06-20T20:00:00Z",
            "timestamp_end": "2026-06-20T21:00:00Z",
            "event_type": "inspection",
        }
    )
    wcsv(inp / "maintenance_events.csv", maint)
    run(inp, out, state)
    second_hash = json.loads((state / "boiloff-stage.json").read_text())["source_hash"]
    assert first_hash != second_hash
    assert second_hash == shash(inp)


def test_stage_seal_matches_recomputed_hash(tmp_path: Path) -> None:
    """stage_seal must match independent seal recomputation."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    run(inp, out, state)
    stage = json.loads((state / "boiloff-stage.json").read_text())
    assert stage["stage_seal"] == seal(stage)


def test_report_hash_excludes_nothing_required(tmp_path: Path) -> None:
    """report_hash must match canonical JSON of full report body."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    run(inp, out, state)
    rep = json.loads((out / "boiloff-report.json").read_text())
    body = {k: v for k, v in rep.items() if k != "report_hash"}
    assert rep["report_hash"] == hjson(body)


def test_tank_c_imbalance_on_bundled_data(tmp_path: Path) -> None:
    """TANK-C must flag IMBALANCE_HIGH on bundled inventory snapshots."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    run(inp, out, state)
    rep = assert_all(inp, out, state)
    tank_c = next(b for b in rep["tanks"] if b["tank_id"] == "TANK-C")
    assert tank_c["status"] == "imbalanced"
    assert "IMBALANCE_HIGH" in tank_c["violations"]


def test_tank_d_relief_excessive_on_bundled_data(tmp_path: Path) -> None:
    """TANK-D economy tank must flag RELIEF_EXCESSIVE on bundled relief events."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    run(inp, out, state)
    rep = assert_all(inp, out, state)
    tank_d = next(b for b in rep["tanks"] if b["tank_id"] == "TANK-D")
    assert tank_d["status"] == "imbalanced"
    assert "RELIEF_EXCESSIVE" in tank_d["violations"]
    assert "TANK-D\treview_relief_valve\t" in (out / "corrective-actions.tsv").read_text()


def test_relief_mass_counted_in_inventory_balance(tmp_path: Path) -> None:
    """Relief vent masses must reduce expected closing inventory."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    run(inp, out, state)
    stage = json.loads((state / "boiloff-stage.json").read_text())
    tank_d = next(t for t in stage["tanks"] if t["tank_id"] == "TANK-D")
    assert tank_d["relief_bog_tonnes"] == 24.5


def test_withdrawal_sign_in_inventory_balance(tmp_path: Path) -> None:
    """Withdrawal masses must subtract from expected closing inventory."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    transfers = [
        t
        for t in rcsv(inp / "transfer_events.csv")
        if not (t["tank_id"] == "TANK-A" and t["event_type"] == "withdrawal")
    ]
    wcsv(inp / "transfer_events.csv", transfers)
    run(inp, out, state)
    stage = json.loads((state / "boiloff-stage.json").read_text())
    tank_a = next(t for t in stage["tanks"] if t["tank_id"] == "TANK-A")
    assert tank_a["transaction_delta_tonnes"] == 400.0


def test_time_weighted_integration_differs_from_plain_mean(tmp_path: Path) -> None:
    """Uneven reading spacing must use trapezoidal heat leak integration."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    rows = [r for r in rcsv(inp / "tank_readings.csv") if r["tank_id"] != "TANK-A"]
    rows.extend(
        [
            {
                "tank_id": "TANK-A",
                "timestamp": "2026-06-20T02:00:00Z",
                "pressure_kpag": "18.5",
                "liquid_temp_c": "-161.2",
                "vapor_temp_c": "-159.8",
                "level_mm": "12500",
            },
            {
                "tank_id": "TANK-A",
                "timestamp": "2026-06-20T09:00:00Z",
                "pressure_kpag": "18.6",
                "liquid_temp_c": "-161.0",
                "vapor_temp_c": "-159.6",
                "level_mm": "20000",
            },
            {
                "tank_id": "TANK-A",
                "timestamp": "2026-06-20T17:00:00Z",
                "pressure_kpag": "19.0",
                "liquid_temp_c": "-160.8",
                "vapor_temp_c": "-159.2",
                "level_mm": "12800",
            },
        ]
    )
    wcsv(inp / "tank_readings.csv", rows)
    snaps = rcsv(inp / "inventory_snapshots.csv")
    for s in snaps:
        if s["tank_id"] == "TANK-A" and s["timestamp"] == "2026-06-20T18:00:00Z":
            s["gauged_mass_tonnes"] = "10100.0"
    wcsv(inp / "inventory_snapshots.csv", snaps)
    run(inp, out, state)
    rep = assert_all(inp, out, state)
    tank_a = next(b for b in rep["tanks"] if b["tank_id"] == "TANK-A")
    tanks = {t["tank_id"]: t for t in rcsv(inp / "tanks.csv")}
    profiles = {p["insulation_class"]: p for p in json.loads((inp / "config" / "boiloff-profiles.json").read_text())}
    tank = tanks["TANK-A"]
    prof = profiles[tank["insulation_class"]]
    spaced = [r for r in rows if r["tank_id"] == "TANK-A"]
    rates = [bog_rate_tph(tank, r, prof) for r in spaced]
    plain_mean = r3(sum(rates) / len(rates))
    span_h = (ts("2026-06-20T17:00:00Z") - ts("2026-06-20T02:00:00Z")).total_seconds() / 3600
    assert tank_a["heat_leak_bog_tonnes"] != r3(plain_mean * span_h)


def test_level_mm_converted_for_wetted_area(tmp_path: Path) -> None:
    """level_mm must be converted to meters for wetted area geometry."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    rows = rcsv(inp / "tank_readings.csv")
    for row in rows:
        if row["tank_id"] == "TANK-B" and row["timestamp"] == "2026-06-20T16:00:00Z":
            row["level_mm"] = "22000"
    wcsv(inp / "tank_readings.csv", rows)
    run(inp, out, state)
    rep = assert_all(inp, out, state)
    tank_b = next(b for b in rep["tanks"] if b["tank_id"] == "TANK-B")
    assert tank_b["heat_leak_bog_tonnes"] > 2.4


def test_stage_only_export_flag(tmp_path: Path) -> None:
    """BOILOFF_EXPORT_FROM_STAGE_ONLY must export without reading input files."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    run(inp, out, state)
    stage_path = state / "boiloff-stage.json"
    stage_bytes = stage_path.read_bytes()
    shutil.rmtree(inp)
    inp.mkdir()
    run(inp, out, state, stage_only=True)
    assert stage_path.read_bytes() == stage_bytes
    assert (out / "boiloff-report.json").exists()


def test_absolute_directory_override(tmp_path: Path) -> None:
    """Reconciler must honor absolute BOILOFF_* directory overrides."""
    inp, out, state = tmp_path / "inputs", tmp_path / "outputs", tmp_path / "states"
    copy_inputs(inp)
    run(inp, out, state)
    assert_all(inp, out, state)


def test_binary_cannot_read_verifier_paths_or_exec_python(tmp_path: Path) -> None:
    """Product binary must not open verifier trees (incl. private copy) or exec Python."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    trace = tmp_path / "strace.log"
    res = run(inp, out, state, trace_path=trace)
    assert res.returncode == 0, res.stderr
    log = trace.read_text(errors="replace")
    for line in log.splitlines():
        if _trace_line_banned_verifier(line):
            raise AssertionError(f"binary must not access verifier/python: {line}")
    assert_all(inp, out, state)


def test_stage_only_uses_divergent_sealed_stage_not_app_data(tmp_path: Path) -> None:
    """Stage-only export must use sealed stage values even when /app/data still matches a prior run."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    run(inp, out, state)
    stage_path = state / "boiloff-stage.json"
    stage = json.loads(stage_path.read_text())
    marker = 777.123
    found = False
    for tank in stage["tanks"]:
        if tank["tank_id"] == "TANK-A":
            tank["heat_leak_bog_tonnes"] = marker
            tank["status"] = "imbalanced"
            if "BOG_RATE_HIGH" not in tank["violations"]:
                tank["violations"] = list(tank["violations"]) + ["BOG_RATE_HIGH"]
            found = True
    assert found
    stage = _reseal_stage(stage)
    stage_path.write_text(json.dumps(stage, indent=2) + "\n")
    os.chmod(stage_path, 0o666)

    # Leave /app/data intact. Point INPUT_DIR at an empty tree so only explicit
    # /app/data (or verifier) cheating could rebuild the default bundled report.
    shutil.rmtree(inp)
    inp.mkdir()
    _chmod_tree_writable(inp)
    shutil.rmtree(out)
    out.mkdir()
    _chmod_tree_writable(out)

    default_from_app = ref(ROOT / "data")[1]
    default_heat = next(t["heat_leak_bog_tonnes"] for t in default_from_app["tanks"] if t["tank_id"] == "TANK-A")
    assert default_heat != marker

    trace = tmp_path / "stage_only.strace"
    res = run(inp, out, state, stage_only=True, trace_path=trace)
    assert res.returncode == 0, res.stderr
    log = trace.read_text(errors="replace")
    for line in log.splitlines():
        if _trace_line_banned_verifier(line):
            raise AssertionError(f"stage-only must not read verifier paths: {line}")
        if _trace_line_raw_input(line, [inp, ROOT / "data"]):
            raise AssertionError(f"stage-only must not read raw inputs: {line}")

    rep = json.loads((out / "boiloff-report.json").read_text())
    tank_a = next(t for t in rep["tanks"] if t["tank_id"] == "TANK-A")
    assert tank_a["heat_leak_bog_tonnes"] == marker
    assert tank_a["heat_leak_bog_tonnes"] != default_heat
    assert "BOG_RATE_HIGH" in tank_a["violations"]
    assert rep["stage_hash"] == stage["stage_hash"]


def test_corrective_actions_empty_array_when_all_balanced(tmp_path: Path) -> None:
    """All-balanced reports must serialize corrective_actions as [] not null."""
    inp, out, state = tmp_path / "i", tmp_path / "o", tmp_path / "s"
    copy_inputs(inp)
    run(inp, out, state)
    stage = json.loads((state / "boiloff-stage.json").read_text())
    for tank in stage["tanks"]:
        tank["status"] = "balanced"
        tank["violations"] = []
        tank["imbalance_pct"] = 0.0
        tank["heat_leak_bog_tonnes"] = 1.0
        tank["relief_bog_tonnes"] = 0.0
    stage = _reseal_stage(stage)
    (state / "boiloff-stage.json").write_text(json.dumps(stage, indent=2) + "\n")
    os.chmod(state / "boiloff-stage.json", 0o666)
    shutil.rmtree(inp)
    inp.mkdir()
    shutil.rmtree(out)
    out.mkdir()
    _chmod_tree_writable(inp)
    _chmod_tree_writable(out)
    run(inp, out, state, stage_only=True)
    rep = json.loads((out / "boiloff-report.json").read_text())
    assert "corrective_actions" in rep
    assert rep["corrective_actions"] == []
    assert isinstance(rep["corrective_actions"], list)
    raw = (out / "boiloff-report.json").read_text()
    assert '"corrective_actions": null' not in raw
    assert '"corrective_actions": []' in raw or '"corrective_actions":[]' in raw
