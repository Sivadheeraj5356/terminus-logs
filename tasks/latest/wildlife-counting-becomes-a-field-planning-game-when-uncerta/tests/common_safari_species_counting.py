"""Runtime, integrity, and case helpers for safari species censuses."""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import os
import secrets
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Iterator

import requests


TEST_DIR = Path(__file__).resolve().parent
TASK_ROOT = next(
    (parent for parent in TEST_DIR.parents if (parent / "environment" / "src" / "server.mjs").exists()),
    TEST_DIR,
)
LOCAL_APP_DIR = TASK_ROOT / "environment"
HARBOR_APP_DIR = Path("/app")
EXPECTED_HASHES = TEST_DIR / "expected_hashes.json"

SCENARIO_SEEDS = {
    "open_savanna": [730101, 730104, 730107, 730109],
    "river_confluence": [730201, 730204, 730207, 730209],
    "thornveld_dusk": [730301, 730304, 730307, 730309],
}
CASE_ROWS = [
    (scenario_id, seed, f"case_{index:02d}")
    for index, (scenario_id, seed) in enumerate(
        (
            (scenario_id, seed)
            for scenario_id, seeds in SCENARIO_SEEDS.items()
            for seed in seeds
        ),
        start=1,
    )
]
REPORT_ROWS: list[dict[str, Any]] = []
_RESULT_KEY: str | None = None
_RESULT_NONCE: str | None = None
_EXPECTED_BINDING: str | None = None


def app_dir() -> Path:
    """Return the packaged application directory or its checkout equivalent."""
    override = os.environ.get("APP_DIR")
    if override:
        candidate = Path(override)
        if (candidate / "src" / "server.mjs").exists() and (candidate / "safari_dispatch.mjs").exists():
            return candidate
    if (HARBOR_APP_DIR / "src" / "server.mjs").exists() and (HARBOR_APP_DIR / "safari_dispatch.mjs").exists():
        return HARBOR_APP_DIR
    return LOCAL_APP_DIR


def dispatcher_path() -> Path:
    """Return the single editable dispatcher path."""
    override = os.environ.get("SOLVER_PATH")
    if override:
        candidate = Path(override)
        return candidate if candidate.is_absolute() else candidate.resolve()
    return app_dir() / "safari_dispatch.mjs"


def stable_payload(value: Any) -> Any:
    """Order one HMAC payload recursively while excluding its proof field."""
    if isinstance(value, list):
        return [stable_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: stable_payload(value[key]) for key in sorted(value) if key != "result_proof"}
    return value


def normalized_sha256(path: Path) -> str:
    """Hash a protected text file with normalized line endings."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256((text.rstrip("\n") + "\n").encode()).hexdigest()


def protected_paths(root: Path) -> list[Path]:
    """List the protected runtime files outside the editable dispatcher."""
    return [root / "package.json", root / "safari_runtime.md", *sorted((root / "src").rglob("*.mjs"))]


def assert_protected_hashes() -> None:
    """Verify the complete protected runtime file set and every expected digest."""
    expected = json.loads(EXPECTED_HASHES.read_text(encoding="utf-8"))
    root = app_dir()
    observed = {
        path.relative_to(root).as_posix(): normalized_sha256(path)
        for path in protected_paths(root)
        if path.exists()
    }
    assert set(observed) == set(expected), "protected runtime file set changed"
    changed = [relative for relative, digest in observed.items() if expected[relative] != digest]
    assert not changed, f"protected runtime files changed: {changed}"


def dispatcher_environment() -> dict[str, str]:
    """Return a solver environment without verifier paths, secrets, or pytest case names."""
    environment = os.environ.copy()
    blocked = {
        "TEST_DIR",
        "TASK_VERIFIER_HMAC_KEY_FILE",
        "TASK_EXPECTED_HASHES_PATH",
        "PYTHONPATH",
        "PYTHONHOME",
    }
    for name in list(environment):
        if name in blocked or name.startswith("PYTEST_") or name.startswith("TASK_"):
            environment.pop(name, None)
    return environment


def run_with_integrity_checks(command: list[str], timeout_sec: int) -> subprocess.CompletedProcess[str]:
    """Run the dispatcher while rechecking protected files at unpredictable intervals."""
    assert_protected_hashes()
    process = subprocess.Popen(
        command,
        cwd=str(app_dir()),
        env=dispatcher_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadlines = sorted({0.25 + secrets.randbelow(500) / 1000, 0.9 + secrets.randbelow(700) / 1000})
    start = time.monotonic()
    checked = 0
    while process.poll() is None:
        elapsed = time.monotonic() - start
        while checked < len(deadlines) and elapsed >= deadlines[checked]:
            assert_protected_hashes()
            checked += 1
        if elapsed > timeout_sec:
            process.kill()
            stdout, stderr = process.communicate()
            raise subprocess.TimeoutExpired(command, timeout_sec, output=stdout, stderr=stderr)
        time.sleep(0.05)
    stdout, stderr = process.communicate()
    assert_protected_hashes()
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def free_port() -> int:
    """Reserve an available loopback TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def setup_headers(payload: dict[str, Any], key: str) -> dict[str, str]:
    """Build one-use verifier headers for census setup."""
    nonce = secrets.token_hex(24)
    envelope = stable_payload({"method": "POST", "path": "/new_game", "nonce": nonce, "payload": payload})
    signature = hmac.new(
        key.encode(), json.dumps(envelope, separators=(",", ":")).encode(), hashlib.sha256
    ).hexdigest()
    return {"X-Setup-Nonce": nonce, "X-Setup-Hmac": signature}


def result_headers() -> dict[str, str]:
    """Create a fresh challenge for the final public state."""
    global _RESULT_NONCE
    _RESULT_NONCE = secrets.token_hex(24)
    return {"X-State-Nonce": _RESULT_NONCE}


def verify_state_proof(payload: dict[str, Any]) -> None:
    """Verify that final state came from the bound verifier-owned census."""
    assert _RESULT_KEY and _RESULT_NONCE and _EXPECTED_BINDING
    proof = payload.get("result_proof")
    assert isinstance(proof, dict), "missing verifier-owned state proof"
    assert proof.get("algorithm") == "hmac-sha256"
    assert proof.get("method") == "GET"
    assert proof.get("path") == "/state"
    assert proof.get("nonce_hash") == hashlib.sha256(_RESULT_NONCE.encode()).hexdigest()
    assert hmac.compare_digest(str(proof.get("run_binding", "")), _EXPECTED_BINDING)
    proof_core = {
        "status": payload.get("status"),
        "end_reason": payload.get("end_reason"),
        "turn": payload.get("turn"),
        "score": payload.get("score"),
        "scenario_id": payload.get("scenario", {}).get("id"),
        "objective_reached": payload.get("summary", {}).get("objective_reached"),
        "completed_turn": payload.get("summary", {}).get("completed_turn"),
        "reports_filed": payload.get("summary", {}).get("reports_filed"),
    }
    envelope = stable_payload(
        {"method": "GET", "path": "/state", "nonce": _RESULT_NONCE, "payload": proof_core}
    )
    expected = hmac.new(
        _RESULT_KEY.encode(), json.dumps(envelope, separators=(",", ":")).encode(), hashlib.sha256
    ).hexdigest()
    assert hmac.compare_digest(str(proof.get("digest", "")), expected)


def wait_for_runtime(base_url: str) -> None:
    """Wait until the secured safari runtime responds."""
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            response = requests.get(f"{base_url}/health", timeout=0.5)
            if response.ok and response.json().get("ok") is True:
                return
        except requests.RequestException:
            pass
        time.sleep(0.1)
    raise RuntimeError("secured safari runtime did not start")


@contextlib.contextmanager
def secured_runtime() -> Iterator[tuple[str, str]]:
    """Start one verifier-owned secured safari runtime."""
    global _RESULT_KEY
    port = free_port()
    setup_key = secrets.token_hex(32)
    key_dir = Path("/dev/shm") if Path("/dev/shm").exists() else Path(tempfile.gettempdir())
    file_descriptor, key_path = tempfile.mkstemp(prefix="safari_census_verifier_key_", dir=str(key_dir))
    with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
        handle.write(setup_key)
    environment = os.environ.copy()
    environment.update(
        {
            "HOST": "127.0.0.1",
            "PORT": str(port),
            "APP_DIR": str(app_dir()),
            "TASK_VERIFIER_HMAC_KEY_FILE": key_path,
            "TASK_EXPECTED_HASHES_PATH": str(EXPECTED_HASHES),
        }
    )
    _RESULT_KEY = setup_key
    process = subprocess.Popen(
        ["node", str(TEST_DIR / "secure_server.mjs")],
        cwd=str(app_dir()),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        wait_for_runtime(base_url)
        yield base_url, setup_key
    finally:
        try:
            os.unlink(key_path)
        except FileNotFoundError:
            pass
        process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)


def play_case(scenario_id: str, seed: int, case_label: str) -> dict[str, Any]:
    """Execute the dispatcher against one verifier-owned hidden census."""
    global _EXPECTED_BINDING
    with secured_runtime() as (base_url, setup_key):
        payload = {"scenario_id": scenario_id, "seed": seed}
        _EXPECTED_BINDING = hmac.new(
            setup_key.encode(),
            json.dumps(stable_payload(payload), separators=(",", ":")).encode(),
            hashlib.sha256,
        ).hexdigest()
        unsigned = requests.post(f"{base_url}/new_game", json=payload, timeout=3)
        assert unsigned.status_code == 403, "unsigned setup request was accepted"
        headers = setup_headers(payload, setup_key)
        created = requests.post(f"{base_url}/new_game", json=payload, headers=headers, timeout=3)
        assert created.ok, created.text
        replay = requests.post(f"{base_url}/new_game", json=payload, headers=headers, timeout=3)
        assert replay.status_code == 403, "replayed setup request was accepted"
        duplicate = requests.post(
            f"{base_url}/new_game", json=payload, headers=setup_headers(payload, setup_key), timeout=3
        )
        assert duplicate.status_code == 409, "duplicate census setup was accepted"
        result = run_with_integrity_checks(["node", str(dispatcher_path()), base_url], timeout_sec=180)
        assert result.returncode == 0, result.stderr[-3000:]
        final_response = requests.get(f"{base_url}/state", headers=result_headers(), timeout=3)
        assert final_response.ok, final_response.text
        state = final_response.json()
        verify_state_proof(state)
        REPORT_ROWS.append(
            {
                "case": case_label,
                "scenario": scenario_id,
                "score": state.get("score"),
                "turn": state.get("turn"),
                "reports": state.get("summary", {}).get("reports_filed"),
                "reliable": state.get("summary", {}).get("reliable_sightings"),
                "risk": state.get("summary", {}).get("unsupported_risk"),
                "commands": state.get("summary", {}).get("commands_submitted"),
            }
        )
        return state


def assert_completion(state: dict[str, Any], minimum_score: int) -> None:
    """Assert genuine census submission and the shared performance threshold."""
    assert state["status"] == "complete"
    assert state["end_reason"] == "census_submitted"
    assert state["summary"]["objective_reached"] is True
    assert state["summary"]["reports_filed"] == state["summary"]["required_reports"]
    assert state["score"] >= minimum_score


def render_report(rows: list[dict[str, Any]]) -> str:
    """Render a seed-safe census summary."""
    lines = ["case scenario score turn reports reliable risk commands"]
    for row in rows:
        lines.append(
            f"{row['case']} {row['scenario']} {row['score']} {row['turn']} "
            f"{row['reports']} {row['reliable']} {row['risk']} {row['commands']}"
        )
    return "\n".join(lines)
