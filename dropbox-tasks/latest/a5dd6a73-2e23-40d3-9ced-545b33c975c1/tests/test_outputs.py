"""Verifier for immunoflow vaccine lot-wave planner."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

import pytest

LAB_ROOT = "/app/data/immunolab"
LAB = Path(LAB_ROOT)
IMMUNOFLOW = "/app/bin/immunoflow"
GO = "/usr/local/go/bin/go"
ENV = Path("/app/environment")
REF = "/tests/immunoflow_ref.py"
WAVE = 3
OUT = Path("/app/output")
VAR = Path("/app/var")
CACHE = VAR / "immunoflow_plan_cache.json"
SCOPE = VAR / "immunoflow_scopebook.json"
CUSTOMS = VAR / "immunoflow_customs.json"
REMAINDER = VAR / "immunoflow_vialremainder.json"

FIXTURE_INTEGRITY = {
    LAB / "regions.json": None,
    LAB / "lots.json": None,
    LAB / "routes.json": None,
    LAB / "clinics.json": None,
    LAB / "demand.json": None,
}


def _sha256_file(path: Path) -> str:
    proc = subprocess.run(["sha256sum", str(path)], capture_output=True, check=True, text=True)
    return proc.stdout.split()[0]


def _populate_integrity() -> None:
    for key in list(FIXTURE_INTEGRITY):
        FIXTURE_INTEGRITY[key] = _sha256_file(key)


_populate_integrity()


def _ref_plan(wave: int = WAVE) -> dict:
    raw = subprocess.check_output(
        ["python3", REF, "--lab", LAB_ROOT, "plan", "--wave", str(wave)],
        text=True,
    )
    return json.loads(raw)


def _ref_dose(dose1_wave: int = WAVE) -> dict:
    raw = subprocess.check_output(
        ["python3", REF, "--lab", LAB_ROOT, "dose", "--dose1-wave", str(dose1_wave)],
        text=True,
    )
    return json.loads(raw)


def _ref_equity(wave: int = WAVE) -> dict:
    raw = subprocess.check_output(
        ["python3", REF, "--lab", LAB_ROOT, "equity", "--wave", str(wave)],
        text=True,
    )
    return json.loads(raw)


def _ref_pallets(wave: int = WAVE) -> dict:
    raw = subprocess.check_output(
        ["python3", REF, "--lab", LAB_ROOT, "pallets", "--wave", str(wave)],
        text=True,
    )
    return json.loads(raw)


def _ref_customs(wave: int = WAVE) -> dict:
    raw = subprocess.check_output(
        ["python3", REF, "--lab", LAB_ROOT, "customs", "--wave", str(wave)],
        text=True,
    )
    return json.loads(raw)


def _ref_coldchain(wave: int = WAVE) -> dict:
    raw = subprocess.check_output(
        ["python3", REF, "--lab", LAB_ROOT, "coldchain", "--wave", str(wave)],
        text=True,
    )
    return json.loads(raw)


def _ref_infection(wave: int = WAVE) -> dict:
    raw = subprocess.check_output(
        ["python3", REF, "--lab", LAB_ROOT, "infection", "--wave", str(wave)],
        text=True,
    )
    return json.loads(raw)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _rebuild() -> None:
    subprocess.run(
        [GO, "build", "-o", IMMUNOFLOW, "./cmd/immunoflow"],
        cwd=str(ENV),
        check=True,
    )


def _run_pipeline() -> None:
    subprocess.run([IMMUNOFLOW, "bench", "reset"], check=True)
    subprocess.run(
        [IMMUNOFLOW, "plan-wave", "--lab", LAB_ROOT, "--wave", str(WAVE), "--out", str(OUT / "allocation_plan.json")],
        check=True,
    )
    subprocess.run(
        [
            IMMUNOFLOW,
            "bind-lanes",
            "--wave",
            str(WAVE),
            "--plan",
            str(OUT / "allocation_plan.json"),
            "--out",
            str(OUT / "coldchain_audit.json"),
        ],
        check=True,
    )
    subprocess.run([IMMUNOFLOW, "schedule-doses", "--lab", LAB_ROOT, "--dose1-wave", str(WAVE)], check=True)
    subprocess.run(
        [IMMUNOFLOW, "reconcile-equity", "--lab", LAB_ROOT, "--plan", str(OUT / "allocation_plan.json")],
        check=True,
    )
    subprocess.run(
        [
            IMMUNOFLOW,
            "project-infections",
            "--lab",
            LAB_ROOT,
            "--plan",
            str(OUT / "allocation_plan.json"),
        ],
        check=True,
    )


@pytest.fixture(scope="session", autouse=True)
def _session_build() -> None:
    _rebuild()


@pytest.fixture(autouse=True)
def _fresh_run() -> None:
    _run_pipeline()


def test_fixture_integrity() -> None:
    """Bundled immunolab fixtures remain unchanged."""
    for path, digest in FIXTURE_INTEGRITY.items():
        assert _sha256_file(path) == digest


def test_pipeline_outputs_exist() -> None:
    """Canonical wave-3 pipeline emits every public artifact."""
    for name in [
        "allocation_plan.json",
        "shipment_legs.csv",
        "coldchain_audit.json",
        "dose_schedule.json",
        "infection_projection.json",
        "equity_rollup.json",
        "feasibility_report.json",
    ]:
        assert (OUT / name).exists()


def test_shared_fefo_pool_matches_reference() -> None:
    """Shared expiry-ordered pool depletion matches the independent reference plan."""
    ref = _ref_plan()
    got = _load(OUT / "allocation_plan.json")
    assert got["lot_assignments"] == ref["lot_assignments"]
    assert got["plan_digest_hex"] == ref["plan_digest_hex"]
    assert got["equity_met"] == ref["equity_met"]
    assert got["region_coverage"] == ref["region_coverage"]


def test_later_region_sees_depleted_stock() -> None:
    """Later regions cannot redraw doses already consumed by earlier region_id peers."""
    plan = _load(OUT / "allocation_plan.json")
    consumed: dict[str, int] = {}
    for row in plan["lot_assignments"]:
        consumed[row["lot_id"]] = consumed.get(row["lot_id"], 0) + int(row["doses"])
    lots = {row["lot_id"]: int(row["doses"]) for row in json.loads((LAB / "lots.json").read_text(encoding="utf-8"))}
    for lot_id, used in consumed.items():
        assert used <= lots[lot_id]


def test_min_gap_days_applied() -> None:
    """Dose-2 waves honor clinic min_gap_days ceiling math."""
    ref = _ref_dose()
    got = _load(OUT / "dose_schedule.json")
    assert got["schedule"] == ref["schedule"]


def test_reserve_not_counted_delivered() -> None:
    """Equity rollup excludes non-deliverable reserve doses from region totals."""
    ref = _ref_equity()
    got = _load(OUT / "equity_rollup.json")
    assert got["region_delivered"] == ref["region_delivered"]
    assert got["equity_met"] == ref["equity_met"]


def test_coverage_agrees_with_equity_rollup() -> None:
    """Allocation coverage delivered totals agree with equity rollup region_delivered."""
    plan = _load(OUT / "allocation_plan.json")
    equity = _load(OUT / "equity_rollup.json")
    for row in plan["region_coverage"]:
        assert equity["region_delivered"][row["region_id"]] == row["delivered"]


def test_single_temp_band_per_pallet() -> None:
    """Each pallet key groups lots with a single storage temperature band."""
    ref = _ref_pallets()
    assert ref["ok"] is True
    got = _load(OUT / "coldchain_audit.json")["pallets"]
    assert got == ref["pallets"]
    rows = list(csv.DictReader((OUT / "shipment_legs.csv").open(encoding="utf-8")))
    lot_band = {row["lot_id"]: row["temp_band"] for row in rows}
    for lot_ids in got.values():
        bands = {lot_band[lot_id] for lot_id in lot_ids}
        assert len(bands) == 1


def test_inspect_generation_filter() -> None:
    """Inspect returns an empty plan when generation does not match cache."""
    scope = _load(SCOPE)
    inspected = json.loads(
        subprocess.check_output([IMMUNOFLOW, "inspect", "--generation", "999"], text=True)
    )
    assert inspected["wave"] == 0
    assert inspected.get("lot_assignments") in ([], None)
    cache = _load(CACHE)
    assert cache["generation"] == scope["generation"]


def test_inspect_matches_disk_for_current_generation() -> None:
    """Inspect with live generation mirrors the on-disk allocation plan."""
    scope = _load(SCOPE)
    inspected = json.loads(
        subprocess.check_output([IMMUNOFLOW, "inspect", "--generation", str(scope["generation"])], text=True)
    )
    disk = _load(OUT / "allocation_plan.json")
    assert inspected["wave"] == disk["wave"]
    assert inspected["lot_assignments"] == disk["lot_assignments"]
    assert inspected["plan_digest_hex"] == disk["plan_digest_hex"]


def test_lane_hours_accumulate() -> None:
    """Scopebook lane hours grow across spoilage replan invocations."""
    first = _load(SCOPE)["total_lane_hours"]
    subprocess.run([IMMUNOFLOW, "spoilage-replan", "--lab", LAB_ROOT, "--wave", str(WAVE)], check=True)
    second = _load(SCOPE)["total_lane_hours"]
    assert second > first


def test_customs_assignment_scoped() -> None:
    """Customs delay accrual increases by assignment-scoped route delays only."""
    before = _load(CUSTOMS)["total_delay_days"]
    ref_delta = _ref_customs()["delta"]
    subprocess.run(
        [IMMUNOFLOW, "plan-wave", "--lab", LAB_ROOT, "--wave", str(WAVE), "--out", str(OUT / "allocation_plan.json")],
        check=True,
    )
    after = _load(CUSTOMS)["total_delay_days"]
    assert after - before == ref_delta


def test_shipment_legs_cover_assignments() -> None:
    """Shipment CSV includes one leg row per lot assignment with the contract columns."""
    plan = _load(OUT / "allocation_plan.json")
    with (OUT / "shipment_legs.csv").open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == ["leg_id", "region_id", "lot_id", "depart_day", "arrive_day", "temp_band"]
        rows = list(reader)
    assert len(rows) == len(plan["lot_assignments"])
    plan_pairs = {(row["region_id"], row["lot_id"]) for row in plan["lot_assignments"]}
    csv_pairs = {(row["region_id"], row["lot_id"]) for row in rows}
    assert plan_pairs == csv_pairs
    routes = {row["region_id"]: row for row in json.loads((LAB / "routes.json").read_text(encoding="utf-8"))}
    lots = {row["lot_id"]: row for row in json.loads((LAB / "lots.json").read_text(encoding="utf-8"))}
    for row in rows:
        route = routes[row["region_id"]]
        lot = lots[row["lot_id"]]
        assert row["leg_id"] == route["leg_id"]
        assert row["depart_day"] == str(route["depart_day"])
        assert row["arrive_day"] == str(route["arrive_day"])
        assert row["temp_band"] == lot["temp_band"]


def test_coldchain_lane_digest_and_spoilage_rows() -> None:
    """Cold-chain audit carries spoilage_rows and a pallets-derived lane_digest_hex."""
    ref = _ref_coldchain()
    got = _load(OUT / "coldchain_audit.json")
    assert got["wave"] == WAVE
    assert got["spoilage_rows"] == ref["spoilage_rows"]
    assert got["pallets"] == ref["pallets"]
    assert got["lane_digest_hex"] == ref["lane_digest_hex"]


def test_infection_projection_uses_gap_weeks() -> None:
    """Projected cases scale uncovered demand by clinic gap weeks."""
    ref = _ref_infection()
    got = _load(OUT / "infection_projection.json")
    assert got["rows"] == ref["rows"]


def test_feasibility_tracks_equity() -> None:
    """Feasibility report feasible flag tracks equity_met from the plan."""
    plan = _load(OUT / "allocation_plan.json")
    report = _load(OUT / "feasibility_report.json")
    assert report["feasible"] == plan["equity_met"]
    equity = _load(OUT / "equity_rollup.json")
    assert report["feasible"] == equity["equity_met"]


def test_expiry_mutation_changes_first_lot() -> None:
    """Lowering an early-expiry lot reshuffles shared FEFO consumption order."""
    lot_path = LAB / "lots.json"
    backup = lot_path.read_text(encoding="utf-8")
    lots = json.loads(backup)
    lots[2]["expiry_day"] = 5
    lot_path.write_text(json.dumps(lots, indent=2) + "\n", encoding="utf-8")
    try:
        _run_pipeline()
        ref = _ref_plan()
        got = _load(OUT / "allocation_plan.json")
        assert got["lot_assignments"][0]["lot_id"] == ref["lot_assignments"][0]["lot_id"]
        assert got["plan_digest_hex"] == ref["plan_digest_hex"]
        assert got["lot_assignments"] == ref["lot_assignments"]
    finally:
        lot_path.write_text(backup, encoding="utf-8")


def test_remainder_affects_second_wave() -> None:
    """Vial remainder carried across plan-wave runs without reset changes the digest."""
    first = _load(OUT / "allocation_plan.json")["plan_digest_hex"]
    rem_before = _load(REMAINDER)
    assert any(int(v) > 0 for v in rem_before.values())
    subprocess.run(
        [IMMUNOFLOW, "plan-wave", "--lab", LAB_ROOT, "--wave", str(WAVE), "--out", str(OUT / "allocation_plan.json")],
        check=True,
    )
    second = _load(OUT / "allocation_plan.json")["plan_digest_hex"]
    assert second != first
