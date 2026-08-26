"""Midpipe chain digest gates for egress-lane and apply."""

from __future__ import annotations

import json
from pathlib import Path

from test_outputs import (
    PATH_EGRESS_LANE,
    PATH_INSPECT_MANIFEST,
    PATH_ROLLBACK_PLAN,
    PATH_WAVE_SNAPSHOT,
    _rebuild_ctl,
    _run,
    reference_midpipe_chain_digest,
    reference_wave_step_sequence_digest,
    validate_ok,
)


class TestMidpipeChainDigest:
    def test_plan_writes_midpipe_chain_digest(self):
        """egress-lane midpipe_chain_digest must bind snapshot release digest and wave order."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        lane = json.loads(Path(PATH_EGRESS_LANE).read_text())
        snapshot = json.loads(Path(PATH_WAVE_SNAPSHOT).read_text())
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        assert "midpipe_chain_digest" in lane
        wave_digest = reference_wave_step_sequence_digest(
            json.loads(Path(PATH_ROLLBACK_PLAN).read_text())["steps"]
        )
        expected = reference_midpipe_chain_digest(
            manifest["capture_sequence"],
            lane["plan_hash"],
            snapshot["manifest_release_digest"],
            wave_digest,
        )
        assert lane["midpipe_chain_digest"] == expected
        assert snapshot["manifest_release_digest"] == manifest["release_digest"]

    def test_apply_rejects_stale_midpipe_chain_digest(self):
        """apply-rollback must fail when midpipe_chain_digest is tampered."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        lane_path = Path(PATH_EGRESS_LANE)
        lane = json.loads(lane_path.read_text())
        saved = lane_path.read_text()
        lane["midpipe_chain_digest"] = "0" * 64
        lane_path.write_text(json.dumps(lane, indent=2))
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode != 0
        lane_path.write_text(saved)


class TestTb3MidpipeChainTraps:
    def test_hidden_midpipe_chain_fixture_binding(self):
        """Hidden probe expects chain digest aligned with wave snapshot release binding."""
        hidden = json.loads(
            (Path(__file__).resolve().parent / "verifier-fixtures" / "tb3-midpipe-chain-trap.json").read_text()
        )
        assert isinstance(hidden.get("probe"), str) and hidden["probe"]
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        lane = json.loads(Path(hidden["lane_path"]).read_text())
        snapshot = json.loads(Path(hidden["snapshot_path"]).read_text())
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        wave_digest = reference_wave_step_sequence_digest(plan["steps"])
        expected = reference_midpipe_chain_digest(
            manifest["capture_sequence"],
            lane["plan_hash"],
            snapshot[hidden["release_field"]],
            wave_digest,
        )
        assert lane[hidden["chain_field"]] == expected

    def test_wave_digest_only_fix_still_fails_chain(self):
        """Correct wave_step_sequence_digest with wrong chain digest must block apply."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        lane_path = Path(PATH_EGRESS_LANE)
        lane = json.loads(lane_path.read_text())
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        lane["wave_step_sequence_digest"] = reference_wave_step_sequence_digest(plan["steps"])
        lane["midpipe_chain_digest"] = "0" * 64
        lane_path.write_text(json.dumps(lane, indent=2))
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode != 0
