import http.client
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

BASE_HOST = "127.0.0.1"
BASE_PORT = 8080
VALID_TOKEN = "tok_admin_123"
STATE_DIR = Path(tempfile.mkdtemp(prefix="tb3-auth-state-"))
PROC = None

PROTECTED_VARIANTS = [
    "/v1/admin/profile",
    "/V1//AdMiN/%70rofile",
    "/v1/public/../admin/profile",
    "/v1/%61dmin/profile",
    "//v1//admin///profile",
]


def call(path: str, method: str = "GET", token: str | None = None):
    conn = http.client.HTTPConnection(BASE_HOST, BASE_PORT, timeout=2)
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    conn.request(method, path, headers=headers)
    resp = conn.getresponse()
    status = resp.status
    body = json.loads(resp.read().decode("utf-8"))
    conn.close()
    return status, body


def assert_unauth_schema(body):
    assert body == {
        "error": {
            "code": "unauthorized",
            "message": "missing or invalid bearer token",
        }
    }


def start_api():
    global PROC
    env = os.environ.copy()
    env["TOKEN_FILE"] = "/app/fixtures/tokens.json"
    env["STATE_DIR"] = str(STATE_DIR)
    PROC = subprocess.Popen(
        ["/usr/local/go/bin/go", "run", "."],
        cwd="/app/runtime",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid,
    )
    for _ in range(250):
        try:
            status, _ = call("/v1/public/ping")
            if status == 200:
                return
        except Exception:
            pass
        time.sleep(0.05)
    raise RuntimeError("api did not become ready")


def stop_api():
    global PROC
    if PROC is None:
        return
    if PROC.poll() is None:
        os.killpg(os.getpgid(PROC.pid), 15)
        try:
            PROC.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(PROC.pid), 9)
            PROC.wait(timeout=2)
    PROC = None


def restart_api():
    stop_api()
    start_api()


def read_state():
    status, body = call("/v1/public/state")
    assert status == 200
    return body["state"]


def assert_state_shape(state):
    assert isinstance(state["seq"], int)
    assert isinstance(state["grant_routes"], int)
    assert isinstance(state["aliases"], int)
    assert isinstance(state["corruptions"], int)
    assert isinstance(state["route_seq"], dict)
    for route, seq in state["route_seq"].items():
        assert route in {"/v1/admin/profile", "/v1/admin/audit"}
        assert isinstance(seq, int)


def must_auth(path: str):
    status, body = call(path, token=VALID_TOKEN)
    assert status == 200, (path, status, body)


def must_deny(path: str):
    status, body = call(path)
    assert status == 401, (path, status, body)
    assert_unauth_schema(body)


def setup_module(_module):
    start_api()


def teardown_module(_module):
    stop_api()
    shutil.rmtree(STATE_DIR, ignore_errors=True)


def test_01_public_contract_stable():
    """Verifier scenario: test_01_public_contract_stable."""
    status, body = call("/v1/public/ping")
    assert status == 200 and body["status"] == "ok"
    status, body = call("/v1/public/docs")
    assert status == 200 and "/v1/admin/profile" in body["docs"]
    assert_state_shape(read_state())


def test_02_protected_routes_require_auth_cold_start():
    """Verifier scenario: test_02_protected_routes_require_auth_cold_start."""
    for p in PROTECTED_VARIANTS:
        must_deny(p)


def test_03_authenticated_access_increments_state_seq():
    """Verifier scenario: test_03_authenticated_access_increments_state_seq."""
    before = read_state()
    must_auth("/v1/admin/profile")
    after = read_state()
    assert after["seq"] == before["seq"] + 1
    assert after["route_seq"].get("/v1/admin/profile", 0) >= before["route_seq"].get("/v1/admin/profile", 0) + 1


def test_04_variant_after_authenticated_warmup_still_denied():
    """Verifier scenario: test_04_variant_after_authenticated_warmup_still_denied."""
    must_auth("/v1/admin/profile")
    mid = read_state()["seq"]
    must_deny("/V1//AdMiN/%70rofile")
    assert read_state()["seq"] == mid


def test_05_double_encoded_variant_after_warmup_denied():
    """Verifier scenario: test_05_double_encoded_variant_after_warmup_denied."""
    must_auth("/v1/admin/profile")
    before = read_state()["seq"]
    must_deny("/v1/%2561dmin/profile")
    assert read_state()["seq"] == before


def test_06_ordering_public_then_protected_variant_never_inherits_auth():
    """Verifier scenario: test_06_ordering_public_then_protected_variant_never_inherits_auth."""
    for _ in range(4):
        status, _ = call("/v1/public/ping")
        assert status == 200
    must_auth("/v1/admin/profile")
    seq = read_state()["seq"]
    must_deny("/v1/public/../admin/profile")
    assert read_state()["seq"] == seq


def test_07_restart_preserves_seq_not_transient_auth():
    """Verifier scenario: test_07_restart_preserves_seq_not_transient_auth."""
    pre = read_state()
    must_auth("/v1/admin/profile")
    restart_api()
    post = read_state()
    assert post["seq"] >= pre["seq"] + 1
    assert post["route_seq"].get("/v1/admin/profile", 0) >= pre["route_seq"].get("/v1/admin/profile", 0)
    for p in PROTECTED_VARIANTS:
        must_deny(p)


def test_08_alternating_routes_never_create_replay_auth_channel():
    """Verifier scenario: test_08_alternating_routes_never_create_replay_auth_channel."""
    s0 = read_state()
    for i in range(6):
        must_auth("/v1/admin/audit" if i % 2 == 0 else "/v1/admin/profile")
        status, _ = call("/v1/public/state")
        assert status == 200
    s1 = read_state()
    assert s1["seq"] >= s0["seq"] + 6
    must_deny("//v1//admin///audit")


def test_09_invalid_token_always_rejected_even_after_valid_sequence():
    """Verifier scenario: test_09_invalid_token_always_rejected_even_after_valid_sequence."""
    must_auth("/v1/admin/profile")
    before = read_state()["seq"]
    for p in ["/v1/admin/profile", "/V1//AdMiN/%70rofile", "/v1/public/../admin/audit"]:
        status, body = call(p, token="invalid-token")
        assert status == 401
        assert_unauth_schema(body)
    assert read_state()["seq"] == before


def test_10_journal_corruption_does_not_open_protected_routes():
    """Verifier scenario: test_10_journal_corruption_does_not_open_protected_routes."""
    journal = STATE_DIR / "auth_journal.log"
    with journal.open("a", encoding="utf-8") as f:
        f.write("{bad-json}\n")
        f.write("not-even-json\n")
    restart_api()
    state = read_state()
    assert state["corruptions"] >= 1
    must_deny("/v1/%61dmin/profile")


def test_11_snapshot_corruption_recovery_keeps_runtime_and_auth_safe():
    """Verifier scenario: test_11_snapshot_corruption_recovery_keeps_runtime_and_auth_safe."""
    prev = read_state()["corruptions"]
    (STATE_DIR / "auth_snapshot.json").write_text("{", encoding="utf-8")
    restart_api()
    status, body = call("/v1/public/ping")
    assert status == 200 and body["status"] == "ok"
    assert read_state()["corruptions"] >= prev + 1
    must_deny("/v1/admin/profile")


def test_12_cross_route_warmups_do_not_bleed_authorization():
    """Verifier scenario: test_12_cross_route_warmups_do_not_bleed_authorization."""
    must_auth("/v1/admin/profile")
    must_auth("/v1/admin/audit")
    state = read_state()
    assert state["route_seq"].get("/v1/admin/profile", 0) >= 1
    assert state["route_seq"].get("/v1/admin/audit", 0) >= 1
    must_deny("/V1//AdMiN/%61udit")
    must_deny("/v1/public/../admin/profile")


def test_13_long_workflow_semantic_correctness_over_time():
    """Verifier scenario: test_13_long_workflow_semantic_correctness_over_time."""
    seq0 = read_state()["seq"]
    for i in range(16):
        must_auth("/v1/admin/profile" if i % 3 else "/v1/admin/audit")
        if i % 4 == 0:
            restart_api()
        if i % 5 == 0:
            must_deny("/v1/public/../admin/audit")
    seq1 = read_state()["seq"]
    assert seq1 >= seq0 + 16


def test_14_method_and_not_found_contracts_stable():
    """Verifier scenario: test_14_method_and_not_found_contracts_stable."""
    status, body = call("/v1/public/state", method="POST")
    assert status == 405 and body["error"]["code"] == "method_not_allowed"
    status, body = call("/v1/missing")
    assert status == 404 and body["error"]["code"] == "not_found"


def test_15_restart_chain_state_monotonic_and_protected_safe():
    """Verifier scenario: test_15_restart_chain_state_monotonic_and_protected_safe."""
    s0 = read_state()["seq"]
    for _ in range(3):
        must_auth("/v1/admin/profile")
        restart_api()
    s1 = read_state()["seq"]
    assert s1 >= s0 + 3
    must_deny("/V1//AdMiN///profile")


def test_16_alias_index_growth_never_implies_authorization():
    """Verifier scenario: test_16_alias_index_growth_never_implies_authorization."""
    before = read_state()["aliases"]
    for p in ["/v1/admin/profile", "/V1//AdMiN/%70rofile", "/v1/public/../admin/profile"]:
        must_auth(p)
    after = read_state()["aliases"]
    assert after >= before + 2
    must_deny("/v1/%61dmin/profile")


def test_17_partial_journal_tail_damage_then_restart_stays_safe():
    """Verifier scenario: test_17_partial_journal_tail_damage_then_restart_stays_safe."""
    journal = STATE_DIR / "auth_journal.log"
    if journal.exists():
        b = journal.read_bytes()
        if len(b) > 96:
            journal.write_bytes(b[:-31])
    restart_api()
    must_deny("/v1/admin/audit")
    state = read_state()
    assert_state_shape(state)


def test_18_repeated_variant_probe_cannot_trigger_delayed_bypass():
    """Verifier scenario: test_18_repeated_variant_probe_cannot_trigger_delayed_bypass."""
    must_auth("/v1/admin/profile")
    baseline = read_state()["seq"]
    for _ in range(20):
        must_deny("/V1//AdMiN/%70rofile")
        status, _ = call("/v1/public/ping")
        assert status == 200
    assert read_state()["seq"] == baseline


def test_19_restart_then_variant_with_invalid_token_is_rejected():
    """Verifier scenario: test_19_restart_then_variant_with_invalid_token_is_rejected."""
    must_auth("/v1/admin/profile")
    seq = read_state()["seq"]
    restart_api()
    status, body = call("/V1//AdMiN/%70rofile", token="bad")
    assert status == 401
    assert_unauth_schema(body)
    assert read_state()["seq"] == seq


def test_20_public_routes_never_require_auth_under_stress():
    """Verifier scenario: test_20_public_routes_never_require_auth_under_stress."""
    for _ in range(12):
        status, body = call("/v1/public/state")
        assert status == 200
        assert_state_shape(body["state"])
