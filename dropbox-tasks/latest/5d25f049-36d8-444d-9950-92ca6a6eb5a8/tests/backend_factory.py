"""Build verifier-owned backend and manifest snapshots."""

from __future__ import annotations

import json
from pathlib import Path


def empty_state(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "backend.json").write_text(json.dumps({"sets": {}, "chains": {}, "rules": {}, "next_handle": 1}))
    (root / "ownership-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "committed": {"generation": 0, "phase": "empty", "entries": []},
                "pending": None,
            }
        )
    )
    (root / "runtime-overrides.json").write_text("{}")
    (root / "audit.jsonl").write_text("")
    return root


def insert_foreign_rule(root: Path, visible_name: str, counter: int = 3) -> None:
    backend = json.loads((root / "backend.json").read_text())
    handle = backend.get("next_handle", 1)
    backend["next_handle"] = handle + 1
    backend.setdefault("rules", {})[str(handle)] = {
        "handle": handle,
        "visible_name": visible_name,
        "annotation": None,
        "action": "allow",
        "src_set": None,
        "dst_set": None,
        "dst_port": 443,
        "chain": "operator",
        "counter": counter,
    }
    backend.setdefault("chains", {}).setdefault("operator", []).append(handle)
    (root / "backend.json").write_text(json.dumps(backend))


def legacy_manifest_v1(root: Path, lineage: str = "rule-legacy-1") -> None:
    doc = {
        "schema_version": 1,
        "committed": {
            "generation": 1,
            "phase": "committed",
            "entries": [
                {
                    "logical_id": lineage,
                    "visible_name": f"pol-rule-{lineage}-deadbeef",
                    "kind": "rule",
                    "generation": 1,
                    "semantic_revision": "abc",
                    "counter_lineage": lineage,
                }
            ],
        },
        "pending": None,
    }
    (root / "ownership-manifest.json").write_text(json.dumps(doc))
