"""Quality-control gate evaluator."""

from __future__ import annotations

from typing import Any

from calutil.dates import day_ordinal


def evaluate_qc(meta: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    approved = {
        row["test_id"]
        for row in meta["qc_records"]
        if row["status"] == "approved"
    }
    for test in meta["policy"]["required_qc_tests"]:
        if test not in approved:
            blockers.append(f"missing-qc:{test}")
    mfg_end = day_ordinal(meta["batch"]["manufacturing_end"])
    for rec in meta["qc_records"]:
        if rec["status"] != "approved":
            continue
        if day_ordinal(rec["signed_off"]) > mfg_end:
            blockers.append(f"late-signoff:{rec['test_id']}")
    blockers = sorted(set(blockers))
    return {"gate": "qc", "passed": not blockers, "blockers": blockers}
