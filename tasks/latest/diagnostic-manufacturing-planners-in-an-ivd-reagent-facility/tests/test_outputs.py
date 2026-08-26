"""Verifier for reagent-lot-blend-feasibility-witness."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

APP = Path("/app")
INPUT_DIR = APP / "input"
STATE = APP / "state"
OUTPUT = APP / "output"
JAR = APP / "target" / "blendcert.jar"
BUNDLED = APP / "bundled-fixtures" / "input"
VERIFIER_FIXTURES = Path("/opt/verifier-fixtures")
if not VERIFIER_FIXTURES.is_dir():
    VERIFIER_FIXTURES = Path(__file__).resolve().parent / "verifier-fixtures"

PATH_BLEND_MODEL = "/app/state/blend-model.json"
PATH_LOT_INVENTORY = "/app/state/lot-inventory.json"
PATH_ALLOCATION = "/app/state/allocation.json"
PATH_DUAL_CERTIFICATE = "/app/state/dual-certificate.json"
PATH_BLEND_LEDGER = "/app/output/blend-ledger.json"
PATH_BLEND_FEASIBILITY_CERT = "/app/output/blend-feasibility-cert.json"
PATH_GREEDY_PREVIEW = "/app/state/greedy-preview.json"

STEPS = 101
EPS = 1e-6
DUAL_EPS_RATIO = 1e-4
TOL = 1e-6

SPEC01_COST = 80.0
SPEC02_COST = 89.356436
SPEC03_COST = 91.287129
COST_TOL = 1e-3
SHADOW_TOL = 1e-3


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), capture_output=True, text=True, check=False)


def _blendcert(sub: str) -> subprocess.CompletedProcess[str]:
    if Path("/usr/sbin/runuser").is_file():
        return _run("runuser", "-u", "agent", "--", "java", "-jar", str(JAR), sub)
    return _run("java", "-jar", str(JAR), sub)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _artifact_file_digest(path: Path) -> str:
    """SHA-256 of exact on-disk state file bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _round6(value: float) -> float:
    return round(value * 1_000_000) / 1_000_000


def _sorted_analytes(spec: dict[str, Any]) -> list[str]:
    return sorted(spec["bands"].keys())


def _concentrations_feasible(spec: dict[str, Any], concentrations: dict[str, float]) -> bool:
    for analyte, band in spec["bands"].items():
        lower = float(band["lower"])
        upper = float(band["upper"])
        achieved = concentrations.get(analyte, 0.0)
        if achieved < lower - EPS or achieved > upper + EPS:
            return False
    return True


def _evaluate_fractions(
    lots: list[dict[str, Any]],
    spec: dict[str, Any],
    volume: float,
    fracs: list[int],
) -> dict[str, Any] | None:
    n = len(lots)
    amounts = [(f / STEPS) * volume for f in fracs]
    for i in range(n):
        if amounts[i] > float(lots[i]["available_ml"]) + EPS:
            return None
    analytes = _sorted_analytes(spec)
    concentrations: dict[str, float] = {}
    for analyte in analytes:
        total = sum(amounts[i] * float(lots[i]["assays"][analyte]) for i in range(n))
        concentrations[analyte] = total / volume
    if not _concentrations_feasible(spec, concentrations):
        return None
    cost = sum(amounts[i] * float(lots[i]["cost_per_ml"]) for i in range(n))
    lot_amounts = {lots[i]["lot_id"]: amounts[i] for i in range(n)}
    return {
        "feasible": True,
        "total_cost": cost,
        "lot_amounts_ml": lot_amounts,
        "concentrations": concentrations,
    }


def _enumerate_all(
    lots: list[dict[str, Any]],
    spec: dict[str, Any],
    volume: float,
    n: int,
    fracs: list[int],
    depth: int,
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    if depth == n - 1:
        partial = sum(fracs[: n - 1])
        if partial > STEPS:
            return None
        fracs[n - 1] = STEPS - partial
        return _evaluate_fractions(lots, spec, volume, fracs)
    for frac in range(STEPS + 1):
        fracs[depth] = frac
        if sum(fracs[: depth + 1]) > STEPS:
            continue
        candidate = _enumerate_all(lots, spec, volume, n, fracs, depth + 1)
        if candidate is not None and (
            best is None or candidate["total_cost"] < best["total_cost"] - EPS
        ):
            best = candidate
    return best


def reference_blend_solve(
    lots: list[dict[str, Any]], spec: dict[str, Any], volume: float
) -> dict[str, Any]:
    n = len(lots)
    if n == 0 or n > 4:
        return {
            "feasible": False,
            "total_cost": 0.0,
            "lot_amounts_ml": {},
            "concentrations": {},
        }
    fracs = [0] * n
    result = _enumerate_all(lots, spec, volume, n, fracs, 0)
    if result is None:
        return {
            "feasible": False,
            "total_cost": 0.0,
            "lot_amounts_ml": {},
            "concentrations": {},
        }
    return result


def reference_sort_specs(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(specs, key=lambda row: (row["priority"], row["spec_id"]))


def reference_bind_model(
    lots_root: dict[str, Any], specs_root: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": "blend-model/1",
        "batch_generation": lots_root["batch_generation"],
        "target_volume_ml": lots_root["target_volume_ml"],
        "lots": copy.deepcopy(lots_root["lots"]),
        "specifications": reference_sort_specs(specs_root["specifications"]),
        "source_lots": "/app/input/lots.json",
        "source_specs": "/app/input/specs.json",
    }


def reference_lot_inventory(lots_root: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "lot-inventory/1",
        "batch_generation": lots_root["batch_generation"],
        "lots": [
            {"lot_id": lot["lot_id"], "remaining_ml": lot["available_ml"]}
            for lot in lots_root["lots"]
        ],
    }


def _debit_working_lots(
    lots_working: list[dict[str, Any]], lot_amounts_ml: dict[str, Any]
) -> None:
    for lot_id, amount in lot_amounts_ml.items():
        for lot in lots_working:
            if lot["lot_id"] == lot_id:
                lot["available_ml"] = float(lot["available_ml"]) - float(amount)


def _perturb_lot_avail(
    lots: list[dict[str, Any]], lot_id: str, delta: float
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for lot in lots:
        row = copy.deepcopy(lot)
        if row["lot_id"] == lot_id:
            row["available_ml"] = float(row["available_ml"]) + delta
        out.append(row)
    return out


def _perturb_band(
    spec: dict[str, Any], analyte: str, lower: float, upper: float
) -> dict[str, Any]:
    copy_spec = copy.deepcopy(spec)
    copy_spec["bands"][analyte] = {"lower": lower, "upper": upper}
    return copy_spec


def reference_shadow_prices(
    lots: list[dict[str, Any]],
    spec: dict[str, Any],
    volume: float,
    solution_row: dict[str, Any],
) -> dict[str, Any]:
    base_cost = float(solution_row["total_cost"])
    eps = max(1e-4, volume * DUAL_EPS_RATIO)

    vol_up = reference_blend_solve(lots, spec, volume + eps)
    volume_dual = (
        (vol_up["total_cost"] - base_cost) / eps if vol_up.get("feasible") else 0.0
    )
    prices: dict[str, Any] = {"volume": _round6(volume_dual)}

    lot_duals: dict[str, float] = {}
    for lot in lots:
        lot_id = lot["lot_id"]
        amount = float(solution_row["lot_amounts_ml"][lot_id])
        avail = float(lot["available_ml"])
        dual = 0.0
        if amount >= avail - 1e-6:
            relaxed = reference_blend_solve(_perturb_lot_avail(lots, lot_id, eps), spec, volume)
            if relaxed.get("feasible"):
                dual = max(0.0, (base_cost - relaxed["total_cost"]) / eps)
        lot_duals[lot_id] = _round6(dual)
    prices["lots"] = lot_duals

    lower_duals: dict[str, float] = {}
    upper_duals: dict[str, float] = {}
    concentrations = solution_row["concentrations"]
    for analyte, band in spec["bands"].items():
        lower = float(band["lower"])
        upper = float(band["upper"])
        conc = float(concentrations[analyte])

        lower_dual = 0.0
        if conc <= lower + 1e-6:
            tightened = reference_blend_solve(
                lots, _perturb_band(spec, analyte, lower + eps, upper), volume
            )
            if tightened.get("feasible"):
                lower_dual = max(0.0, (tightened["total_cost"] - base_cost) / eps)
        lower_duals[analyte] = _round6(lower_dual)

        upper_dual = 0.0
        if conc >= upper - 1e-6:
            relaxed_band = reference_blend_solve(
                lots, _perturb_band(spec, analyte, lower, upper + eps), volume
            )
            if relaxed_band.get("feasible"):
                upper_dual = max(0.0, (base_cost - relaxed_band["total_cost"]) / eps)
        upper_duals[analyte] = _round6(upper_dual)

    prices["analytes_lower"] = lower_duals
    prices["analytes_upper"] = upper_duals
    return prices


def reference_gap_bound(
    solution_row: dict[str, Any],
    shadow_prices: dict[str, Any],
    lots: list[dict[str, Any]],
    spec: dict[str, Any],
) -> float:
    gap = 0.0
    for lot in lots:
        lot_id = lot["lot_id"]
        slack = float(lot["available_ml"]) - float(solution_row["lot_amounts_ml"][lot_id])
        dual = float(shadow_prices["lots"][lot_id])
        if slack > TOL and dual > TOL:
            gap += slack * dual

    concentrations = solution_row["concentrations"]
    for analyte, band in spec["bands"].items():
        lower = float(band["lower"])
        upper = float(band["upper"])
        conc = float(concentrations[analyte])
        lower_slack = conc - lower
        upper_slack = upper - conc
        lower_dual = float(shadow_prices["analytes_lower"][analyte])
        upper_dual = float(shadow_prices["analytes_upper"][analyte])
        if lower_slack > TOL and lower_dual > TOL:
            gap += lower_slack * lower_dual
        if upper_slack > TOL and upper_dual > TOL:
            gap += upper_slack * upper_dual
    return gap


def _solution_row_from_result(
    spec: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "spec_id": spec["spec_id"],
        "priority": spec["priority"],
    }
    if result.get("feasible"):
        row["feasible"] = True
        row["total_cost"] = _round6(result["total_cost"])
        row["lot_amounts_ml"] = {
            lot_id: _round6(amount) for lot_id, amount in result["lot_amounts_ml"].items()
        }
        row["concentrations"] = {
            analyte: _round6(value) for analyte, value in result["concentrations"].items()
        }
    else:
        row["feasible"] = False
        row["total_cost"] = 0.0
        row["lot_amounts_ml"] = {}
        row["concentrations"] = {}
    return row


def reference_solve_outputs(model: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    lots_working = copy.deepcopy(model["lots"])
    for lot in lots_working:
        lot["available_ml"] = float(lot["available_ml"])
    volume = float(model["target_volume_ml"])
    solutions: list[dict[str, Any]] = []
    ledger_entries: list[dict[str, Any]] = []
    for spec in model["specifications"]:
        result = reference_blend_solve(lots_working, spec, volume)
        row = _solution_row_from_result(spec, result)
        solutions.append(row)
        ledger_entries.append(
            {
                "spec_id": row["spec_id"],
                "priority": row["priority"],
                "feasible": row["feasible"],
                "total_cost": row["total_cost"],
                "lot_amounts_ml": copy.deepcopy(row["lot_amounts_ml"]),
            }
        )
        if row["feasible"]:
            _debit_working_lots(lots_working, row["lot_amounts_ml"])
    allocation = {
        "schema_version": "allocation/1",
        "batch_generation": model["batch_generation"],
        "target_volume_ml": volume,
        "solutions": solutions,
    }
    ledger = {
        "schema_version": "blend-ledger/1",
        "batch_generation": model["batch_generation"],
        "entries": ledger_entries,
    }
    return allocation, ledger


def reference_dual_certificate(
    model: dict[str, Any], allocation: dict[str, Any]
) -> dict[str, Any]:
    lots_working = copy.deepcopy(model["lots"])
    for lot in lots_working:
        lot["available_ml"] = float(lot["available_ml"])
    volume = float(model["target_volume_ml"])
    model_digest = _sha256(_canonical_json(model))
    certificates: list[dict[str, Any]] = []
    spec_by_id = {spec["spec_id"]: spec for spec in model["specifications"]}
    for solution_row in allocation["solutions"]:
        cert: dict[str, Any] = {"spec_id": solution_row["spec_id"]}
        if not solution_row["feasible"]:
            cert["certified"] = False
            cert["shadow_prices"] = {}
            cert["optimality_gap_bound"] = 0.0
            certificates.append(cert)
            continue
        spec = spec_by_id[solution_row["spec_id"]]
        shadow = reference_shadow_prices(lots_working, spec, volume, solution_row)
        gap = reference_gap_bound(solution_row, shadow, lots_working, spec)
        cert["certified"] = True
        cert["shadow_prices"] = shadow
        cert["optimality_gap_bound"] = _round6(gap)
        certificates.append(cert)
        _debit_working_lots(lots_working, solution_row["lot_amounts_ml"])
    return {
        "schema_version": "dual-certificate/1",
        "batch_generation": allocation["batch_generation"],
        "model_layer_digest": model_digest,
        "certificates": certificates,
    }


def reference_cert(
    allocation: dict[str, Any],
    dual_certificate: dict[str, Any],
    *,
    allocation_path: Path | None = None,
    dual_path: Path | None = None,
) -> dict[str, Any]:
    allocation_rows: list[dict[str, Any]] = []
    for src in allocation["solutions"]:
        allocation_rows.append(
            {
                "spec_id": src["spec_id"],
                "priority": src["priority"],
                "feasible": src["feasible"],
                "total_cost": src["total_cost"],
                "lot_amounts_ml": copy.deepcopy(src["lot_amounts_ml"]),
            }
        )
    feasible_count = sum(1 for row in allocation["solutions"] if row["feasible"])
    total_cost = sum(
        float(row["total_cost"]) for row in allocation["solutions"] if row["feasible"]
    )
    cert_body: dict[str, Any] = {
        "cert_version": "1.0",
        "batch_generation": allocation["batch_generation"],
        "allocation_rows": allocation_rows,
        "summary": {
            "feasible_count": feasible_count,
            "infeasible_count": len(allocation["solutions"]) - feasible_count,
            "total_cost": _round6(total_cost),
        },
    }
    if allocation_path is not None:
        allocation_layer = _artifact_file_digest(allocation_path)
    else:
        allocation_layer = _sha256(_canonical_json(allocation))
    if dual_path is not None:
        dual_layer = _artifact_file_digest(dual_path)
    else:
        dual_layer = _sha256(_canonical_json(dual_certificate))
    combined_layer = _sha256(_canonical_json(cert_body))
    digest = _sha256(f"{allocation_layer}|{dual_layer}|{combined_layer}")
    cert_body["feasibility_digest"] = digest
    cert_body["digest_layers"] = {
        "allocation": allocation_layer,
        "dual": dual_layer,
        "combined": combined_layer,
    }
    return cert_body


def reference_pipeline(
    lots_root: dict[str, Any], specs_root: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    model = reference_bind_model(lots_root, specs_root)
    allocation, ledger = reference_solve_outputs(model)
    dual = reference_dual_certificate(model, allocation)
    cert = reference_cert(allocation, dual)
    return model, allocation, ledger, dual, cert


def _reset_outputs() -> None:
    for path in (
        STATE / "blend-model.json",
        STATE / "lot-inventory.json",
        STATE / "allocation.json",
        STATE / "dual-certificate.json",
        STATE / "greedy-preview.json",
        OUTPUT / "blend-ledger.json",
        OUTPUT / "blend-feasibility-cert.json",
    ):
        if path.exists():
            path.unlink()
    STATE.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)


def _restore_inputs(fixture_dir: Path | None = None) -> None:
    src = fixture_dir if fixture_dir is not None else BUNDLED
    shutil.copy2(src / "lots.json", INPUT_DIR / "lots.json")
    shutil.copy2(src / "specs.json", INPUT_DIR / "specs.json")
    if Path("/usr/sbin/runuser").is_file():
        for name in ("lots.json", "specs.json"):
            subprocess.run(
                ["chown", "agent:agent", str(INPUT_DIR / name)],
                check=False,
            )


def _fixture_inputs(fixture_dir: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    src = fixture_dir if fixture_dir is not None else BUNDLED
    lots_root = _load(src / "lots.json")
    specs_root = _load(src / "specs.json")
    return lots_root, specs_root


def _run_pipeline(fixture_dir: Path | None = None) -> None:
    _reset_outputs()
    _restore_inputs(fixture_dir)
    for sub in ("bind", "solve", "certify", "seal"):
        proc = _blendcert(sub)
        assert proc.returncode == 0, proc.stderr or proc.stdout


def _solution_by_id(allocation: dict[str, Any], spec_id: str) -> dict[str, Any]:
    return next(row for row in allocation["solutions"] if row["spec_id"] == spec_id)


def _avg_lot_cost(lots: list[dict[str, Any]]) -> float:
    return sum(float(lot["cost_per_ml"]) for lot in lots) / len(lots)


def _assert_shadow_prices_match(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    assert abs(float(actual["volume"]) - float(expected["volume"])) < SHADOW_TOL
    assert set(actual["lots"]) == set(expected["lots"])
    for lot_id, dual in expected["lots"].items():
        assert abs(float(actual["lots"][lot_id]) - float(dual)) < SHADOW_TOL
    assert set(actual["analytes_lower"]) == set(expected["analytes_lower"])
    for analyte, dual in expected["analytes_lower"].items():
        assert abs(float(actual["analytes_lower"][analyte]) - float(dual)) < SHADOW_TOL
    assert set(actual["analytes_upper"]) == set(expected["analytes_upper"])
    for analyte, dual in expected["analytes_upper"].items():
        assert abs(float(actual["analytes_upper"][analyte]) - float(dual)) < SHADOW_TOL


def _cert_for_spec(dual: dict[str, Any], spec_id: str) -> dict[str, Any]:
    return next(cert for cert in dual["certificates"] if cert["spec_id"] == spec_id)


# --- bundled tests ---


def test_instruction_output_paths_exist():
    """All contract paths from instruction exist after full pipeline."""
    _run_pipeline()
    for contract in (
        PATH_BLEND_MODEL,
        PATH_LOT_INVENTORY,
        PATH_ALLOCATION,
        PATH_DUAL_CERTIFICATE,
        PATH_BLEND_LEDGER,
        PATH_BLEND_FEASIBILITY_CERT,
    ):
        assert Path(contract).is_file(), contract


def test_bind_writes_blend_model_schema():
    """bind writes blend-model/1 with batch_generation from lots.json."""
    _reset_outputs()
    _restore_inputs()
    assert _blendcert("bind").returncode == 0
    model = _load(STATE / "blend-model.json")
    assert model["schema_version"] == "blend-model/1"
    assert model["batch_generation"] == 12


def test_bind_writes_lot_inventory_snapshot():
    """bind writes lot-inventory/1 staging snapshot from lots.json."""
    _reset_outputs()
    _restore_inputs()
    lots_root, _ = _fixture_inputs()
    assert _blendcert("bind").returncode == 0
    inventory = _load(STATE / "lot-inventory.json")
    expected = reference_lot_inventory(lots_root)
    assert inventory == expected


def test_bind_missing_input_exit_3():
    """bind exits 3 when lots.json is missing."""
    _reset_outputs()
    (INPUT_DIR / "lots.json").unlink(missing_ok=True)
    assert _blendcert("bind").returncode == 3


def test_solve_missing_model_exit_2():
    """solve exits 2 when blend-model.json is missing."""
    _reset_outputs()
    assert _blendcert("solve").returncode == 2


def test_solve_missing_inventory_exit_2():
    """solve exits 2 when lot-inventory.json is missing."""
    _reset_outputs()
    _restore_inputs()
    assert _blendcert("bind").returncode == 0
    (STATE / "lot-inventory.json").unlink()
    assert _blendcert("solve").returncode == 2


def test_bundled_spec01_cost_and_allocation():
    """SPEC-01 uses 100 percent LOT-A at cost 80.0."""
    _run_pipeline()
    row = _solution_by_id(_load(STATE / "allocation.json"), "SPEC-01")
    assert row["feasible"] is True
    assert abs(float(row["total_cost"]) - SPEC01_COST) < COST_TOL
    assert abs(float(row["lot_amounts_ml"]["LOT-A"]) - 100.0) < COST_TOL


def test_bundled_spec02_cost_approx():
    """SPEC-02 least-cost feasible blend is about 89.356436."""
    _run_pipeline()
    row = _solution_by_id(_load(STATE / "allocation.json"), "SPEC-02")
    assert row["feasible"] is True
    assert abs(float(row["total_cost"]) - SPEC02_COST) < COST_TOL


def test_bundled_spec03_cost_approx():
    """SPEC-03 least-cost feasible blend is about 85.049505."""
    _run_pipeline()
    row = _solution_by_id(_load(STATE / "allocation.json"), "SPEC-03")
    assert row["feasible"] is True
    assert abs(float(row["total_cost"]) - SPEC03_COST) < COST_TOL


def test_bundled_all_specs_feasible():
    """Bundled allocation marks every specification feasible."""
    _run_pipeline()
    solutions = _load(STATE / "allocation.json")["solutions"]
    assert len(solutions) == 3
    assert all(row["feasible"] for row in solutions)


def test_ledger_schema_and_entry_count():
    """blend-ledger has schema and three entries."""
    _run_pipeline()
    ledger = _load(OUTPUT / "blend-ledger.json")
    assert ledger["schema_version"] == "blend-ledger/1"
    assert ledger["batch_generation"] == 12
    assert len(ledger["entries"]) == 3


def test_ledger_priority_order():
    """Ledger entries follow priority then spec_id order SPEC-01, SPEC-02, SPEC-03."""
    _run_pipeline()
    entries = _load(OUTPUT / "blend-ledger.json")["entries"]
    assert [entry["spec_id"] for entry in entries] == ["SPEC-01", "SPEC-02", "SPEC-03"]


def test_allocation_schema_version():
    """allocation.json uses allocation/1 schema with target volume."""
    _run_pipeline()
    allocation = _load(STATE / "allocation.json")
    assert allocation["schema_version"] == "allocation/1"
    assert allocation["target_volume_ml"] == 100.0


def test_dual_certificate_schema():
    """dual-certificate carries schema and one certificate per solution."""
    _run_pipeline()
    dual = _load(STATE / "dual-certificate.json")
    assert dual["schema_version"] == "dual-certificate/1"
    assert len(dual["certificates"]) == 3


def test_dual_certificate_model_layer_digest():
    """model_layer_digest is SHA-256 of on-disk blend-model.json bytes."""
    _run_pipeline()
    dual = _load(STATE / "dual-certificate.json")
    expected = _artifact_file_digest(STATE / "blend-model.json")
    assert dual["model_layer_digest"] == expected
    assert len(dual["model_layer_digest"]) == 64


def test_witness_schema_and_digest():
    """feasibility-witness includes version and 64-char feasibility_digest."""
    _run_pipeline()
    witness = _load(OUTPUT / "blend-feasibility-cert.json")
    assert witness["cert_version"] == "1.0"
    assert len(witness["feasibility_digest"]) == 64


def test_witness_digest_matches_reference():
    """feasibility_digest matches independent three-layer reference."""
    _run_pipeline()
    allocation = _load(STATE / "allocation.json")
    dual = _load(STATE / "dual-certificate.json")
    expected = reference_cert(
        allocation,
        dual,
        allocation_path=STATE / "allocation.json",
        dual_path=STATE / "dual-certificate.json",
    )
    actual = _load(OUTPUT / "blend-feasibility-cert.json")
    assert actual["feasibility_digest"] == expected["feasibility_digest"]


def test_witness_digest_layers_match_on_disk_state():
    """allocation and dual digest layers hash on-disk state file bytes."""
    _run_pipeline()
    layers = _load(OUTPUT / "blend-feasibility-cert.json")["digest_layers"]
    assert layers["allocation"] == _artifact_file_digest(STATE / "allocation.json")
    assert layers["dual"] == _artifact_file_digest(STATE / "dual-certificate.json")


def test_witness_digest_layers_present():
    """digest_layers exposes allocation, dual, and combined hashes."""
    _run_pipeline()
    layers = _load(OUTPUT / "blend-feasibility-cert.json")["digest_layers"]
    assert set(layers) == {"allocation", "dual", "combined"}
    assert all(len(layers[key]) == 64 for key in layers)


def test_agent_source_does_not_reference_verifier_paths():
    """blendcert sources must not embed verifier or test harness paths."""
    banned = ("/tests", "test_outputs", "/opt/verifier-fixtures", "verifier-fixtures")
    src_root = APP / "src" / "main" / "java"
    for path in src_root.rglob("*.java"):
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{path} must not reference {token}"


def test_full_pipeline_exit_codes_zero():
    """All four stages exit 0 on bundled inputs."""
    _reset_outputs()
    _restore_inputs()
    for sub in ("bind", "solve", "certify", "seal"):
        assert _blendcert(sub).returncode == 0


def test_solve_reads_staging_only():
    """solve reads blend-model and lot-inventory only, not mutated live lots.json after bind."""
    _reset_outputs()
    _restore_inputs()
    assert _blendcert("bind").returncode == 0
    inventory_after_bind = copy.deepcopy(_load(STATE / "lot-inventory.json"))
    assert _blendcert("solve").returncode == 0
    first = _load(STATE / "allocation.json")
    _write(INPUT_DIR / "lots.json", {"batch_generation": 99, "target_volume_ml": 1.0, "lots": []})
    (STATE / "allocation.json").unlink(missing_ok=True)
    (OUTPUT / "blend-ledger.json").unlink(missing_ok=True)
    _write(STATE / "lot-inventory.json", inventory_after_bind)
    assert _blendcert("solve").returncode == 0
    second = _load(STATE / "allocation.json")
    assert second == first


def test_seal_reads_staging_only_not_model():
    """seal reads allocation and dual-certificate only, not blend-model."""
    _run_pipeline()
    first = _load(OUTPUT / "blend-feasibility-cert.json")
    _write(STATE / "blend-model.json", {"schema_version": "blend-model/1", "batch_generation": 0})
    (OUTPUT / "blend-feasibility-cert.json").unlink(missing_ok=True)
    assert _blendcert("seal").returncode == 0
    second = _load(OUTPUT / "blend-feasibility-cert.json")
    assert second == first


def test_export_reads_staging_only():
    """blend-ledger export reads blend-model and lot-inventory staging only, not live input after bind."""
    _reset_outputs()
    _restore_inputs()
    assert _blendcert("bind").returncode == 0
    inventory_after_bind = copy.deepcopy(_load(STATE / "lot-inventory.json"))
    assert _blendcert("solve").returncode == 0
    first_ledger = _load(Path(PATH_BLEND_LEDGER))
    _write(INPUT_DIR / "lots.json", {"batch_generation": 99, "target_volume_ml": 1.0, "lots": []})
    (STATE / "allocation.json").unlink(missing_ok=True)
    (OUTPUT / "blend-ledger.json").unlink(missing_ok=True)
    _write(STATE / "lot-inventory.json", inventory_after_bind)
    assert _blendcert("solve").returncode == 0
    second_ledger = _load(Path(PATH_BLEND_LEDGER))
    assert second_ledger == first_ledger


def test_seal_certificate_reads_prior_artifacts_only():
    """seal certificate reads allocation and dual-certificate only, not blend-model."""
    _run_pipeline()
    first_witness = _load(Path(PATH_BLEND_FEASIBILITY_CERT))
    _write(STATE / "blend-model.json", {"schema_version": "blend-model/1", "batch_generation": 0})
    (OUTPUT / "blend-feasibility-cert.json").unlink(missing_ok=True)
    assert _blendcert("seal").returncode == 0
    second_witness = _load(Path(PATH_BLEND_FEASIBILITY_CERT))
    assert second_witness == first_witness


def test_idempotent_seal_rerun():
    """Repeated seal on unchanged state yields identical witness bytes."""
    _run_pipeline()
    first = (OUTPUT / "blend-feasibility-cert.json").read_text(encoding="utf-8")
    (OUTPUT / "blend-feasibility-cert.json").unlink(missing_ok=True)
    assert _blendcert("seal").returncode == 0
    second = (OUTPUT / "blend-feasibility-cert.json").read_text(encoding="utf-8")
    assert first == second


def test_decoy_greedy_preview_absent_without_env():
    """PATH_GREEDY_PREVIEW absent when BLEND_GREEDY_PREVIEW unset."""
    _run_pipeline()
    assert not Path(PATH_GREEDY_PREVIEW).exists()


def test_decoy_greedy_preview_present_with_env_witness_unchanged():
    """BLEND_GREEDY_PREVIEW=1 writes PATH_GREEDY_PREVIEW without changing witness."""
    _reset_outputs()
    _restore_inputs()
    os.environ["BLEND_GREEDY_PREVIEW"] = "1"
    try:
        for sub in ("bind", "solve", "certify", "seal"):
            assert _blendcert(sub).returncode == 0
        assert Path(PATH_GREEDY_PREVIEW).is_file()
        witness_with = _load(Path(PATH_BLEND_FEASIBILITY_CERT))
    finally:
        os.environ.pop("BLEND_GREEDY_PREVIEW", None)
    _reset_outputs()
    _restore_inputs()
    for sub in ("bind", "solve", "certify", "seal"):
        assert _blendcert(sub).returncode == 0
    witness_without = _load(Path(PATH_BLEND_FEASIBILITY_CERT))
    assert witness_with == witness_without


def test_reference_allocation_matches_bundled():
    """allocation.json matches independent reference solve math."""
    lots_root, specs_root = _fixture_inputs()
    _, expected_allocation, expected_ledger, _, _ = reference_pipeline(lots_root, specs_root)
    _run_pipeline()
    actual_allocation = _load(STATE / "allocation.json")
    actual_ledger = _load(OUTPUT / "blend-ledger.json")
    for spec_id in ("SPEC-01", "SPEC-02", "SPEC-03"):
        exp = _solution_by_id(expected_allocation, spec_id)
        act = _solution_by_id(actual_allocation, spec_id)
        assert act["feasible"] == exp["feasible"]
        assert abs(float(act["total_cost"]) - float(exp["total_cost"])) < COST_TOL
    assert actual_ledger["entries"] == expected_ledger["entries"]


def test_bind_preserves_full_precision_assays():
    """bind keeps full-precision assay values without one-decimal rounding."""
    _reset_outputs()
    trap = VERIFIER_FIXTURES / "precision-assay-trap"
    _restore_inputs(trap)
    assert _blendcert("bind").returncode == 0
    model = _load(STATE / "blend-model.json")
    prec_a = next(lot for lot in model["lots"] if lot["lot_id"] == "PREC-A")
    assert abs(float(prec_a["assays"]["albumin"]) - 3.149) < 1e-9


def test_certify_gap_bound_near_zero_bundled():
    """Bundled certified solutions have optimality_gap_bound near zero."""
    _run_pipeline()
    dual = _load(STATE / "dual-certificate.json")
    for cert in dual["certificates"]:
        if cert.get("certified"):
            assert float(cert["optimality_gap_bound"]) < 1e-3


def test_dual_certificate_shadow_prices_match_reference_bundled():
    """Bundled dual-certificate shadow prices match independent reference for every dual field."""
    lots_root, specs_root = _fixture_inputs()
    _, _, _, expected_dual, _ = reference_pipeline(lots_root, specs_root)
    _run_pipeline()
    actual_dual = _load(STATE / "dual-certificate.json")
    for spec_id in ("SPEC-01", "SPEC-02", "SPEC-03"):
        actual_cert = _cert_for_spec(actual_dual, spec_id)
        expected_cert = _cert_for_spec(expected_dual, spec_id)
        assert actual_cert.get("certified") is True
        _assert_shadow_prices_match(actual_cert["shadow_prices"], expected_cert["shadow_prices"])


# --- hidden traps ---


def test_trap_upper_band_trap():
    """Hidden upper-band-trap rejects UP-HIGH when only lower bands are checked."""
    trap = VERIFIER_FIXTURES / "upper-band-trap"
    assert Path("/opt/verifier-fixtures/upper-band-trap").name == trap.name or trap.is_dir()
    lots_root, specs_root = _fixture_inputs(trap)
    _, expected_allocation, _, _, _ = reference_pipeline(lots_root, specs_root)
    _run_pipeline(trap)
    row = _solution_by_id(_load(STATE / "allocation.json"), "SPEC-UP")
    expected = _solution_by_id(expected_allocation, "SPEC-UP")
    assert row["feasible"] is True
    assert abs(float(row["lot_amounts_ml"]["UP-HIGH"]) - 0.0) < COST_TOL
    assert float(row["lot_amounts_ml"]["UP-MID"]) > 50.0
    assert abs(float(row["total_cost"]) - float(expected["total_cost"])) < COST_TOL


def test_trap_degenerate_spec_trap():
    """Hidden degenerate-spec-trap shadow prices must not equal average lot cost."""
    trap = VERIFIER_FIXTURES / "degenerate-spec-trap"
    assert str(trap).endswith("verifier-fixtures/degenerate-spec-trap")
    lots_root, specs_root = _fixture_inputs(trap)
    _, expected_allocation, _, expected_dual, _ = reference_pipeline(lots_root, specs_root)
    _run_pipeline(trap)
    actual_cert = next(
        cert
        for cert in _load(STATE / "dual-certificate.json")["certificates"]
        if cert["spec_id"] == "SPEC-DEG"
    )
    expected_cert = next(
        cert for cert in expected_dual["certificates"] if cert["spec_id"] == "SPEC-DEG"
    )
    avg_cost = _avg_lot_cost(lots_root["lots"])
    assert abs(float(actual_cert["shadow_prices"]["volume"]) - avg_cost) > 1e-3
    _assert_shadow_prices_match(actual_cert["shadow_prices"], expected_cert["shadow_prices"])
    row = _solution_by_id(_load(STATE / "allocation.json"), "SPEC-DEG")
    exp_row = _solution_by_id(expected_allocation, "SPEC-DEG")
    assert abs(float(row["total_cost"]) - float(exp_row["total_cost"])) < COST_TOL


def test_trap_fractional_lot_trap():
    """Hidden fractional-lot-trap optimality_gap_bound matches reference near zero."""
    trap = VERIFIER_FIXTURES / "fractional-lot-trap"
    assert trap.is_dir()
    lots_root, specs_root = _fixture_inputs(trap)
    _, _, _, expected_dual, _ = reference_pipeline(lots_root, specs_root)
    _run_pipeline(trap)
    actual_cert = next(
        cert
        for cert in _load(STATE / "dual-certificate.json")["certificates"]
        if cert["spec_id"] == "SPEC-FRAC"
    )
    expected_cert = next(
        cert for cert in expected_dual["certificates"] if cert["spec_id"] == "SPEC-FRAC"
    )
    _assert_shadow_prices_match(actual_cert["shadow_prices"], expected_cert["shadow_prices"])
    assert abs(float(actual_cert["optimality_gap_bound"]) - float(expected_cert["optimality_gap_bound"])) < 1e-3
    assert float(actual_cert["optimality_gap_bound"]) < 1e-2


def test_trap_precision_assay_trap():
    """Hidden precision-assay-trap requires albumin 3.149 at bind for feasible blend."""
    trap = VERIFIER_FIXTURES / "precision-assay-trap"
    assert "/opt/verifier-fixtures/precision-assay-trap".endswith(trap.name) or trap.is_dir()
    lots_root, specs_root = _fixture_inputs(trap)
    _, expected_allocation, _, _, _ = reference_pipeline(lots_root, specs_root)
    _run_pipeline(trap)
    model = _load(STATE / "blend-model.json")
    prec_a = next(lot for lot in model["lots"] if lot["lot_id"] == "PREC-A")
    assert abs(float(prec_a["assays"]["albumin"]) - 3.149) < 1e-9
    row = _solution_by_id(_load(STATE / "allocation.json"), "SPEC-PREC")
    expected = _solution_by_id(expected_allocation, "SPEC-PREC")
    assert row["feasible"] is True
    assert abs(float(row["lot_amounts_ml"]["PREC-A"]) - 100.0) < COST_TOL
    assert abs(float(row["total_cost"]) - float(expected["total_cost"])) < COST_TOL


def test_trap_inventory_cascade_trap():
    """Hidden inventory-cascade-trap debits STAR lot so SPEC-B cost rises after SPEC-A."""
    trap = VERIFIER_FIXTURES / "inventory-cascade-trap"
    assert trap.is_dir()
    lots_root, specs_root = _fixture_inputs(trap)
    _, expected_allocation, _, _, _ = reference_pipeline(lots_root, specs_root)
    _run_pipeline(trap)
    row = _solution_by_id(_load(STATE / "allocation.json"), "SPEC-B")
    expected = _solution_by_id(expected_allocation, "SPEC-B")
    independent_cost = 50.0
    assert abs(float(row["total_cost"]) - independent_cost) > 50.0
    assert abs(float(row["total_cost"]) - float(expected["total_cost"])) < COST_TOL
    assert float(row["lot_amounts_ml"]["BACK"]) > 50.0
