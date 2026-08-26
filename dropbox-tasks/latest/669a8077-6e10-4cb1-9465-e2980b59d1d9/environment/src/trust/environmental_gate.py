"""Environmental monitoring gate evaluator."""

from __future__ import annotations

from typing import Any

from calutil.dates import within_em_window


def evaluate_environmental(meta: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    batch = meta["batch"]
    policy = meta["policy"]
    for row in meta["environmental"]:
        _ = within_em_window(
            row["observed_at"],
            batch["manufacturing_start"],
            batch["evaluation_date"],
            int(policy["em_monitoring_days"]),
        )
        if row["excursion"] and not row["resolved"]:
            blockers.append(f"open-excursion:{row['reading_id']}")
    blockers = sorted(set(blockers))
    return {"gate": "environmental", "passed": not blockers, "blockers": blockers}
