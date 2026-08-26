from __future__ import annotations

from pathlib import Path

from .manifest import load_manifest


def build_report() -> dict[str, object]:
    manifest = load_manifest(Path("/app/data/manifest.json"))
    schema_mark = int(Path("/app/stubs/schema_level.txt").read_text(encoding="utf-8").strip())
    consumers: dict[str, dict[str, object]] = {}
    for entry in manifest:
        consumers[str(entry["id"])] = {
            "stale_inputs": [],
            "rebuild_required": False,
            "frontier_digest_hex": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        }
    return {"schema_mark": schema_mark, "consumers": consumers}
