"""Egress-lane midpipe and rollback-run-ledger apply gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from test_outputs import (
    PATH_EGRESS_LANE,
    PATH_INSPECT_MANIFEST,
    PATH_ROLLBACK_COMPLETE,
    PATH_ROLLBACK_PLAN,
    PATH_RUN_LEDGER,
    _rebuild_ctl,
    _run,
    reference_wave_step_sequence_digest,
    validate_ok,
)


class TestEgressLanemidpipe:
    def test_plan_writes_egress_lane_midpipe(self):
        """plan emit must write egress-lane-midpipe.json after wave snapshot."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        lane_path = Path(PATH_EGRESS_LANE)
        assert lane_path.is_file()
        lane = json.loads(lane_path.read_text())
        assert "wave_step_sequence_digest" in lane
        assert "plan_hash" in lane
        assert "capture_sequence" in lane

    def test_egress_lane_wave_sequence_digest_matches_reference(self):
        """wave_step_sequence_digest must bind plan steps in array order."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        lane = json.loads(Path(PATH_EGRESS_LANE).read_text())
        expected = reference_wave_step_sequence_digest(plan["steps"])
        assert lane["wave_step_sequence_digest"] == expected
        assert lane["plan_hash"] == plan["hash"]

    def test_egress_lane_capture_sequence_matches_manifest(self):
        """egress-lane capture_sequence must match inspect-manifest."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        lane = json.loads(Path(PATH_EGRESS_LANE).read_text())
        assert lane["capture_sequence"] == manifest["capture_sequence"]


class TestEgressLaneApplyGates:
    def test_apply_requires_egress_lane_midpipe(self):
        """apply-rollback must fail when egress-lane-midpipe.json is missing."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        lane_path = Path(PATH_EGRESS_LANE)
        saved = lane_path.read_text()
        lane_path.unlink()
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode != 0
        lane_path.write_text(saved)

    def test_apply_rejects_stale_egress_lane_digest(self):
        """apply-rollback must fail when wave_step_sequence_digest is tampered."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        lane_path = Path(PATH_EGRESS_LANE)
        lane = json.loads(lane_path.read_text())
        saved = lane_path.read_text()
        lane["wave_step_sequence_digest"] = "0" * 64
        lane_path.write_text(json.dumps(lane, indent=2))
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode != 0
        lane_path.write_text(saved)

    def test_apply_rejects_replay_when_run_ledger_matches(self):
        """First apply binds ledger fields to live plan/manifest; identical second apply fails."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        env = {"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"}
        first = _run(["bash", "/app/deploy/scripts/apply-rollback.sh"], env=env)
        assert first.returncode == 0
        ledger_path = Path(PATH_RUN_LEDGER)
        assert ledger_path.is_file()
        ledger = json.loads(ledger_path.read_text())
        assert ledger["apply_epoch"] == 1
        assert ledger["last_plan_hash"] == plan["hash"]
        assert ledger["last_capture_sequence"] == manifest["capture_sequence"]
        second = _run(["bash", "/app/deploy/scripts/apply-rollback.sh"], env=env)
        assert second.returncode != 0
        Path(PATH_ROLLBACK_COMPLETE).unlink(missing_ok=True)
        Path(PATH_RUN_LEDGER).unlink(missing_ok=True)

    def test_wave_snapshot_only_fix_still_fails_apply(self):
        """Fixing wave snapshot without egress-lane digest must not satisfy apply."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        lane_path = Path(PATH_EGRESS_LANE)
        lane = json.loads(lane_path.read_text())
        saved_lane = lane_path.read_text()
        lane["wave_step_sequence_digest"] = "deadbeef" * 8
        lane_path.write_text(json.dumps(lane, indent=2))
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode != 0
        lane_path.write_text(saved_lane)


class TestTb3EgressLaneTraps:
    def test_hidden_egress_lane_fixture_binding(self):
        """Hidden probe expects egress-lane fields aligned with manifest and plan."""
        hidden = json.loads(
            (Path(__file__).resolve().parent / "verifier-fixtures" / "tb3-egress-lane-trap.json").read_text()
        )
        assert isinstance(hidden.get("probe"), str) and hidden["probe"]
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        lane = json.loads(Path(hidden["lane_path"]).read_text())
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        assert lane[hidden["manifest_field"]] == manifest[hidden["manifest_field"]]
        assert lane[hidden["plan_hash_field"]] == plan["hash"]
        digest = reference_wave_step_sequence_digest(plan["steps"])
        assert lane[hidden["digest_field"]] == digest

    def test_hidden_ingest_only_export_lane_digest_patch_still_fails_apply(self):
        """Manually patching egress-lane with sorted-step digest must block apply."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        lane_path = Path(PATH_EGRESS_LANE)
        lane = json.loads(lane_path.read_text())
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        sorted_lines = [f"lane|step|{step}" for step in sorted(plan["steps"])]
        lane["wave_step_sequence_digest"] = hashlib.sha256(
            "\n".join(sorted_lines).encode()
        ).hexdigest()
        lane_path.write_text(json.dumps(lane, indent=2))
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode != 0
