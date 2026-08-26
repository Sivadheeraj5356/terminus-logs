"""Verifier for fleet unit constraint synthesizer task."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tarfile
from collections import deque
from pathlib import Path
from typing import Any

import pytest

APP = Path("/app")
ENV = APP / "environment"
TAR_PATH = APP / "output" / "fleet_units.tar"
TRACE_PATH = APP / "output" / "restart_trace.json"
SCHEMA_VER = "fleet.unit.v1"
SEED = "23"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_entries_digest(entries: list[dict[str, str]]) -> str:
    canon = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return _sha256_hex(canon)


def _canonical_scenarios_digest(scenarios: list[dict[str, Any]]) -> str:
    canon = json.dumps(scenarios, sort_keys=True, separators=(",", ":")).encode()
    return _sha256_hex(canon)


def _run_pipeline() -> None:
    env = os.environ.copy()
    env["TB_FLEET_SEED"] = SEED
    for path in (TAR_PATH, TRACE_PATH):
        if path.exists():
            path.unlink()
    subprocess.run(
        ["bash", str(ENV / "scripts" / "fleet_pipeline.sh")],
        check=True,
        env=env,
    )


def _load_tar() -> tuple[dict[str, Any], dict[str, str]]:
    manifest: dict[str, Any] = {}
    units: dict[str, str] = {}
    with tarfile.open(TAR_PATH, "r") as tar:
        for member in tar.getmembers():
            if member.name == "manifest.json":
                manifest = json.loads(tar.extractfile(member).read().decode())
            elif member.name.startswith("units/") and member.isfile():
                units[member.name.split("/", 1)[1]] = tar.extractfile(member).read().decode()
    return manifest, units


def _unit_field(body: str, key: str) -> list[str]:
    prefix = f"{key}="
    for line in body.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].split()
    return []


def _requires_graph(units: dict[str, str]) -> dict[str, list[str]]:
    return {name: _unit_field(body, "Requires") for name, body in units.items()}


def _reverse_topo_stops(trigger: str, requires: dict[str, list[str]]) -> list[str]:
    """Dependents-before-dependencies order for Requires closure."""
    closure: set[str] = {trigger}
    changed = True
    while changed:
        changed = False
        for unit, deps in requires.items():
            for dep in deps:
                if dep in closure and unit not in closure:
                    closure.add(unit)
                    changed = True
    stop_set = set(closure)
    stop_set.discard(trigger)
    indeg = {u: 0 for u in stop_set}
    adj: dict[str, list[str]] = {u: [] for u in stop_set}
    for unit in stop_set:
        for dep in requires.get(unit, []):
            if dep in stop_set:
                adj[unit].append(dep)
                indeg[dep] += 1
    q = deque(sorted(u for u, d in indeg.items() if d == 0))
    order: list[str] = []
    while q:
        node = q.popleft()
        order.append(node)
        for nxt in sorted(adj.get(node, [])):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    return order


def pipeline_run() -> None:
    _run_pipeline()


@pytest.fixture(scope="module", autouse=True)
def _pipeline_once() -> None:
    pipeline_run()


def test_f01_pipeline_outputs() -> None:
    """pipeline regenerates tarball and restart trace."""
    assert TAR_PATH.is_file()
    assert TRACE_PATH.is_file()


def test_f02_manifest_schema() -> None:
    """manifest schema_version and bundle_digest defined as tarball seals."""
    manifest, _ = _load_tar()
    assert manifest["schema_version"] == SCHEMA_VER
    assert isinstance(manifest["bundle_digest"], str) and manifest["bundle_digest"]


def test_f03_entry_digests() -> None:
    """entries carry per-unit sha256 matching tarball bytes."""
    manifest, units = _load_tar()
    by_name = {e["name"]: e for e in manifest["entries"]}
    assert sorted(by_name) == sorted(units)
    for name, body in units.items():
        digest = _sha256_hex(body.encode())
        assert by_name[name]["sha256"] == digest


def test_f04_systemd_analyze() -> None:
    """units pass offline systemd-analyze verify."""
    work = Path("/tmp/fleet_verify")
    subprocess.run(
        ["bash", str(ENV / "scripts" / "analyze_units.sh"), str(work)],
        check=True,
    )


def test_f05_worker_cli_precedence() -> None:
    """cli RestartSec and env Restart precedence on acme-worker.service."""
    _, units = _load_tar()
    body = units["acme-worker.service"]
    assert "Restart=always" in body
    assert "RestartSec=12" in body


def test_f06_cache_cli_lists() -> None:
    """cli list replacement for acme-cache.service After and Requires."""
    _, units = _load_tar()
    body = units["acme-cache.service"]
    assert "After=acme-collector.service" in body
    assert "Requires=acme-collector.service" in body
    assert "acme-reporter.service" not in body


def test_f07_collector_slice_env() -> None:
    """env Slice override on acme-collector.service."""
    _, units = _load_tar()
    body = units["acme-collector.service"]
    assert "Slice=fleet.work.slice" in body


def test_f08_trace_schema() -> None:
    """restart trace schema_version and trace_digest."""
    trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
    assert trace["schema_version"] == SCHEMA_VER
    assert isinstance(trace["trace_digest"], str) and trace["trace_digest"]


def test_f09_smoke_restart_scope() -> None:
    """smoke scenario restarts only the trigger unit."""
    trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
    smoke = next(s for s in trace["scenarios"] if s["scenario"] == "iota_smoke")
    assert smoke["trigger"] == "acme-reporter.service"
    touched = {e["unit"] for e in smoke["ordered_events"]}
    assert touched == {"acme-reporter.service"}


def test_f10_graded_restart_order() -> None:
    """graded scenarios stop dependents before dependencies, then the trigger."""
    trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
    _, units = _load_tar()
    requires = _requires_graph(units)
    for scenario in trace["scenarios"]:
        if scenario["scenario"] == "iota_smoke":
            continue
        stops = [e["unit"] for e in scenario["ordered_events"] if e["action"] == "stop"]
        assert stops[-1] == scenario["trigger"]
        expected = _reverse_topo_stops(scenario["trigger"], requires)
        assert stops[:-1] == expected


def test_f11_event_pairs() -> None:
    """each unit emits stop then start with monotonic ts_index."""
    trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
    for scenario in trace["scenarios"]:
        events = scenario["ordered_events"]
        starts = [e for e in events if e["action"] == "start"]
        assert len(starts) == 1
        assert starts[0]["unit"] == scenario["trigger"]
        for prev, cur in zip(events, events[1:]):
            assert cur["ts_index"] > prev["ts_index"]


def test_f12_idempotent_digest() -> None:
    """repeated runs keep bundle_digest and trace_digest stable."""
    manifest1, _ = _load_tar()
    trace1 = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
    first_bundle = manifest1["bundle_digest"]
    first_trace = trace1["trace_digest"]
    _run_pipeline()
    manifest2, _ = _load_tar()
    trace2 = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
    assert manifest2["bundle_digest"] == first_bundle
    assert trace2["trace_digest"] == first_trace


def test_f13_slice_kind() -> None:
    """slice units tagged with kind slice in manifest."""
    manifest, _ = _load_tar()
    kinds = {e["name"]: e["kind"] for e in manifest["entries"]}
    assert kinds["fleet.work.slice"] == "slice"
    assert kinds["acme-collector.service"] == "service"


def test_f14_bundle_digest_matches_entries() -> None:
    """bundle_digest defined as the sorted-entry seal over canonical entries JSON."""
    manifest, _ = _load_tar()
    entries = sorted(
        [{"name": e["name"], "kind": e["kind"], "sha256": e["sha256"]} for e in manifest["entries"]],
        key=lambda row: row["name"],
    )
    expected = _canonical_entries_digest(entries)
    assert manifest["bundle_digest"] == expected


def test_f15_trace_digest_matches_scenarios() -> None:
    """trace_digest defined as the scenario-array seal over canonical scenarios JSON."""
    trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
    expected = _canonical_scenarios_digest(trace["scenarios"])
    assert trace["trace_digest"] == expected
    scenario_names = sorted(s["scenario"] for s in trace["scenarios"])
    fixture_names = sorted(p.stem for p in (ENV / "data" / "scenarios").glob("*.json"))
    assert scenario_names == fixture_names


def test_f16_worker_after_requires_wants_separate() -> None:
    """After, Requires, and Wants stay distinct on acme-worker.service."""
    _, units = _load_tar()
    body = units["acme-worker.service"]
    after = _unit_field(body, "After")
    requires = _unit_field(body, "Requires")
    wants = _unit_field(body, "Wants")
    assert after == ["acme-cache.service"]
    assert requires == ["acme-cache.service"]
    assert wants == ["acme-collector.service"]


def test_f17_mu_reporter_precedes_worker() -> None:
    """mu_cross_restart stops dependents before the trigger along Requires edges."""
    trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
    scenario = next(s for s in trace["scenarios"] if s["scenario"] == "mu_cross_restart")
    assert scenario["trigger"] == "acme-worker.service"
    stops = [e["unit"] for e in scenario["ordered_events"] if e["action"] == "stop"]
    assert stops.index("acme-reporter.service") < stops.index("acme-worker.service")


def test_f18_lambda_worker_precedes_cache() -> None:
    """lambda_requires_order walks Requires closure toward dependents before dependencies."""
    trace = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
    scenario = next(s for s in trace["scenarios"] if s["scenario"] == "lambda_requires_order")
    assert scenario["trigger"] == "acme-cache.service"
    stops = [e["unit"] for e in scenario["ordered_events"] if e["action"] == "stop"]
    assert stops.index("acme-worker.service") < stops.index("acme-cache.service")
