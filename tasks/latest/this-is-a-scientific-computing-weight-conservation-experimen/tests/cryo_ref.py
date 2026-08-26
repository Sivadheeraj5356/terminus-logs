"""Independent reference for cryoready readiness math (no C++ internals)."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ATM_PSIA = 14.6959


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def sort_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: sort_json(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [sort_json(v) for v in value]
    return value


def canonical_json_compact(doc: Any) -> str:
    return json.dumps(sort_json(doc), separators=(",", ":"), ensure_ascii=False)


def round6(v: float) -> float:
    return round(v * 1e6) / 1e6


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_model(catalog: dict, model_id: str) -> dict:
    for model in catalog["models"]:
        if model["model_id"] == model_id:
            return model
    raise KeyError(model_id)


def fill_fraction(level_liters: float, model: dict) -> float:
    usable = float(model["usable_capacity_l"])
    if usable <= 0:
        return 0.0
    return level_liters / usable


def fill_in_range(fraction: float, model: dict) -> bool:
    return float(model["min_fill_fraction"]) <= fraction <= float(model["max_fill_fraction"])


def hold_hours(level_liters: float, model: dict) -> float:
    boil = float(model["boil_off_l_per_day"])
    if boil <= 0:
        return 0.0
    reserve = float(model["usable_capacity_l"]) * float(model["hold_reserve_fraction"])
    remaining = level_liters - reserve
    if remaining <= 0:
        return 0.0
    return (remaining / boil) * 24.0


def pressure_psia(pressure_psig: float) -> float:
    return pressure_psig + ATM_PSIA


def pressure_ok(pressure_psig: float, model: dict) -> bool:
    return pressure_psia(pressure_psig) <= float(model["mawp_psia"])


def in_maintenance(maint: dict, vessel_id: str, epoch: int) -> bool:
    for window in maint["windows"]:
        if window["vessel_id"] != vessel_id:
            continue
        if int(window["start_unix"]) <= epoch < int(window["end_unix"]):
            return True
    return False


def sensor_cal_ok(calibrated_until: int, epoch: int) -> bool:
    return calibrated_until > epoch


def specimen_compatible(specimen_class: str, vessel_cryogen_class: str) -> bool:
    return specimen_class == vessel_cryogen_class


def build_inventory_stage(
    facility_path: Path,
    catalog_path: Path,
    maintenance_path: Path,
) -> dict:
    facility = load_json(facility_path)
    catalog = load_json(catalog_path)
    maint = load_json(maintenance_path)
    epoch = int(facility["assessment_epoch_unix"])

    vessels = sorted(facility["vessels"], key=lambda v: v["vessel_id"])
    rows: list[dict] = []
    for vessel in vessels:
        model = find_model(catalog, vessel["model_id"])
        frac = round6(fill_fraction(float(vessel["level_liters"]), model))
        hold = round6(hold_hours(float(vessel["level_liters"]), model))
        psia = round6(pressure_psia(float(vessel["pressure_psig"])))
        reasons: list[str] = []
        if in_maintenance(maint, vessel["vessel_id"], epoch):
            reasons.append("in_maintenance")
        if not sensor_cal_ok(int(vessel["sensor_calibrated_until_unix"]), epoch):
            reasons.append("sensor_cal_expired")
        if not fill_in_range(frac, model):
            if frac < float(model["min_fill_fraction"]):
                reasons.append("fill_below_min")
            else:
                reasons.append("fill_above_max")
        if not pressure_ok(float(vessel["pressure_psig"]), model):
            reasons.append("pressure_exceeds_mawp")
        rows.append(
            {
                "vessel_id": vessel["vessel_id"],
                "model_id": vessel["model_id"],
                "cryogen": vessel["cryogen"],
                "cryogen_class": model["cryogen_class"],
                "level_liters": vessel["level_liters"],
                "fill_fraction": frac,
                "pressure_psig": vessel["pressure_psig"],
                "pressure_psia": psia,
                "hold_hours": hold,
                "sensor_calibrated_until_unix": vessel["sensor_calibrated_until_unix"],
                "ready": len(reasons) == 0,
                "reasons": reasons,
            }
        )

    stage = {
        "facility_id": facility["facility_id"],
        "assessment_epoch_unix": epoch,
        "facility_digest": sha256_file(facility_path),
        "catalog_digest": sha256_file(catalog_path),
        "maintenance_digest": sha256_file(maintenance_path),
        "vessels": rows,
    }
    stage["inventory_digest"] = sha256_bytes(
        canonical_json_compact(
            {
                "assessment_epoch_unix": stage["assessment_epoch_unix"],
                "facility_digest": stage["facility_digest"],
                "catalog_digest": stage["catalog_digest"],
                "maintenance_digest": stage["maintenance_digest"],
                "facility_id": stage["facility_id"],
                "vessels": stage["vessels"],
            }
        )
    )
    return stage


def vessel_meets_request(row: dict, req: dict) -> bool:
    if not row["ready"]:
        return False
    if not specimen_compatible(req["specimen_class"], row["cryogen_class"]):
        return False
    if float(row["hold_hours"]) + 1e-9 < float(req["min_hold_hours"]):
        return False
    return True


def first_eligible(vessels: list[dict], req: dict) -> str:
    for row in vessels:
        if vessel_meets_request(row, req):
            return row["vessel_id"]
    return ""


def build_readiness_report(
    facility_path: Path,
    catalog_path: Path,
    maintenance_path: Path,
    inventory_stage: dict,
) -> dict:
    facility = load_json(facility_path)
    fac_d = sha256_file(facility_path)
    cat_d = sha256_file(catalog_path)
    mnt_d = sha256_file(maintenance_path)
    if (
        inventory_stage.get("facility_digest") != fac_d
        or inventory_stage.get("catalog_digest") != cat_d
        or inventory_stage.get("maintenance_digest") != mnt_d
    ):
        raise ValueError("inventory stage digests stale; re-run inventory")

    vessels = inventory_stage["vessels"]
    ready_count = sum(1 for row in vessels if row["ready"])
    blocked_count = len(vessels) - ready_count

    placements: list[dict] = []
    satisfied = 0
    for req in facility.get("placement_requests", []):
        preferred = req.get("preferred_vessel_id") or ""
        reasons: list[str] = []
        assigned = ""
        ok = False

        if preferred:
            row = next((v for v in vessels if v["vessel_id"] == preferred), None)
            if row is None:
                reasons.append("preferred_vessel_missing")
            elif not vessel_meets_request(row, req):
                reasons.append("preferred_vessel_not_eligible")
            else:
                assigned = preferred
                ok = True

        if not ok:
            assigned = first_eligible(vessels, req)
            if assigned:
                ok = True
            else:
                reasons.append("no_compatible_ready_vessel")

        if ok:
            satisfied += 1
            if not preferred or assigned == preferred:
                reasons = []

        placements.append(
            {
                "request_id": req["request_id"],
                "specimen_class": req["specimen_class"],
                "min_hold_hours": req["min_hold_hours"],
                "preferred_vessel_id": preferred,
                "assigned_vessel_id": assigned or None,
                "satisfied": ok,
                "reasons": reasons,
            }
        )

    report = {
        "facility_id": facility["facility_id"],
        "assessment_epoch_unix": facility["assessment_epoch_unix"],
        "facility_digest": fac_d,
        "catalog_digest": cat_d,
        "maintenance_digest": mnt_d,
        "inventory_digest": inventory_stage["inventory_digest"],
        "vessels": vessels,
        "placements": placements,
        "ready_vessel_count": ready_count,
        "blocked_vessel_count": blocked_count,
        "satisfied_placement_count": satisfied,
        "placement_request_count": len(facility.get("placement_requests", [])),
    }
    report["report_digest"] = sha256_bytes(
        canonical_json_compact(
            {
                "facility_id": report["facility_id"],
                "assessment_epoch_unix": report["assessment_epoch_unix"],
                "facility_digest": report["facility_digest"],
                "catalog_digest": report["catalog_digest"],
                "maintenance_digest": report["maintenance_digest"],
                "inventory_digest": report["inventory_digest"],
                "vessels": report["vessels"],
                "placements": report["placements"],
                "ready_vessel_count": report["ready_vessel_count"],
                "blocked_vessel_count": report["blocked_vessel_count"],
                "satisfied_placement_count": report["satisfied_placement_count"],
                "placement_request_count": report["placement_request_count"],
            }
        )
    )
    return report


def build_certificate(report: dict) -> dict:
    all_placements = report["satisfied_placement_count"] == report["placement_request_count"]
    cert = {
        "facility_id": report["facility_id"],
        "assessment_epoch_unix": report["assessment_epoch_unix"],
        "report_digest": report["report_digest"],
        "facility_digest": report["facility_digest"],
        "catalog_digest": report["catalog_digest"],
        "maintenance_digest": report["maintenance_digest"],
        "inventory_digest": report["inventory_digest"],
        "all_placements_satisfied": all_placements,
        "ready_vessel_count": report["ready_vessel_count"],
        "blocked_vessel_count": report["blocked_vessel_count"],
        "certificate_ok": all_placements,
    }
    cert["certificate_digest"] = sha256_bytes(
        canonical_json_compact(
            {
                "facility_id": cert["facility_id"],
                "assessment_epoch_unix": cert["assessment_epoch_unix"],
                "report_digest": cert["report_digest"],
                "facility_digest": cert["facility_digest"],
                "catalog_digest": cert["catalog_digest"],
                "maintenance_digest": cert["maintenance_digest"],
                "inventory_digest": cert["inventory_digest"],
                "all_placements_satisfied": cert["all_placements_satisfied"],
                "ready_vessel_count": cert["ready_vessel_count"],
                "blocked_vessel_count": cert["blocked_vessel_count"],
                "certificate_ok": cert["certificate_ok"],
            }
        )
    )
    return cert


def assess_ledger_key(facility_digest: str, catalog_digest: str, maintenance_digest: str) -> str:
    return f"{facility_digest}|{catalog_digest}|{maintenance_digest}"


def mutate_facility(base: Path, out: Path, bump: int) -> Path:
    data = load_json(base)
    data["assessment_epoch_unix"] = int(data["assessment_epoch_unix"]) + bump
    if data["vessels"]:
        data["vessels"][0]["level_liters"] = float(data["vessels"][0]["level_liters"]) + (bump % 5) * 0.25
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return out


def deep_copy_json(path: Path) -> dict:
    return deepcopy(load_json(path))
