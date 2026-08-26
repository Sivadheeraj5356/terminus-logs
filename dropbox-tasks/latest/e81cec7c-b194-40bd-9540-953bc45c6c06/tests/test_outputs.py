"""Verifier for cpp-cryogenic-storage-readiness-assessor.

Independent reference (cryo_ref) recomputes inventory metrics, placement
assignment, certificates, digests, and ledger keys without C++ internals.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cryo_ref as ref

APP = Path("/app")
BIN = APP / "bin" / "cryoready"
FIX = APP / "fixtures"
OUT = APP / "output"
TOOLS = APP / "tools"
STATE = APP / "state"
LEDGER = APP / "var" / "cryoready-ledger.json"
HIDDEN = Path(__file__).resolve().parent / "hidden"


def _run(cmd: list[str], check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(cmd, check=check, capture_output=True, text=True, env=merged)


def _run_id() -> str:
    return uuid.uuid4().hex[:8]


def rebuild() -> None:
    _run(["bash", str(TOOLS / "build.sh")])


def _clear_dir_contents(directory: Path) -> None:
    """Remove files and subdirectories under directory (directory itself kept)."""
    if not directory.exists():
        return
    for path in directory.iterdir():
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)


def reset_workspace(tmp_path: Path | None = None) -> dict:
    if LEDGER.exists():
        LEDGER.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.mkdir(parents=True, exist_ok=True)
    _clear_dir_contents(STATE)
    _clear_dir_contents(OUT)
    (APP / "var").mkdir(parents=True, exist_ok=True)
    env = {}
    if tmp_path is not None:
        state_dir = tmp_path / "state"
        ledger = tmp_path / "ledger.json"
        state_dir.mkdir(parents=True, exist_ok=True)
        env["CRYOREADY_STATE_DIR"] = str(state_dir)
        env["CRYOREADY_LEDGER_PATH"] = str(ledger)
    return env


def run_inventory(facility: Path, catalog: Path, maintenance: Path, env: dict) -> dict:
    _run(
        [
            str(BIN),
            "inventory",
            "--facility",
            str(facility),
            "--catalog",
            str(catalog),
            "--maintenance",
            str(maintenance),
        ],
        env=env,
    )
    stage_path = Path(env.get("CRYOREADY_STATE_DIR", str(STATE))) / "inventory-stage.json"
    return json.loads(stage_path.read_text(encoding="utf-8"))


def run_assess(
    facility: Path,
    catalog: Path,
    maintenance: Path,
    report_out: Path,
    cert_out: Path,
    env: dict,
    check: bool = True,
) -> subprocess.CompletedProcess:
    report_out.parent.mkdir(parents=True, exist_ok=True)
    return _run(
        [
            str(BIN),
            "assess",
            "--facility",
            str(facility),
            "--catalog",
            str(catalog),
            "--maintenance",
            str(maintenance),
            "--output-report",
            str(report_out),
            "--output-certificate",
            str(cert_out),
        ],
        check=check,
        env=env,
    )


@pytest.fixture(scope="module", autouse=True)
def _build_once() -> None:
    rebuild()


def test_bay_alpha_inventory_matches_reference(tmp_path: Path) -> None:
    env = reset_workspace(tmp_path)
    facility = FIX / "facility/bay-alpha.json"
    catalog = FIX / "catalog/equipment.json"
    maintenance = FIX / "maintenance/bay-alpha.json"
    got = run_inventory(facility, catalog, maintenance, env)
    expect = ref.build_inventory_stage(facility, catalog, maintenance)
    assert got["facility_digest"] == expect["facility_digest"]
    assert got["catalog_digest"] == expect["catalog_digest"]
    assert got["maintenance_digest"] == expect["maintenance_digest"]
    assert got["inventory_digest"] == expect["inventory_digest"]
    assert got["vessels"] == expect["vessels"]


def test_bay_alpha_assess_report_and_certificate(tmp_path: Path) -> None:
    env = reset_workspace(tmp_path)
    facility = FIX / "facility/bay-alpha.json"
    catalog = FIX / "catalog/equipment.json"
    maintenance = FIX / "maintenance/bay-alpha.json"
    stage = run_inventory(facility, catalog, maintenance, env)
    report_out = tmp_path / "report.json"
    cert_out = tmp_path / "cert.json"
    run_assess(facility, catalog, maintenance, report_out, cert_out, env)
    got_report = json.loads(report_out.read_text(encoding="utf-8"))
    got_cert = json.loads(cert_out.read_text(encoding="utf-8"))
    expect_report = ref.build_readiness_report(facility, catalog, maintenance, stage)
    expect_cert = ref.build_certificate(expect_report)
    assert got_report["placements"] == expect_report["placements"]
    assert got_report["ready_vessel_count"] == expect_report["ready_vessel_count"]
    assert got_report["blocked_vessel_count"] == expect_report["blocked_vessel_count"]
    assert got_report["satisfied_placement_count"] == expect_report["satisfied_placement_count"]
    assert got_report["report_digest"] == expect_report["report_digest"]
    assert got_cert == expect_cert


def test_maintenance_boundary_half_open(tmp_path: Path) -> None:
    """Epoch equal to window end_unix must not block (half-open)."""
    env = reset_workspace(tmp_path)
    facility = FIX / "facility/bay-alpha.json"
    catalog = FIX / "catalog/equipment.json"
    maintenance = FIX / "maintenance/bay-alpha.json"
    stage = run_inventory(facility, catalog, maintenance, env)
    dw01 = next(v for v in stage["vessels"] if v["vessel_id"] == "DW-01")
    assert "in_maintenance" not in dw01["reasons"]


def test_pressure_uses_absolute_mawp(tmp_path: Path) -> None:
    env = reset_workspace(tmp_path)
    facility = FIX / "facility/bay-alpha.json"
    catalog = FIX / "catalog/equipment.json"
    maintenance = FIX / "maintenance/bay-alpha.json"
    stage = run_inventory(facility, catalog, maintenance, env)
    dw02 = next(v for v in stage["vessels"] if v["vessel_id"] == "DW-02")
    assert "pressure_exceeds_mawp" in dw02["reasons"]
    assert dw02["ready"] is False


def test_sensor_cal_expired_at_exact_epoch(tmp_path: Path) -> None:
    env = reset_workspace(tmp_path)
    facility = FIX / "facility/bay-alpha.json"
    catalog = FIX / "catalog/equipment.json"
    maintenance = FIX / "maintenance/bay-alpha.json"
    stage = run_inventory(facility, catalog, maintenance, env)
    dw03 = next(v for v in stage["vessels"] if v["vessel_id"] == "DW-03")
    assert "sensor_cal_expired" in dw03["reasons"]


def test_fill_fraction_uses_usable_capacity(tmp_path: Path) -> None:
    env = reset_workspace(tmp_path)
    facility = FIX / "facility/bay-alpha.json"
    catalog = FIX / "catalog/equipment.json"
    maintenance = FIX / "maintenance/bay-alpha.json"
    stage = run_inventory(facility, catalog, maintenance, env)
    dw01 = next(v for v in stage["vessels"] if v["vessel_id"] == "DW-01")
    # 70 / 90 usable, not 70 / 100 gross
    assert abs(dw01["fill_fraction"] - (70.0 / 90.0)) < 1e-6


def test_hold_hours_applies_reserve(tmp_path: Path) -> None:
    env = reset_workspace(tmp_path)
    facility = FIX / "facility/bay-alpha.json"
    catalog = FIX / "catalog/equipment.json"
    maintenance = FIX / "maintenance/bay-alpha.json"
    stage = run_inventory(facility, catalog, maintenance, env)
    dw04 = next(v for v in stage["vessels"] if v["vessel_id"] == "DW-04")
    # usable 52, reserve 0.12*52=6.24, remaining 40-6.24=33.76, /0.8*24
    expect = ref.round6(((40.0 - 52.0 * 0.12) / 0.8) * 24.0)
    assert abs(dw04["hold_hours"] - expect) < 1e-6


def test_lhe_specimen_not_compatible_with_ln2(tmp_path: Path) -> None:
    env = reset_workspace(tmp_path)
    facility = FIX / "facility/bay-alpha.json"
    catalog = FIX / "catalog/equipment.json"
    maintenance = FIX / "maintenance/bay-alpha.json"
    run_inventory(facility, catalog, maintenance, env)
    report_out = tmp_path / "report.json"
    cert_out = tmp_path / "cert.json"
    run_assess(facility, catalog, maintenance, report_out, cert_out, env)
    report = json.loads(report_out.read_text(encoding="utf-8"))
    lhe_b = next(p for p in report["placements"] if p["request_id"] == "REQ-LHe-B")
    # preferred DW-01 is LN2; must not accept as compatible
    if lhe_b["assigned_vessel_id"] == "DW-01":
        pytest.fail("LHe specimen incorrectly assigned to LN2 vessel DW-01")
    assert lhe_b["assigned_vessel_id"] == "DW-04"
    assert lhe_b["satisfied"] is True


def test_preferred_ineligible_requires_eligibility(tmp_path: Path) -> None:
    env = reset_workspace(tmp_path)
    facility = FIX / "facility/bay-alpha.json"
    catalog = FIX / "catalog/equipment.json"
    maintenance = FIX / "maintenance/bay-alpha.json"
    stage = run_inventory(facility, catalog, maintenance, env)
    report_out = tmp_path / "report.json"
    cert_out = tmp_path / "cert.json"
    run_assess(facility, catalog, maintenance, report_out, cert_out, env)
    got = json.loads(report_out.read_text(encoding="utf-8"))
    expect = ref.build_readiness_report(facility, catalog, maintenance, stage)
    ln2 = next(p for p in got["placements"] if p["request_id"] == "REQ-LN2-A")
    exp = next(p for p in expect["placements"] if p["request_id"] == "REQ-LN2-A")
    assert ln2 == exp


def test_certificate_ok_requires_all_placements(tmp_path: Path) -> None:
    env = reset_workspace(tmp_path)
    catalog = FIX / "catalog/equipment.json"
    maintenance = FIX / "maintenance/bay-alpha.json"
    data = ref.deep_copy_json(FIX / "facility/bay-alpha.json")
    data["placement_requests"].append(
        {
            "request_id": "REQ-IMPOSSIBLE",
            "specimen_class": "LHe",
            "min_hold_hours": 100000.0,
            "preferred_vessel_id": "",
        }
    )
    facility = tmp_path / "facility-impossible.json"
    facility.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    stage = run_inventory(facility, catalog, maintenance, env)
    report_out = tmp_path / "report.json"
    cert_out = tmp_path / "cert.json"
    run_assess(facility, catalog, maintenance, report_out, cert_out, env)
    cert = json.loads(cert_out.read_text(encoding="utf-8"))
    expect = ref.build_certificate(ref.build_readiness_report(facility, catalog, maintenance, stage))
    assert expect["certificate_ok"] is False
    assert cert["certificate_ok"] is False
    assert cert["all_placements_satisfied"] is False


def test_assess_requires_inventory_stage(tmp_path: Path) -> None:
    env = reset_workspace(tmp_path)
    facility = FIX / "facility/bay-alpha.json"
    catalog = FIX / "catalog/equipment.json"
    maintenance = FIX / "maintenance/bay-alpha.json"
    report_out = tmp_path / "report.json"
    cert_out = tmp_path / "cert.json"
    proc = run_assess(facility, catalog, maintenance, report_out, cert_out, env, check=False)
    assert proc.returncode == 2
    assert "inventory" in (proc.stderr + proc.stdout).lower()


def test_stale_inventory_rejected(tmp_path: Path) -> None:
    env = reset_workspace(tmp_path)
    facility = FIX / "facility/bay-alpha.json"
    catalog = FIX / "catalog/equipment.json"
    maintenance = FIX / "maintenance/bay-alpha.json"
    run_inventory(facility, catalog, maintenance, env)
    mutated = tmp_path / "facility-mut.json"
    ref.mutate_facility(facility, mutated, bump=17)
    report_out = tmp_path / "report.json"
    cert_out = tmp_path / "cert.json"
    proc = run_assess(mutated, catalog, maintenance, report_out, cert_out, env, check=False)
    assert proc.returncode == 2
    assert "inventory" in (proc.stderr + proc.stdout).lower()


def test_mutated_facility_roundtrip(tmp_path: Path) -> None:
    env = reset_workspace(tmp_path)
    run_id = _run_id()
    bump = (int(run_id[:4], 16) % 20) + 1
    facility = ref.mutate_facility(FIX / "facility/bay-alpha.json", tmp_path / f"fac-{run_id}.json", bump)
    catalog = FIX / "catalog/equipment.json"
    maintenance = FIX / "maintenance/bay-alpha.json"
    stage = run_inventory(facility, catalog, maintenance, env)
    expect_stage = ref.build_inventory_stage(facility, catalog, maintenance)
    assert stage["inventory_digest"] == expect_stage["inventory_digest"]
    report_out = tmp_path / "report.json"
    cert_out = tmp_path / "cert.json"
    run_assess(facility, catalog, maintenance, report_out, cert_out, env)
    got = json.loads(report_out.read_text(encoding="utf-8"))
    expect = ref.build_readiness_report(facility, catalog, maintenance, expect_stage)
    assert got["report_digest"] == expect["report_digest"]
    assert got["placements"] == expect["placements"]


def test_ledger_composite_key_and_counters(tmp_path: Path) -> None:
    env = reset_workspace(tmp_path)
    facility = FIX / "facility/bay-alpha.json"
    catalog = FIX / "catalog/equipment.json"
    maintenance = FIX / "maintenance/bay-alpha.json"
    stage = run_inventory(facility, catalog, maintenance, env)
    report_out = tmp_path / "report.json"
    cert_out = tmp_path / "cert.json"
    run_assess(facility, catalog, maintenance, report_out, cert_out, env)
    run_assess(facility, catalog, maintenance, report_out, cert_out, env)
    ledger_path = Path(env["CRYOREADY_LEDGER_PATH"])
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    key = ref.assess_ledger_key(
        stage["facility_digest"],
        stage["catalog_digest"],
        stage["maintenance_digest"],
    )
    assert key in ledger["entries"]
    entry = ledger["entries"][key]
    assert entry["inventory_runs"] == 1
    assert entry["assess_runs"] == 2
    assert ledger["write_seq"] == 3


def test_ledger_salvages_truncated_prefix(tmp_path: Path) -> None:
    env = reset_workspace(tmp_path)
    facility = FIX / "facility/bay-alpha.json"
    catalog = FIX / "catalog/equipment.json"
    maintenance = FIX / "maintenance/bay-alpha.json"
    stage = run_inventory(facility, catalog, maintenance, env)
    ledger_path = Path(env["CRYOREADY_LEDGER_PATH"])
    good = json.loads(ledger_path.read_text(encoding="utf-8"))
    # Append corruption after a complete JSON document so salvage can recover the prefix.
    truncated = json.dumps(good, indent=2) + "\n@@@TRUNCATED_TAIL"
    ledger_path.write_text(truncated, encoding="utf-8")
    report_out = tmp_path / "report.json"
    cert_out = tmp_path / "cert.json"
    run_assess(facility, catalog, maintenance, report_out, cert_out, env)
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    key = ref.assess_ledger_key(
        stage["facility_digest"],
        stage["catalog_digest"],
        stage["maintenance_digest"],
    )
    assert key in ledger["entries"]
    assert ledger["entries"][key]["inventory_runs"] >= 1
    assert ledger["entries"][key]["assess_runs"] >= 1


def test_hidden_facility_gamma(tmp_path: Path) -> None:
    env = reset_workspace(tmp_path)
    facility = HIDDEN / "facility-gamma.json"
    catalog = HIDDEN / "catalog-gamma.json"
    maintenance = HIDDEN / "maintenance-gamma.json"
    assert facility.exists()
    stage = run_inventory(facility, catalog, maintenance, env)
    expect_stage = ref.build_inventory_stage(facility, catalog, maintenance)
    assert stage["vessels"] == expect_stage["vessels"]
    report_out = tmp_path / "report.json"
    cert_out = tmp_path / "cert.json"
    run_assess(facility, catalog, maintenance, report_out, cert_out, env)
    got = json.loads(report_out.read_text(encoding="utf-8"))
    expect = ref.build_readiness_report(facility, catalog, maintenance, expect_stage)
    assert got["placements"] == expect["placements"]
    cert = json.loads(cert_out.read_text(encoding="utf-8"))
    assert cert == ref.build_certificate(expect)


def test_hidden_facility_delta_pressure_edge(tmp_path: Path) -> None:
    env = reset_workspace(tmp_path)
    facility = HIDDEN / "facility-delta.json"
    catalog = HIDDEN / "catalog-gamma.json"
    maintenance = HIDDEN / "maintenance-delta.json"
    stage = run_inventory(facility, catalog, maintenance, env)
    expect = ref.build_inventory_stage(facility, catalog, maintenance)
    assert stage["inventory_digest"] == expect["inventory_digest"]
    for row, exp in zip(stage["vessels"], expect["vessels"], strict=True):
        assert row["ready"] == exp["ready"]
        assert row["reasons"] == exp["reasons"]
