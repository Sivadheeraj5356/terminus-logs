"""Release trust attestation export from staged integrity capsules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from attestation.digest import ensure_parent, seal_bytes


def publish_from_stage(
    stage: Path,
    output: Path,
    meta: dict[str, Any],
    evaluation_seq: int,
) -> dict[str, Any]:
    raw = stage.read_bytes()
    snapshot = json.loads(raw.decode("utf-8"))
    staging_seal = seal_bytes(raw)
    report = report_from_snapshot(meta, snapshot, staging_seal, evaluation_seq)
    ensure_parent(output)
    text = json.dumps(report, separators=(",", ":"))
    output.write_text(f"{text}\n", encoding="utf-8")
    return report


def report_from_snapshot(
    meta: dict[str, Any],
    snapshot: dict[str, Any],
    staging_seal: str,
    evaluation_seq: int,
) -> dict[str, Any]:
    gates_passed = sum(1 for gate in snapshot["gate_results"] if gate["passed"])
    gates_failed = len(snapshot["gate_results"]) - gates_passed
    qc_tests_required = len(meta["policy"]["required_qc_tests"])
    qc_tests_approved = sum(1 for row in meta["qc_records"] if row["status"] == "approved")
    equipment_units = sum(1 for row in meta["equipment"] if row["used_in_batch"])
    equipment_released = sum(
        1 for row in meta["equipment"] if row["used_in_batch"] and row["status"] == "released"
    )
    env_gate = next(g for g in snapshot["gate_results"] if g["gate"] == "environmental")
    documentation_required = len(meta["policy"]["required_doc_types"])
    documentation_approved = sum(
        1 for row in meta["documentation"] if row["status"] == "approved"
    )
    release_ready = all(gate["passed"] for gate in snapshot["gate_results"])
    return {
        "schema_version": 1,
        "batch_id": meta["batch"]["batch_id"],
        "release_ready": release_ready,
        "status": "released" if release_ready else "hold",
        "gate_results": snapshot["gate_results"],
        "summary": {
            "gates_passed": gates_passed,
            "gates_failed": gates_failed,
            "qc_tests_required": qc_tests_required,
            "qc_tests_approved": qc_tests_approved,
            "equipment_units": equipment_units,
            "equipment_released": equipment_released,
            "environmental_excursions_open": len(env_gate["blockers"]),
            "documentation_required": documentation_required,
            "documentation_approved": documentation_approved,
        },
        "metadata_digest": snapshot["metadata_digest"],
        "staging_seal": staging_seal,
        "evaluation_seq": evaluation_seq,
    }
