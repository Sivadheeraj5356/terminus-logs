"""Documentation completeness gate evaluator."""

from __future__ import annotations

from typing import Any


def evaluate_documentation(meta: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    approved = {
        row["doc_type"]
        for row in meta["documentation"]
        if row["status"] == "approved"
    }
    for doc in meta["policy"]["required_doc_types"]:
        if doc not in approved:
            blockers.append(f"missing-doc:{doc}")
    blockers = sorted(set(blockers))
    return {"gate": "documentation", "passed": not blockers, "blockers": blockers}
