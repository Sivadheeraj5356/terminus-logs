"""Quality-control, equipment, environmental, and documentation gate orchestration."""

from __future__ import annotations

from typing import Any

from trust.documentation_gate import evaluate_documentation
from trust.environmental_gate import evaluate_environmental
from trust.equipment_gate import evaluate_equipment
from trust.qc_gate import evaluate_qc


def evaluate_all(meta: dict[str, Any]) -> list[dict[str, Any]]:
    gates = [
        evaluate_qc(meta),
        evaluate_equipment(meta),
        evaluate_environmental(meta),
        evaluate_documentation(meta),
    ]
    gates.sort(key=lambda row: row["gate"])
    return gates
