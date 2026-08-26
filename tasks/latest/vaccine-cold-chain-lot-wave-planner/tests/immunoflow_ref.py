#!/usr/bin/env python3
"""Independent reference model for immunoflow verifier."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def load_lab(lab: str) -> dict:
    root = Path(lab)
    return {
        "regions": json.loads((root / "regions.json").read_text(encoding="utf-8")),
        "lots": json.loads((root / "lots.json").read_text(encoding="utf-8")),
        "routes": json.loads((root / "routes.json").read_text(encoding="utf-8")),
        "clinics": json.loads((root / "clinics.json").read_text(encoding="utf-8")),
    }


def load_cfg() -> dict:
    cfg = {"reserve_doses": 40, "vial_size": 5}
    raw = Path("/app/config/immuno.toml").read_text(encoding="utf-8")
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = [p.strip() for p in line.split("=", 1)]
        value = value.strip('"')
        if key in cfg:
            cfg[key] = int(value)
    return cfg


def gap_weeks(min_gap_days: int) -> int:
    return (min_gap_days + 6) // 7


def dose2_wave(dose1_wave: int, min_gap_days: int) -> int:
    return dose1_wave + gap_weeks(min_gap_days)


def digest_hex(wave: int, entries: list[str]) -> str:
    body = f"{wave}|{'|'.join(entries)}"
    proc = subprocess.run(["sha256sum"], input=body.encode(), capture_output=True, check=True)
    return proc.stdout.decode().split()[0]


def fefo_ids(lots: list[dict], left: dict[str, int]) -> list[dict]:
    rows = []
    for lot in lots:
        avail = left.get(lot["lot_id"], 0)
        if avail <= 0:
            continue
        row = dict(lot)
        row["doses"] = avail
        rows.append(row)
    return sorted(rows, key=lambda row: (row["expiry_day"], row["lot_id"]))


def build_plan(lab: str, wave: int = 3, remainder: dict[str, int] | None = None) -> dict:
    data = load_lab(lab)
    cfg = load_cfg()
    routes = {row["region_id"]: row for row in data["routes"]}
    rem = dict(remainder or {})
    left: dict[str, int] = {}
    for lot in data["lots"]:
        avail = int(lot["doses"]) - int(rem.get(lot["lot_id"], 0))
        left[lot["lot_id"]] = max(avail, 0)
    regions = sorted(data["regions"], key=lambda row: row["region_id"])
    delivered: dict[str, int] = {}
    assignments: list[dict] = []
    for region in regions:
        need = int(region["demand_dose1"])
        remain = need
        for lot in fefo_ids(data["lots"], left):
            if remain <= 0:
                break
            if lot["temp_band"] != region["storage_temp"]:
                continue
            give = min(remain, int(lot["doses"]))
            if give <= 0:
                continue
            remain -= give
            left[lot["lot_id"]] -= give
            rem[lot["lot_id"]] = (int(rem.get(lot["lot_id"], 0)) + give) % cfg["vial_size"]
            route = routes[region["region_id"]]
            assignments.append(
                {
                    "region_id": region["region_id"],
                    "lot_id": lot["lot_id"],
                    "doses": give,
                    "temp_band": lot["temp_band"],
                    "pallet_id": route["pallet_id"],
                }
            )
            delivered[region["region_id"]] = delivered.get(region["region_id"], 0) + give
    coverage = []
    equity_met = True
    for region in regions:
        got = delivered.get(region["region_id"], 0)
        need = int(region["demand_dose1"])
        floor = int(region["equity_floor"])
        ratio = (got / need) if need else 0.0
        coverage.append(
            {
                "region_id": region["region_id"],
                "delivered": got,
                "need": need,
                "coverage_ratio": ratio,
            }
        )
        if got < floor:
            equity_met = False
    entries = sorted(f"{row['region_id']}:{row['lot_id']}:{row['doses']}" for row in assignments)
    return {
        "wave": wave,
        "lot_assignments": assignments,
        "region_coverage": coverage,
        "equity_met": equity_met,
        "plan_digest_hex": digest_hex(wave, entries),
        "_remainder": rem,
    }


def build_dose_schedule(lab: str, dose1_wave: int = 3) -> dict:
    clinics = load_lab(lab)["clinics"]
    rows = []
    for clinic in clinics:
        rows.append(
            {
                "clinic_id": clinic["clinic_id"],
                "dose1_wave": dose1_wave,
                "dose2_wave": dose2_wave(dose1_wave, int(clinic["min_gap_days"])),
                "min_gap_days": int(clinic["min_gap_days"]),
            }
        )
    return {"schedule": rows}


def build_equity_rollup(lab: str, plan: dict) -> dict:
    regions = load_lab(lab)["regions"]
    delivered = {row["region_id"]: row["delivered"] for row in plan["region_coverage"]}
    out = {}
    equity_met = True
    for region in regions:
        got = delivered.get(region["region_id"], 0)
        out[region["region_id"]] = got
        if got < int(region["equity_floor"]):
            equity_met = False
    return {"region_delivered": out, "equity_met": equity_met}


def build_infection(lab: str, plan: dict) -> dict:
    clinics = {row["region_id"]: int(row["min_gap_days"]) for row in load_lab(lab)["clinics"]}
    rows = []
    for cov in plan["region_coverage"]:
        short = max(int(cov["need"]) - int(cov["delivered"]), 0)
        weeks = gap_weeks(clinics[cov["region_id"]])
        rows.append({"region_id": cov["region_id"], "projected_cases": short * weeks})
    return {"wave": plan["wave"], "rows": rows}


def bind_pallets(plan: dict) -> dict[str, list[str]]:
    band: dict[str, str] = {}
    out: dict[str, list[str]] = {}
    for row in plan["lot_assignments"]:
        key = row["pallet_id"]
        if key in band and band[key] != row["temp_band"]:
            key = f"{row['pallet_id']}-{row['temp_band']}"
        band[key] = row["temp_band"]
        out.setdefault(key, []).append(row["lot_id"])
    return out


def go_map_v(pallets: dict[str, list[str]]) -> str:
    parts = []
    for key in sorted(pallets.keys()):
        lots = " ".join(pallets[key])
        parts.append(f"{key}:[{lots}]")
    return "map[" + " ".join(parts) + "]"


def lane_digest_hex(pallets: dict[str, list[str]]) -> str:
    body = go_map_v(pallets)
    proc = subprocess.run(["sha256sum"], input=body.encode(), capture_output=True, check=True)
    return proc.stdout.decode().split()[0]


def build_coldchain_audit(lab: str, wave: int = 3) -> dict:
    plan = build_plan(lab, wave)
    plan.pop("_remainder", None)
    pallets = bind_pallets(plan)
    return {
        "wave": wave,
        "pallets": pallets,
        "spoilage_rows": [],
        "lane_digest_hex": lane_digest_hex(pallets),
    }

def customs_delta(lab: str, plan: dict) -> int:
    served = {row["region_id"] for row in plan["lot_assignments"]}
    total = 0
    for route in load_lab(lab)["routes"]:
        if route["region_id"] in served:
            total += int(route["customs_delay_days"])
    return total


def main() -> None:
    argv = sys.argv[1:]
    if not argv:
        raise SystemExit(
            "usage: immunoflow_ref.py --lab PATH <plan|dose|equity|pallets|infection|customs> [--wave N] [--dose1-wave N]"
        )
    lab = "/app/data/immunolab"
    if argv[0] == "--lab":
        lab = argv[1]
        argv = argv[2:]
    if not argv:
        raise SystemExit("missing command")
    cmd = argv[0]
    wave = 3
    dose1_wave = 3
    idx = 1
    while idx < len(argv):
        arg = argv[idx]
        if arg == "--wave" and idx + 1 < len(argv):
            wave = int(argv[idx + 1])
            idx += 2
            continue
        if arg == "--dose1-wave" and idx + 1 < len(argv):
            dose1_wave = int(argv[idx + 1])
            idx += 2
            continue
        idx += 1
    if cmd == "plan":
        plan = build_plan(lab, wave)
        plan.pop("_remainder", None)
        print(json.dumps(plan, indent=2))
    elif cmd == "dose":
        print(json.dumps(build_dose_schedule(lab, dose1_wave), indent=2))
    elif cmd == "equity":
        plan = build_plan(lab, wave)
        plan.pop("_remainder", None)
        print(json.dumps(build_equity_rollup(lab, plan), indent=2))
    elif cmd == "infection":
        plan = build_plan(lab, wave)
        plan.pop("_remainder", None)
        print(json.dumps(build_infection(lab, plan), indent=2))
    elif cmd == "customs":
        plan = build_plan(lab, wave)
        plan.pop("_remainder", None)
        print(json.dumps({"delta": customs_delta(lab, plan)}, indent=2))
    elif cmd == "coldchain":
        print(json.dumps(build_coldchain_audit(lab, wave), indent=2))
    else:
        plan = build_plan(lab, wave)
        plan.pop("_remainder", None)
        pallets = bind_pallets(plan)
        by_lot = {row["lot_id"]: row["temp_band"] for row in plan["lot_assignments"]}
        ok = all(len({by_lot[lid] for lid in lots}) == 1 for lots in pallets.values())
        print(json.dumps({"ok": ok, "pallets": pallets}, indent=2))


if __name__ == "__main__":
    main()
