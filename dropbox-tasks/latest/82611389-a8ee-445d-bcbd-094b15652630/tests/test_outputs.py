"""Verifier tests for fleet release build planner."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import time
import uuid
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

APP = Path("/app")
BINARY = Path("/tmp/fleetd-test")
GO_BIN = os.environ.get("GO_BIN", "/usr/local/go/bin/go")
POLICY_PATH = APP / "config/fleet-policy.toml"
REPORT_PATH = APP / "output/fleet-build-compliance.json"
REPORT_JSON = "/app/output/fleet-build-compliance.json"
SNAPSHOT_PATH = APP / "var/fleet-stage/build-train-probe.json"
SNAPSHOT_JSON = "/app/var/fleet-stage/build-train-probe.json"
STAGE_ROOT = APP / "var/fleet-stage"
EMIT_SCRIPT = APP / "scripts/emit-fleet-build-audit.sh"
MANIFEST_PATH = APP / "data/module-manifest.csv"
CYCLE_MANIFEST = APP / "data/cycle-manifest.csv"
LOW_VERSION_MANIFEST = APP / "data/low-version-manifest.csv"
HIGH_VERSION_MANIFEST = APP / "data/high-version-manifest.csv"
UNAPPROVED_MANIFEST = APP / "data/unapproved-manifest.csv"
TIEBREAK_MANIFEST = APP / "data/tiebreak-manifest.csv"
DIAMOND_MANIFEST = APP / "data/diamond-manifest.csv"
MISSING_DEP_MANIFEST = APP / "data/missing-dep-manifest.csv"
EXPECTED_ORDER = ["auth-core", "billing-api", "ingest-worker", "notify-hub", "gateway"]
TIEBREAK_ORDER = ["a-unit", "c-unit", "b-unit", "d-unit"]
DIAMOND_ORDER = ["root-unit", "left-unit", "right-unit", "merge-unit"]
SECURE_POLICY = """require_registry_approval = true
debug_endpoints_enabled = false
min_module_versions = billing-api:2.0.0,ingest-worker:1.1.0
fleet_release_pin = fleet-2025.11.4
"""
INSECURE_POLICY = """require_registry_approval = false
debug_endpoints_enabled = true
min_module_versions = billing-api:1.0.0,ingest-worker:1.0.0
fleet_release_pin = fleet-dev-unverified
"""

_ACTIVE: dict[str, str] = {"base": "", "instance": ""}


def reference_topo_order(module_ids: list[str], edges: list[tuple[str, str]]) -> list[str]:
    """Independent Kahn order: sort initial ready set; append sorted newly-ready batches only."""
    indeg = {m: 0 for m in module_ids}
    adj: dict[str, list[str]] = {m: [] for m in module_ids}
    for dep, node in edges:
        adj[dep].append(node)
        indeg[node] += 1
    queue = sorted(m for m, d in indeg.items() if d == 0)
    order: list[str] = []
    while queue:
        cur = queue.pop(0)
        order.append(cur)
        newly: list[str] = []
        for nxt in sorted(adj[cur]):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                newly.append(nxt)
        queue.extend(sorted(newly))
    if len(order) != len(module_ids):
        raise ValueError("cycle")
    return order


def reference_semver_gte(version: str, minimum: str) -> bool:
    """Independent numeric X.Y.Z comparison used by verifier references."""

    def parts(v: str) -> list[int]:
        out = [0, 0, 0]
        for i, p in enumerate(v.split(".")[:3]):
            out[i] = int(p)
        return out

    return parts(version) >= parts(minimum)


def reference_plan_digest(modules: list[str]) -> str:
    """Independent plan digest: SHA-256 of module_id + newline in plan order."""
    h = hashlib.sha256()
    for mid in modules:
        h.update(mid.encode())
        h.update(b"\n")
    return h.hexdigest()


def reference_plan_seal(plan_digest_hex: str, release_pin: str, module_count: int) -> str:
    """Independent plan seal with domain byte 0x46."""
    h = hashlib.sha256()
    h.update(bytes([0x46]))
    h.update(bytes.fromhex(plan_digest_hex))
    h.update(release_pin.encode())
    h.update(int(module_count).to_bytes(4, "big"))
    return h.hexdigest()


def reference_plan_seal_no_domain(plan_digest_hex: str, release_pin: str, module_count: int) -> str:
    h = hashlib.sha256()
    h.update(bytes.fromhex(plan_digest_hex))
    h.update(release_pin.encode())
    h.update(int(module_count).to_bytes(4, "big"))
    return h.hexdigest()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http_json(
    method: str,
    path: str,
    body: dict | None = None,
    *,
    base: str | None = None,
) -> tuple[int, dict]:
    target = base or _ACTIVE["base"]
    assert target, "no active fleetd base URL"
    payload = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        target + path,
        data=payload,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        return exc.code, json.loads(raw) if raw else {}


def http_status(
    method: str,
    path: str,
    body: dict | None = None,
    *,
    base: str | None = None,
) -> int:
    status, _ = http_json(method, path, body, base=base)
    return status


def policy_digest() -> str:
    return hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()


def _go_env() -> dict[str, str]:
    env = {**os.environ, "PATH": "/usr/local/go/bin:" + os.environ.get("PATH", "")}
    env.setdefault("CGO_ENABLED", "0")
    env.setdefault("GOPROXY", "off")
    env.setdefault("GOSUMDB", "off")
    return env


def _build_binary() -> None:
    build = subprocess.run(
        [GO_BIN, "build", "-o", str(BINARY), "./cmd/fleetd"],
        cwd=APP,
        capture_output=True,
        text=True,
        env=_go_env(),
    )
    assert build.returncode == 0, build.stderr


def _wait_for_own_server(base: str, instance: str, timeout_sec: float = 8.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            status, body = http_json("GET", "/health", base=base)
            if status == 200 and body.get("instance_id") == instance:
                return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def _start_server(
    db_path: Path,
    policy_text: str,
    manifest_path: Path = MANIFEST_PATH,
) -> tuple[subprocess.Popen[str], str, str]:
    POLICY_PATH.write_text(policy_text)
    port = _free_port()
    instance = uuid.uuid4().hex
    base = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["REGISTRY_DB_PATH"] = str(db_path)
    env["POLICY_PATH"] = str(POLICY_PATH)
    env["MANIFEST_PATH"] = str(manifest_path)
    env["LISTEN_ADDR"] = f"127.0.0.1:{port}"
    env["FLEETD_INSTANCE_ID"] = instance
    proc = subprocess.Popen(
        [str(BINARY)],
        cwd=APP,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if not _wait_for_own_server(base, instance):
        _stop_server(proc)
        pytest.fail(f"server failed to start on {base} with instance {instance}")
    _ACTIVE["base"] = base
    _ACTIVE["instance"] = instance
    return proc, base, instance


def _stop_server(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def _fleetd_emit_audit(env: dict[str, str], *, expect_ok: bool = True) -> subprocess.CompletedProcess[str]:
    env = dict(env)
    env.setdefault("API_BASE", _ACTIVE["base"])
    last: subprocess.CompletedProcess[str] | None = None
    for attempt in range(8):
        last = subprocess.run(
            ["/bin/bash", str(EMIT_SCRIPT)],
            cwd=APP,
            capture_output=True,
            text=True,
            env=env,
        )
        combined = (last.stderr or "") + (last.stdout or "")
        locked = "database is locked" in combined.lower()
        if expect_ok and last.returncode == 0 and REPORT_PATH.is_file():
            break
        if not locked:
            break
        time.sleep(0.25 * (attempt + 1))
    assert last is not None
    if expect_ok:
        assert last.returncode == 0, last.stderr + last.stdout
    return last


@pytest.fixture()
def running_server(tmp_path) -> Iterator[dict[str, object]]:
    """Build and start fleetd with the shipped insecure policy."""
    db_path = tmp_path / "registry.json"
    _build_binary()
    proc, base, instance = _start_server(db_path, INSECURE_POLICY)
    ctx = {
        "db_path": db_path,
        "policy_path": POLICY_PATH,
        "proc": proc,
        "base": base,
        "instance": instance,
    }
    yield ctx
    _stop_server(proc)
    if _ACTIVE.get("instance") == instance:
        _ACTIVE["base"] = ""
        _ACTIVE["instance"] = ""


@pytest.fixture()
def fleetd_reconciled_server(running_server) -> Iterator[dict[str, object]]:
    """Run the build-train audit emitter against the live API."""
    env = os.environ.copy()
    env["REGISTRY_DB_PATH"] = str(running_server["db_path"])
    env["POLICY_PATH"] = str(running_server["policy_path"])
    env["API_BASE"] = str(running_server["base"])
    _fleetd_emit_audit(env)
    assert _wait_for_own_server(str(running_server["base"]), str(running_server["instance"]), 5.0)
    yield running_server


def test_fleetd_bt_pulse_ok(running_server):
    """Health must come from the verifier-started instance token."""
    status, body = http_json("GET", "/health")
    assert status == 200
    assert body.get("instance_id") == running_server["instance"]


def test_fleetd_bt_tuple_semver_gate(tmp_path):
    """Semver floors must accept billing-api 10.0.0 over floor 2.0.0 via live HTTP."""
    assert reference_semver_gte("10.0.0", "2.0.0") is True
    assert reference_semver_gte("1.9.0", "2.0.0") is False
    db_path = tmp_path / "registry.json"
    _build_binary()
    proc, _base, _instance = _start_server(db_path, SECURE_POLICY, manifest_path=HIGH_VERSION_MANIFEST)
    try:
        status, body = http_json("POST", "/v1/build-plan", {})
        assert status == 200
        assert body["modules"] == EXPECTED_ORDER
    finally:
        _stop_server(proc)


def test_fleetd_bt_dag_linearize_default(running_server):
    """Build plan must return stable topological order for the default manifest."""
    status, body = http_json("POST", "/v1/build-plan", {})
    assert status == 200
    assert body["modules"] == EXPECTED_ORDER
    assert body["modules"] == reference_topo_order(
        EXPECTED_ORDER,
        [
            ("auth-core", "billing-api"),
            ("auth-core", "ingest-worker"),
            ("billing-api", "notify-hub"),
            ("ingest-worker", "notify-hub"),
            ("auth-core", "gateway"),
            ("billing-api", "gateway"),
            ("notify-hub", "gateway"),
        ],
    )


def test_fleetd_bt_kahn_tail_unlock(tmp_path):
    """Kahn must append sorted newly-ready modules without re-sorting the whole queue."""
    db_path = tmp_path / "registry.json"
    _build_binary()
    proc, _base, _instance = _start_server(db_path, INSECURE_POLICY, manifest_path=TIEBREAK_MANIFEST)
    try:
        status, body = http_json("POST", "/v1/build-plan", {})
        assert status == 200
        assert body["modules"] == TIEBREAK_ORDER
        assert body["modules"] == reference_topo_order(
            TIEBREAK_ORDER,
            [("a-unit", "b-unit"), ("c-unit", "d-unit")],
        )
        assert body["modules"] != ["a-unit", "b-unit", "c-unit", "d-unit"]
    finally:
        _stop_server(proc)


def test_fleetd_bt_fork_join_dag(tmp_path):
    """Diamond dependency graph must resolve left before right then merge."""
    db_path = tmp_path / "registry.json"
    _build_binary()
    proc, _base, _instance = _start_server(db_path, INSECURE_POLICY, manifest_path=DIAMOND_MANIFEST)
    try:
        status, body = http_json("POST", "/v1/build-plan", {})
        assert status == 200
        assert body["modules"] == DIAMOND_ORDER
    finally:
        _stop_server(proc)


def test_fleetd_bt_cycle_guard(tmp_path):
    """Cyclic manifests must return cycle_detected."""
    db_path = tmp_path / "registry.json"
    _build_binary()
    proc, _base, _instance = _start_server(db_path, INSECURE_POLICY, manifest_path=CYCLE_MANIFEST)
    try:
        status, body = http_json("POST", "/v1/build-plan", {})
        assert status == 400
        assert body["error"] == "cycle_detected"
    finally:
        _stop_server(proc)


def test_fleetd_bt_orphan_dep_guard(tmp_path):
    """Unknown depends_on IDs must return manifest_error, not cycle_detected."""
    db_path = tmp_path / "registry.json"
    _build_binary()
    proc, _base, _instance = _start_server(db_path, INSECURE_POLICY, manifest_path=MISSING_DEP_MANIFEST)
    try:
        status, body = http_json("POST", "/v1/build-plan", {})
        assert status == 400
        assert body["error"] == "manifest_error"
    finally:
        _stop_server(proc)


def test_fleetd_bt_registry_pending_gate(tmp_path):
    """Pending registry modules must be rejected when approval is required."""
    db_path = tmp_path / "registry.json"
    _build_binary()
    proc, _base, _instance = _start_server(db_path, SECURE_POLICY, manifest_path=UNAPPROVED_MANIFEST)
    try:
        status, body = http_json("POST", "/v1/build-plan", {})
        assert status == 403
        assert body["error"] == "module_not_allowed"
    finally:
        _stop_server(proc)


def test_fleetd_bt_min_version_gate(tmp_path):
    """Modules below policy min versions must return version_not_allowed."""
    db_path = tmp_path / "registry.json"
    _build_binary()
    proc, _base, _instance = _start_server(db_path, SECURE_POLICY, manifest_path=LOW_VERSION_MANIFEST)
    try:
        status, body = http_json("POST", "/v1/build-plan", {})
        assert status == 403
        assert body["error"] == "version_not_allowed"
    finally:
        _stop_server(proc)


def test_fleetd_bt_hot_reload_policy(tmp_path):
    """Policy changes on disk must apply on the next request without restart."""
    db_path = tmp_path / "registry.json"
    _build_binary()
    proc, _base, _instance = _start_server(db_path, SECURE_POLICY, manifest_path=LOW_VERSION_MANIFEST)
    try:
        status, _ = http_json("POST", "/v1/build-plan", {})
        assert status == 403
        POLICY_PATH.write_text(
            """require_registry_approval = true
debug_endpoints_enabled = false
min_module_versions = billing-api:1.0.0,ingest-worker:1.0.0
fleet_release_pin = fleet-2025.11.4
"""
        )
        status, body = http_json("POST", "/v1/build-plan", {})
        assert status == 200
        assert body["modules"] == EXPECTED_ORDER
    finally:
        _stop_server(proc)


def test_fleetd_bt_debug_route_404(fleetd_reconciled_server):
    """Debug policy endpoint must return 404 when disabled."""
    status, body = http_json("GET", "/debug/policy")
    assert status == 404
    assert body["error"] == "not_found"


def test_fleetd_bt_openapi_surface(running_server):
    """OpenAPI document must describe /v1/build-plan and /health."""
    status, body = http_json("GET", "/openapi.json")
    assert status == 200
    assert body["openapi"].startswith("3.1")
    assert "post" in body["paths"]["/v1/build-plan"]
    assert "post" in body["paths"]["/v1/build-attest"]
    assert "get" in body["paths"]["/health"]


def test_fleetd_bt_compliance_json_emit(running_server):
    """Build-train emitter must produce schema-valid fleet build compliance JSON."""
    if REPORT_PATH.exists():
        REPORT_PATH.unlink()
    env = os.environ.copy()
    env["REGISTRY_DB_PATH"] = str(running_server["db_path"])
    env["POLICY_PATH"] = str(running_server["policy_path"])
    env["API_BASE"] = str(running_server["base"])
    _fleetd_emit_audit(env)
    raw = REPORT_PATH.read_text().strip()
    report = json.loads(raw)
    assert report["policy_applied"] is True
    assert report["openapi_valid"] is True
    assert report["release_pin_valid"] is True
    assert report["debug_endpoint_blocked"] is True
    assert report["build_plan_valid"] is True
    assert report["build_attest_valid"] is True
    assert report["approved_module_count"] == 5
    assert report["policy_digest"] == policy_digest()
    digest = reference_plan_digest(EXPECTED_ORDER)
    seal = reference_plan_seal(digest, "fleet-2025.11.4", len(EXPECTED_ORDER))
    assert report["plan_digest"] == digest
    assert report["seal_root"] == seal
    assert report["seal_root"] != reference_plan_seal_no_domain(
        digest, "fleet-2025.11.4", len(EXPECTED_ORDER)
    )
    content = POLICY_PATH.read_text()
    assert "require_registry_approval = true" in content
    assert "debug_endpoints_enabled = false" in content


def test_fleetd_bt_policy_harden_emit(running_server):
    """Build-train emitter must rewrite fleet-policy.toml with secure defaults."""
    POLICY_PATH.write_text("require_registry_approval = false\n")
    env = os.environ.copy()
    env["REGISTRY_DB_PATH"] = str(running_server["db_path"])
    env["POLICY_PATH"] = str(POLICY_PATH)
    env["API_BASE"] = str(running_server["base"])
    _fleetd_emit_audit(env)
    content = POLICY_PATH.read_text()
    assert "require_registry_approval = true" in content
    assert "debug_endpoints_enabled = false" in content
    assert "min_module_versions = billing-api:2.0.0,ingest-worker:1.1.0" in content
    assert "fleet_release_pin = fleet-2025.11.4" in content


def test_fleetd_bt_post_emit_probe_lock(fleetd_reconciled_server):
    """After build-train emit, live probes must still block unsafe behavior."""
    assert http_status("GET", "/debug/policy") == 404
    status, body = http_json("POST", "/v1/build-plan", {})
    assert status == 200
    assert body["modules"] == EXPECTED_ORDER


def test_fleetd_bt_unreachable_emit_fail(running_server):
    """Build-train emitter must fail when the API is unreachable."""
    proc = running_server["proc"]
    assert isinstance(proc, subprocess.Popen)
    _stop_server(proc)
    env = os.environ.copy()
    env["REGISTRY_DB_PATH"] = str(running_server["db_path"])
    env["POLICY_PATH"] = str(running_server["policy_path"])
    env["API_BASE"] = str(running_server["base"])
    result = _fleetd_emit_audit(env, expect_ok=False)
    assert result.returncode != 0, result.stderr + result.stdout


def test_fleetd_bt_probe_precedes_report(running_server):
    """Build-train driver must write build-train-probe.json before compliance export."""
    if SNAPSHOT_PATH.exists():
        SNAPSHOT_PATH.unlink()
    if REPORT_PATH.exists():
        REPORT_PATH.unlink()
    env = os.environ.copy()
    env["REGISTRY_DB_PATH"] = str(running_server["db_path"])
    env["POLICY_PATH"] = str(running_server["policy_path"])
    env["API_BASE"] = str(running_server["base"])
    _fleetd_emit_audit(env)
    assert Path(SNAPSHOT_JSON).is_file()
    assert Path(REPORT_JSON).is_file()
    raw = SNAPSHOT_PATH.read_text(encoding="utf-8")
    assert "\n" not in raw
    roundtrip = json.dumps(json.loads(raw), separators=(",", ":"), sort_keys=True)
    assert raw == roundtrip
    snap = json.loads(raw)
    assert snap["version"] == 1
    assert snap["release_pin"] == "fleet-2025.11.4"
    assert snap["probes"]["openapi_valid"] is True
    assert snap["probes"]["debug_endpoint_blocked"] is True
    assert snap["probes"]["build_plan_valid"] is True
    assert snap["probes"]["build_attest_valid"] is True
    digest = reference_plan_digest(EXPECTED_ORDER)
    seal = reference_plan_seal(digest, "fleet-2025.11.4", len(EXPECTED_ORDER))
    assert snap["plan_digest"] == digest
    assert snap["plan_seal"] == seal
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    assert report["build_plan_valid"] == snap["probes"]["build_plan_valid"]
    assert report["seal_root"] == snap["plan_seal"]
    assert report["plan_digest"] == snap["plan_digest"]


def test_fleetd_bt_probe_bytes_stable(running_server):
    """Second successful emit must keep identical probe snapshot bytes."""
    env = os.environ.copy()
    env["REGISTRY_DB_PATH"] = str(running_server["db_path"])
    env["POLICY_PATH"] = str(running_server["policy_path"])
    env["API_BASE"] = str(running_server["base"])
    _fleetd_emit_audit(env)
    first = SNAPSHOT_PATH.read_bytes()
    _fleetd_emit_audit(env)
    second = SNAPSHOT_PATH.read_bytes()
    assert first == second
    assert not first.endswith(b"\n")


def test_fleetd_bt_stage_root_trap(running_server):
    """Hidden trap: FLEET_STAGE_ROOT may redirect staging away from the default /app/var/fleet-stage path."""
    stage_dir = Path("/opt/verifier-fixtures/fleet-stage")
    stage_dir.mkdir(parents=True, exist_ok=True)
    snap = stage_dir / "build-train-probe.json"
    if snap.exists():
        snap.unlink()
    env = os.environ.copy()
    env["REGISTRY_DB_PATH"] = str(running_server["db_path"])
    env["POLICY_PATH"] = str(running_server["policy_path"])
    env["FLEET_STAGE_ROOT"] = str(stage_dir)
    env["API_BASE"] = str(running_server["base"])
    _fleetd_emit_audit(env)
    assert snap.is_file()
    doc = json.loads(snap.read_text(encoding="utf-8"))
    assert doc["probes"]["release_pin_valid"] is True


def test_fleetd_bt_toml_literal_form(running_server):
    """Rewritten policy must use unquoted TOML values matching the schema example."""
    env = os.environ.copy()
    env["REGISTRY_DB_PATH"] = str(running_server["db_path"])
    env["POLICY_PATH"] = str(running_server["policy_path"])
    env["API_BASE"] = str(running_server["base"])
    _fleetd_emit_audit(env)
    content = POLICY_PATH.read_text(encoding="utf-8")
    assert 'require_registry_approval = "true"' not in content
    assert "require_registry_approval = true" in content
    assert 'fleet_release_pin = "fleet-2025.11.4"' not in content
    assert "fleet_release_pin = fleet-2025.11.4" in content


def test_fleetd_bt_lab_decoy_skip(running_server):
    """Decoy lab wrap helpers are not required on the build-train hot path."""
    assert (APP / "lab" / "wrap.go").is_file()
    env = os.environ.copy()
    env["REGISTRY_DB_PATH"] = str(running_server["db_path"])
    env["POLICY_PATH"] = str(running_server["policy_path"])
    env["API_BASE"] = str(running_server["base"])
    _fleetd_emit_audit(env)
    assert Path(REPORT_JSON).is_file()


def test_fleetd_bt_pin_fixture_sync(running_server):
    """Hidden release pin must change plan_seal and compliance seal_root on the live pipeline."""
    hidden = Path("/opt/verifier-fixtures/fixtures/hidden-release.pin")
    assert "/opt/verifier-fixtures" in str(hidden)
    assert hidden.is_file()
    pin = hidden.read_text(encoding="utf-8").strip()
    assert pin == "fleet-2026.03.9"
    assert pin != "fleet-2025.11.4"
    pin_path = APP / "fixtures" / "fleet-release.pin"
    original = pin_path.read_text(encoding="utf-8")
    try:
        pin_path.write_text(pin + "\n", encoding="utf-8")
        if SNAPSHOT_PATH.exists():
            SNAPSHOT_PATH.unlink()
        if REPORT_PATH.exists():
            REPORT_PATH.unlink()
        env = os.environ.copy()
        env["REGISTRY_DB_PATH"] = str(running_server["db_path"])
        env["POLICY_PATH"] = str(running_server["policy_path"])
        env["API_BASE"] = str(running_server["base"])
        _fleetd_emit_audit(env)
        snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        assert snap["release_pin"] == pin
        digest = reference_plan_digest(EXPECTED_ORDER)
        seal = reference_plan_seal(digest, pin, len(EXPECTED_ORDER))
        assert snap["plan_digest"] == digest
        assert snap["plan_seal"] == seal
        assert snap["plan_seal"] != reference_plan_seal(
            digest, "fleet-2025.11.4", len(EXPECTED_ORDER)
        )
        assert report["seal_root"] == seal
        assert report["release_pin_valid"] is True
    finally:
        pin_path.write_text(original, encoding="utf-8")


def test_fleetd_bt_probe_schema_lock(running_server):
    """Probe snapshot contract keys must appear on the live staging bytes."""
    env = os.environ.copy()
    env["REGISTRY_DB_PATH"] = str(running_server["db_path"])
    env["POLICY_PATH"] = str(running_server["policy_path"])
    env["API_BASE"] = str(running_server["base"])
    _fleetd_emit_audit(env)
    raw = SNAPSHOT_PATH.read_text(encoding="utf-8")
    snap = json.loads(raw)
    assert set(snap.keys()) == {
        "api_base",
        "plan_digest",
        "plan_seal",
        "probes",
        "release_pin",
        "version",
    }
    assert set(snap["probes"].keys()) == {
        "build_attest_valid",
        "build_plan_valid",
        "debug_endpoint_blocked",
        "openapi_valid",
        "release_pin_valid",
    }
    contract = (APP / "docs" / "probe-snapshot-contract.md").read_text(encoding="utf-8")
    assert "build-train-probe.json" in contract
    assert "plan_seal" in contract
    assert "run-journal.jsonl" in contract
    catalog = (APP / "docs" / "module-fixture-index.md").read_text(encoding="utf-8")
    assert "tiebreak-manifest.csv" in catalog
    assert (APP / "docs" / "build-train-ops.md").is_file()


def test_fleetd_bt_attest_live_probe(running_server):
    """POST /v1/build-attest must return plan_digest and 0x46 plan_seal for the live order."""
    POLICY_PATH.write_text(SECURE_POLICY)
    status, body = http_json("POST", "/v1/build-attest", {})
    assert status == 200
    assert body["modules"] == EXPECTED_ORDER
    assert body["release_pin"] == "fleet-2025.11.4"
    digest = reference_plan_digest(EXPECTED_ORDER)
    assert body["plan_digest"] == digest
    assert body["plan_seal"] == reference_plan_seal(
        digest, "fleet-2025.11.4", len(EXPECTED_ORDER)
    )


def test_fleetd_bt_journal_increments(running_server):
    """Successful emits must append run-journal.jsonl with stable seal_root."""
    journal = STAGE_ROOT / "run-journal.jsonl"
    if journal.exists():
        journal.unlink()
    env = os.environ.copy()
    env["REGISTRY_DB_PATH"] = str(running_server["db_path"])
    env["POLICY_PATH"] = str(running_server["policy_path"])
    env["API_BASE"] = str(running_server["base"])
    _fleetd_emit_audit(env)
    _fleetd_emit_audit(env)
    lines = [ln for ln in journal.read_text(encoding="utf-8").splitlines() if ln]
    assert len(lines) == 2
    j1 = json.loads(lines[0])
    j2 = json.loads(lines[1])
    assert j1["run_index"] == 1
    assert j2["run_index"] == 2
    assert j1["seal_root"] == j2["seal_root"]
    assert set(j1.keys()) == {"run_index", "seal_root"}
    snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert j1["seal_root"] == snap["plan_seal"]


def test_fleetd_bt_csv_fixture_inventory():
    """Module fixture index entries must exist on disk under /app/data."""
    for path in (
        Path("/app/data/module-manifest.csv"),
        Path("/app/data/cycle-manifest.csv"),
        Path("/app/data/unapproved-manifest.csv"),
        Path("/app/data/low-version-manifest.csv"),
        Path("/app/data/high-version-manifest.csv"),
        Path("/app/data/tiebreak-manifest.csv"),
        Path("/app/data/diamond-manifest.csv"),
        Path("/app/data/missing-dep-manifest.csv"),
    ):
        assert path.is_file(), str(path)
