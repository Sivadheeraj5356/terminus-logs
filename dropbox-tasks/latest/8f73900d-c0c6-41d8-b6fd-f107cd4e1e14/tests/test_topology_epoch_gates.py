"""Topology epoch latch — graph freeze between plan emit and validate/apply."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from test_outputs import (
    PATH_INSPECT_MANIFEST,
    PATH_ROLLBACK_GRAPH,
    PATH_ROLLBACK_PLAN,
    _rebuild_ctl,
    _run,
    pipeline_through_validate,
)

PATH_TOPOLOGY_LATCH = "/app/state/topology-epoch-latch.json"
PATH_EGRESS_LANE = "/app/state/egress-lane-midpipe.json"


def reference_graph_epoch_digest(graph: dict) -> str:
    lines = []
    for svc in sorted(graph):
        for dep in sorted(graph.get(svc) or []):
            lines.append(f"dep|{svc}|{dep}")
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def reference_latch_digest(capture_seq: int, plan_hash: str, graph_epoch: str) -> str:
    return hashlib.sha256(
        f"topo-latch|{capture_seq}|{plan_hash}|{graph_epoch}".encode()
    ).hexdigest()


class TestTopologyEpochPlanEmit:
    def test_plan_writes_topology_epoch_latch(self):
        """plan emit must write topology-epoch-latch after egress-lane midpipe."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        latch_path = Path(PATH_TOPOLOGY_LATCH)
        assert latch_path.is_file()
        latch = json.loads(latch_path.read_text())
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        graph = json.loads(Path(PATH_ROLLBACK_GRAPH).read_text())
        assert latch["schema"] == "rollback.topology-epoch.v1"
        assert latch["capture_sequence"] == manifest["capture_sequence"]
        assert latch["plan_hash"] == plan["hash"]
        epoch = reference_graph_epoch_digest(graph)
        assert latch["graph_epoch_digest"] == epoch
        assert latch["latch_digest"] == reference_latch_digest(
            latch["capture_sequence"], latch["plan_hash"], epoch
        )

    def test_topology_latch_follows_egress_lane_artifact(self):
        """topology-epoch-latch must exist only after a successful plan that also wrote egress-lane."""
        _rebuild_ctl()
        Path(PATH_TOPOLOGY_LATCH).unlink(missing_ok=True)
        Path(PATH_EGRESS_LANE).unlink(missing_ok=True)
        _run(["/app/bin/rollbackctl", "inspect"])
        assert not Path(PATH_TOPOLOGY_LATCH).is_file()
        _run(["/app/bin/rollbackctl", "plan"])
        assert Path(PATH_EGRESS_LANE).is_file()
        assert Path(PATH_TOPOLOGY_LATCH).is_file()


class TestTopologyEpochValidateGates:
    def test_validate_requires_topology_epoch_latch(self):
        """validate must refuse when topology-epoch-latch.json is missing after plan."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        Path(PATH_TOPOLOGY_LATCH).unlink()
        proc = _run(["/app/bin/rollbackctl", "validate"])
        assert proc.returncode != 0

    def test_validate_rejects_stale_topology_latch_digest(self):
        """validate must refuse when latch_digest fails live recompute."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        latch_path = Path(PATH_TOPOLOGY_LATCH)
        latch = json.loads(latch_path.read_text())
        latch["latch_digest"] = "b" * 64
        latch_path.write_text(json.dumps(latch, indent=2) + "\n")
        proc = _run(["/app/bin/rollbackctl", "validate"])
        assert proc.returncode != 0

    def test_graph_mutate_after_plan_fails_validate(self):
        """Mutating rollback-graph after plan without re-emit must fail validate."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        graph_path = Path(PATH_ROLLBACK_GRAPH)
        backup = graph_path.read_text()
        try:
            graph = json.loads(backup)
            graph["alert-dispatch"] = list(graph.get("alert-dispatch") or []) + ["ledger-db"]
            graph_path.write_text(json.dumps(graph, indent=2) + "\n")
            proc = _run(["/app/bin/rollbackctl", "validate"])
            assert proc.returncode != 0
        finally:
            graph_path.write_text(backup)


class TestTopologyEpochApplyGates:
    def test_apply_requires_topology_epoch_latch(self):
        """apply-rollback must refuse when topology latch is removed after validate."""
        pipeline_through_validate()
        Path(PATH_TOPOLOGY_LATCH).unlink()
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode != 0

    def test_egress_lane_only_without_latch_still_fails_validate(self):
        """Egress-lane midpipe alone without topology latch must still fail validate."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        assert Path(PATH_EGRESS_LANE).is_file()
        Path(PATH_TOPOLOGY_LATCH).unlink(missing_ok=True)
        proc = _run(["/app/bin/rollbackctl", "validate"])
        assert proc.returncode != 0


class TestTb3TopologyEpochTraps:
    def test_hidden_topology_fixture_changes_graph_epoch(self):
        """Hidden topology fixture must yield a distinct graph_epoch_digest vs bundled graph."""
        fixture = Path(__file__).resolve().parent / "verifier-fixtures" / "tb3-topology-epoch-trap.json"
        hidden = Path("/opt/verifier-fixtures/tb3-topology-epoch-trap.json")
        if not hidden.is_file():
            hidden.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fixture, hidden)
        bundled = json.loads(Path(PATH_ROLLBACK_GRAPH).read_text())
        trap = json.loads(hidden.read_text())
        assert reference_graph_epoch_digest(trap) != reference_graph_epoch_digest(bundled)

    def test_hidden_topology_plan_binding_under_fixture_graph(self):
        """Under hidden topology fixture, plan latch graph_epoch_digest matches fixture reference."""
        fixture = Path(__file__).resolve().parent / "verifier-fixtures" / "tb3-topology-epoch-trap.json"
        hidden = Path("/opt/verifier-fixtures/tb3-topology-epoch-trap.json")
        if not hidden.is_file():
            hidden.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fixture, hidden)
        graph_path = Path(PATH_ROLLBACK_GRAPH)
        backup = graph_path.read_text()
        try:
            shutil.copyfile(hidden, graph_path)
            _rebuild_ctl()
            _run(["/app/bin/rollbackctl", "inspect"])
            _run(["/app/bin/rollbackctl", "plan"])
            latch = json.loads(Path(PATH_TOPOLOGY_LATCH).read_text())
            trap = json.loads(graph_path.read_text())
            epoch = reference_graph_epoch_digest(trap)
            assert latch["graph_epoch_digest"] == epoch
            assert latch["latch_digest"] == reference_latch_digest(
                latch["capture_sequence"], latch["plan_hash"], epoch
            )
        finally:
            graph_path.write_text(backup)
