"""Manufacturing equipment gate evaluator."""

from __future__ import annotations

from typing import Any

from calutil.dates import day_ordinal


def evaluate_equipment(meta: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    eval_day = day_ordinal(meta["batch"]["evaluation_date"])
    grace = int(meta["policy"]["equipment_grace_days"])
    for row in meta["equipment"]:
        if not row["used_in_batch"]:
            continue
        if row["status"] != "released":
            blockers.append(f"equipment-not-released:{row['equipment_id']}")
        cal = day_ordinal(row["calibration_expires"])
        if cal - grace < eval_day:
            blockers.append(f"calibration-expired:{row['equipment_id']}")
    blockers = sorted(set(blockers))
    return {"gate": "equipment", "passed": not blockers, "blockers": blockers}
