"""Witness quorum validate seal and apply gates."""

from __future__ import annotations

import json
from pathlib import Path

from test_outputs import (
    APP,
    PATH_EGRESS_LANE,
    PATH_INSPECT_MANIFEST,
    PATH_ROLLBACK_PLAN,
    PATH_WITNESS_BUNDLE,
    _rebuild_ctl,
    _run,
    pipeline_through_validate,
    reference_zone_quorum_token,
)


class TestWitnessQuorumValidate:
    def test_validate_writes_witness_bundle(self):
        """validate must seal rollback-witness-bundle.json after plan bindings pass."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        witness_path = Path(PATH_WITNESS_BUNDLE)
        if witness_path.is_file():
            witness_path.unlink()
        proc = _run(["/app/bin/rollbackctl", "validate"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert witness_path.is_file()
        bundle = json.loads(witness_path.read_text())
        lane = json.loads(Path(PATH_EGRESS_LANE).read_text())
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        assert bundle["midpipe_chain_digest"] == lane["midpipe_chain_digest"]
        assert bundle["capture_sequence"] == manifest["capture_sequence"]
        assert bundle["plan_hash"] == plan["hash"]
        status = json.loads((APP / "state/deploy-status.json").read_text())
        expected_token = reference_zone_quorum_token(
            status["incident_id"],
            "primary",
            lane["midpipe_chain_digest"],
            manifest["capture_sequence"],
            plan["hash"],
        )
        assert bundle["zone_quorum_token"] == expected_token

    def test_apply_requires_validate_witness(self):
        """apply-rollback must fail when validate never sealed witness bundle."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        witness_path = Path(PATH_WITNESS_BUNDLE)
        if witness_path.is_file():
            witness_path.unlink()
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode != 0

    def test_plan_emit_alone_cannot_apply_without_validate(self):
        """Plan emit without validate witness seal must block apply."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode != 0


class TestWitnessQuorumApply:
    def test_apply_rejects_stale_witness_chain_binding(self):
        """apply-rollback must fail when witness midpipe_chain_digest is tampered."""
        pipeline_through_validate()
        witness_path = Path(PATH_WITNESS_BUNDLE)
        bundle = json.loads(witness_path.read_text())
        saved = witness_path.read_text()
        bundle["midpipe_chain_digest"] = "0" * 64
        witness_path.write_text(json.dumps(bundle, indent=2))
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode != 0
        witness_path.write_text(saved)


class TestTb3WitnessQuorumTraps:
    def test_hidden_witness_fixture_binding(self):
        """Hidden probe expects zone_quorum_token aligned with egress-lane chain digest."""
        hidden = json.loads(
            (Path(__file__).resolve().parent / "verifier-fixtures" / "tb3-witness-quorum-trap.json").read_text()
        )
        pipeline_through_validate()
        bundle = json.loads(Path(hidden["bundle_path"]).read_text())
        lane = json.loads(Path(hidden["lane_path"]).read_text())
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        status = json.loads((APP / "state/deploy-status.json").read_text())
        assert bundle[hidden["chain_field"]] == lane[hidden["chain_field"]]
        expected = reference_zone_quorum_token(
            status["incident_id"],
            hidden["zone"],
            lane[hidden["chain_field"]],
            manifest["capture_sequence"],
            plan["hash"],
        )
        assert bundle[hidden["token_field"]] == expected

    def test_egress_lane_only_fix_still_fails_without_validate_witness(self):
        """Correct egress-lane without validate witness seal must block apply."""
        _rebuild_ctl()
        witness_path = Path(PATH_WITNESS_BUNDLE)
        witness_path.unlink(missing_ok=True)
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        assert not witness_path.is_file()
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode != 0
