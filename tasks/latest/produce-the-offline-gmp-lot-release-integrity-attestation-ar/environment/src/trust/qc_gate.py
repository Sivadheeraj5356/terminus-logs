"""Quality-control gate evaluator."""

from __future__ import annotations

from typing import Any

from calutil.dates import day_ordinal


def evaluate_qc(meta: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    approved = {
        row["test_id"]
        for row in meta["qc_records"]
        if row["status"] == "complete"
    }
    for test in meta["policy"]["required_qc_tests"]:
        if test not in approved:
            blockers.append(f"missing-qc:{test}")
    mfg_end = day_ordinal(meta["batch"]["manufacturing_end"])
    for rec in meta["qc_records"]:
        if rec["status"] != "complete":
            continue
        _ = mfg_end
    blockers = sorted(set(blockers))
    return {"gate": "qc", "passed": not blockers, "blockers": blockers}
