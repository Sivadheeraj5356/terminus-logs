"""Milestone 1 — generation floor projection and manifest floor metadata."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPORT = Path("/app/output/lineage_frontier.json")
SCHEMA_STUB = Path("/app/stubs/schema_level.txt")
LINEAGE = Path("/app/cfg/lineage.toml")
MANIFEST = Path("/app/data/manifest.json")

EMPTY_DIGEST = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _doc() -> dict[str, object]:
    return json.loads(REPORT.read_text(encoding="utf-8"))


def _rebuild() -> None:
    REPORT.unlink(missing_ok=True)
    subprocess.run(["/app/scripts/frontier.sh"], check=True, cwd="/app")


class TestMilestone1:
    def test_report_shape_after_rebuild(self) -> None:
        """The report shape tracks manifest consumers and handoff fields."""
        _rebuild()
        doc = _doc()
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        assert doc["schema_mark"] == int(SCHEMA_STUB.read_text(encoding="utf-8").strip())
        assert set(doc["consumers"]) == {str(row["id"]) for row in manifest["consumers"]}
        for block in doc["consumers"].values():
            assert set(block) == {"stale_inputs", "rebuild_required", "frontier_digest_hex"}
            assert isinstance(block["stale_inputs"], list)
            assert len(block["frontier_digest_hex"]) == 64

    def test_zero_floor_reflected_in_rebuild_output(self) -> None:
        """Manifest zero floor overrides a higher runtime floor and keeps gen-1 stale rows with a non-empty digest."""
        original_manifest = MANIFEST.read_text(encoding="utf-8")
        original_cfg = LINEAGE.read_text(encoding="utf-8")
        original_report = REPORT.read_text(encoding="utf-8") if REPORT.exists() else None
        try:
            manifest = json.loads(original_manifest)
            manifest["consumers"] = [
                row for row in manifest["consumers"] if row["id"] == "consumer_harbor"
            ]
            for row in manifest["consumers"]:
                if row["id"] == "consumer_harbor":
                    row["generation_floor"] = 0
            MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            LINEAGE.write_text(
                original_cfg.replace("generation_floor = 1", "generation_floor = 2"),
                encoding="utf-8",
            )
            _rebuild()
            block = _doc()["consumers"]["consumer_harbor"]
            assert block["stale_inputs"] == ["B"]
            assert block["frontier_digest_hex"] != EMPTY_DIGEST
        finally:
            MANIFEST.write_text(original_manifest, encoding="utf-8")
            LINEAGE.write_text(original_cfg, encoding="utf-8")
            if original_report is None:
                REPORT.unlink(missing_ok=True)
            else:
                REPORT.write_text(original_report, encoding="utf-8")

    def test_raised_floor_collapses_digest_to_empty(self) -> None:
        """When runtime floor filters every ledger finish event, frontier_digest_hex collapses to the empty body."""
        original_manifest = MANIFEST.read_text(encoding="utf-8")
        original_cfg = LINEAGE.read_text(encoding="utf-8")
        original_report = REPORT.read_text(encoding="utf-8") if REPORT.exists() else None
        try:
            manifest = json.loads(original_manifest)
            manifest["consumers"] = [
                row for row in manifest["consumers"] if row["id"] == "consumer_harbor"
            ]
            MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            LINEAGE.write_text(
                original_cfg.replace("generation_floor = 1", "generation_floor = 5"),
                encoding="utf-8",
            )
            _rebuild()
            block = _doc()["consumers"]["consumer_harbor"]
            assert block["frontier_digest_hex"] == EMPTY_DIGEST
        finally:
            MANIFEST.write_text(original_manifest, encoding="utf-8")
            LINEAGE.write_text(original_cfg, encoding="utf-8")
            if original_report is None:
                REPORT.unlink(missing_ok=True)
            else:
                REPORT.write_text(original_report, encoding="utf-8")

    def test_filter_generation_honors_inclusive_floor(self) -> None:
        """Inclusive generation-floor projection keeps gen-equal rows and drops all rows above ledger gen."""
        from eng.ledger_lane import filter_generation

        events = [
            {"kind": "finish", "node": "A", "gen": 1, "seq": 1, "hash": "ha", "rows": 1},
            {"kind": "finish", "node": "B", "gen": 1, "seq": 2, "hash": "hb_new", "rows": 2},
            {"kind": "finish", "node": "C", "gen": 1, "seq": 3, "hash": "hc_ok", "rows": 3},
        ]
        result = filter_generation(events, 1)
        assert result == events
        assert filter_generation(events, 5) == []

    def test_runtime_floor_reload_on_rebuild(self) -> None:
        """Raising runtime generation_floor after startup collapses frontier_digest_hex to the empty body."""
        original_manifest = MANIFEST.read_text(encoding="utf-8")
        original_cfg = LINEAGE.read_text(encoding="utf-8")
        original_report = REPORT.read_text(encoding="utf-8") if REPORT.exists() else None
        try:
            manifest = json.loads(original_manifest)
            manifest["consumers"] = [
                row for row in manifest["consumers"] if row["id"] == "consumer_harbor"
            ]
            MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            _rebuild()
            baseline_harbor = _doc()["consumers"]["consumer_harbor"]
            LINEAGE.write_text(
                original_cfg.replace("generation_floor = 1", "generation_floor = 3"),
                encoding="utf-8",
            )
            _rebuild()
            updated_harbor = _doc()["consumers"]["consumer_harbor"]
            assert updated_harbor["frontier_digest_hex"] != baseline_harbor["frontier_digest_hex"]
            assert updated_harbor["frontier_digest_hex"] == EMPTY_DIGEST
        finally:
            MANIFEST.write_text(original_manifest, encoding="utf-8")
            LINEAGE.write_text(original_cfg, encoding="utf-8")
            if original_report is None:
                REPORT.unlink(missing_ok=True)
            else:
                REPORT.write_text(original_report, encoding="utf-8")

    def test_manifest_zero_floor_keeps_gen_one_via_rebuild(self) -> None:
        """Manifest generation_floor zero alone keeps gen-1 node B in stale_inputs when runtime floor is raised."""
        original_manifest = MANIFEST.read_text(encoding="utf-8")
        original_cfg = LINEAGE.read_text(encoding="utf-8")
        original_report = REPORT.read_text(encoding="utf-8") if REPORT.exists() else None
        try:
            manifest = json.loads(original_manifest)
            manifest["consumers"] = [
                row for row in manifest["consumers"] if row["id"] == "consumer_harbor"
            ]
            for row in manifest["consumers"]:
                if row["id"] == "consumer_harbor":
                    row["generation_floor"] = 0
            MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            LINEAGE.write_text(
                original_cfg.replace("generation_floor = 1", "generation_floor = 2"),
                encoding="utf-8",
            )
            _rebuild()
            block = _doc()["consumers"]["consumer_harbor"]
            assert "B" in block["stale_inputs"]
        finally:
            MANIFEST.write_text(original_manifest, encoding="utf-8")
            LINEAGE.write_text(original_cfg, encoding="utf-8")
            if original_report is None:
                REPORT.unlink(missing_ok=True)
            else:
                REPORT.write_text(original_report, encoding="utf-8")

    def test_lineage_cfg_reload_in_process(self) -> None:
        """Lineage settings reload from disk across in-process build_report calls."""
        from eng.run import build_report

        original_manifest = MANIFEST.read_text(encoding="utf-8")
        original_cfg = LINEAGE.read_text(encoding="utf-8")
        try:
            manifest = json.loads(original_manifest)
            manifest["consumers"] = [
                row for row in manifest["consumers"] if row["id"] == "consumer_harbor"
            ]
            MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            before = build_report()
            assert before["consumers"]["consumer_harbor"]["stale_inputs"] == ["B"]

            patched = original_cfg.replace("generation_floor = 1", "generation_floor = 3")
            LINEAGE.write_text(patched, encoding="utf-8")
            after = build_report()
            harbor = after["consumers"]["consumer_harbor"]
            assert harbor["frontier_digest_hex"] == EMPTY_DIGEST
            assert harbor["frontier_digest_hex"] != before["consumers"]["consumer_harbor"]["frontier_digest_hex"]
        finally:
            MANIFEST.write_text(original_manifest, encoding="utf-8")
            LINEAGE.write_text(original_cfg, encoding="utf-8")

    def test_manifest_reload_in_process(self) -> None:
        """In-process build_report calls re-read manifest.json without module cache."""
        original_manifest = MANIFEST.read_text(encoding="utf-8")
        probe_script = r"""
import json
import sys
from pathlib import Path

from eng.run import build_report

registry = Path("/app/data/manifest.json")
payload = json.loads(sys.argv[1])
registry.write_text(json.dumps(payload["first"], indent=2) + "\n", encoding="utf-8")
first = build_report()
registry.write_text(json.dumps(payload["second"], indent=2) + "\n", encoding="utf-8")
second = build_report()
print(json.dumps({"first": sorted(first["consumers"]), "second": sorted(second["consumers"])}))
"""
        try:
            manifest = json.loads(original_manifest)
            alpha_row = next(row for row in manifest["consumers"] if row["id"] == "consumer_harbor")
            probe_row = {
                "id": "consumer_probe_m1",
                "graph": alpha_row["graph"],
                "ledger": alpha_row["ledger"],
                "consumer": alpha_row["consumer"],
            }
            payload = {
                "first": {"consumers": [alpha_row]},
                "second": {"consumers": [alpha_row, probe_row]},
            }
            proc = subprocess.run(
                ["python3", "-c", probe_script, json.dumps(payload)],
                cwd="/app",
                check=False,
                capture_output=True,
                text=True,
            )
            assert proc.returncode == 0, proc.stderr or proc.stdout
            got = json.loads(proc.stdout.strip())
            assert got["first"] == ["consumer_harbor"]
            assert sorted(got["second"]) == sorted(["consumer_harbor", "consumer_probe_m1"])
        finally:
            MANIFEST.write_text(original_manifest, encoding="utf-8")
