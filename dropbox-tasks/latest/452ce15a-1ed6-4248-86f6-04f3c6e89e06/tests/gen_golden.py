#!/usr/bin/env python3
"""Generate golden digest fixtures (run from tests/ with chip files on disk)."""
from __future__ import annotations

import json
import sys
import types
import hashlib
from pathlib import Path

pytest = types.ModuleType("pytest")
pytest.fixture = lambda *a, **k: (lambda f: f)


class _Raises:
    def __init__(self, *args: object) -> None:
        pass

    def __enter__(self) -> object:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


pytest.raises = _Raises
pytest.mark = types.SimpleNamespace(parametrize=lambda *a, **k: (lambda f: f))
sys.modules["pytest"] = pytest
sys.path.insert(0, str(Path(__file__).parent))
import test_outputs as mod  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LOCAL_FIXTURES = ROOT / "environment" / "fixtures"
DOCKER_PREFIX = "/app/environment/fixtures"


def _source_digest_docker(path: Path) -> str:
    local = LOCAL_FIXTURES / path.name
    return "sha256:" + hashlib.sha256(local.read_bytes()).hexdigest()


mod._source_digest = _source_digest_docker


class DockerChipPath:
    def __init__(self, name: str) -> None:
        self.name = name
        self.local = LOCAL_FIXTURES / name

    def read_text(self) -> str:
        return self.local.read_text()

    def read_bytes(self) -> bytes:
        return self.local.read_bytes()

    def __str__(self) -> str:
        return f"{DOCKER_PREFIX}/{self.name}"


def export(name: str, chips: list[str]) -> dict:
    mod.OUT_DIR = Path("/tmp/piezo_golden_out")
    mod.MANIFEST = mod.OUT_DIR / "resonance_manifest.json"
    mod.OUT_DIR.mkdir(parents=True, exist_ok=True)
    if mod.MANIFEST.exists():
        mod.MANIFEST.unlink()
    as_of = "2024-07-01"
    paths = [DockerChipPath(chip) for chip in chips]
    merged = mod._merge_batch(paths, as_of)  # type: ignore[arg-type]
    expected = mod._expected_report(paths, as_of, None)  # type: ignore[arg-type]
    pgh_body = mod._profile_graph_hash_body(
        merged["all_revisions"], merged["all_segment_overrides"]
    )
    fam_payloads: list[dict] = []
    fam_digests: list[str] = []
    for fam in expected["families"]:
        fam_id = fam["family_id"]
        family = merged["families"][fam_id]
        profile = family["profile"]
        rows = mod._rows_from_profile(profile, family["resolved"])
        body = mod._resonance_digest_body(
            fam_id,
            profile["chip_id"],
            profile["profile_id"],
            expected["profile_graph_hash"],
            as_of,
            expected["input_fingerprint"],
            fam["branch_generation"],
            family["lineage_revisions"],
            family["provenance"],
            rows,
        )
        fam_payloads.append(
            {
                "family_id": fam_id,
                "branch_generation": fam["branch_generation"],
                "resonance_digest": fam["resonance_digest"],
                "payload": body,
            }
        )
        fam_digests.append(fam["resonance_digest"])
    batch_body = mod._batch_digest_body(
        as_of,
        expected["input_fingerprint"],
        expected["profile_graph_hash"],
        expected["batch_generation"],
        fam_digests,
    )
    return {
        "as_of_date": as_of,
        "chip_paths": [str(path) for path in paths],
        "input_fingerprint": expected["input_fingerprint"],
        "profile_graph_hash": expected["profile_graph_hash"],
        "profile_graph_hash_body": pgh_body,
        "batch_generation": expected["batch_generation"],
        "family_count": expected["family_count"],
        "batch_digest": expected["batch_digest"],
        "batch_digest_payload": batch_body,
        "families": fam_payloads,
    }


def main() -> None:
    out = Path(__file__).parent / "testdata" / "golden"
    out.mkdir(parents=True, exist_ok=True)
    cases = {
        "single_family": ["golden_single.chip"],
        "multi_family": ["golden_multi_a.chip", "golden_multi_b.chip"],
    }
    for name, chips in cases.items():
        data = export(name, chips)
        target = out / f"{name}.json"
        target.write_text(json.dumps(data, indent=2) + "\n")
        print(f"wrote {target}")


if __name__ == "__main__":
    main()
