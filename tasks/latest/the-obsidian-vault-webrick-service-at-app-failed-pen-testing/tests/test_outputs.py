"""Hardened verifier for the flat ruby-webrick-escape-room-hardening task."""
import hashlib
import hmac
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid

import yaml

from webrick_fixture import (
    SETTINGS_PATH,
    find_free_port,
    get_admin_secret,
    get_moderator_key,
    http_get,
    http_post,
    new_session,
    signed_admin_headers,
    start_server,
    stop_server,
)

PROP_TEST = "/app/prop_test"
HARNESS = f"{PROP_TEST}/server_harness.go"
TESTS_GO = f"{PROP_TEST}/prop_test.go"
SERVER_RB = "/app/server.rb"
VERIFIER_DIR = os.environ.get("TEST_DIR", os.path.dirname(os.path.abspath(__file__)))
INJECTOR_RB = os.path.join(VERIFIER_DIR, "prop_test_fault_injector.rb")

REQUIRED_TESTS = [
    "TestDebugEndpointsReturn403UnderDefaultConfig",
    "TestGameEndpointAcceptsValidCommand",
    "TestPuzzleAttemptIsThreadSafe",
    "TestModeratorEndpointsRequireHMAC",
    "TestAdminEndpointRejectsReplay",
]


def _rubyopt_with_injector() -> str:
    """Merge -rbundler/setup and verifier -r injector into RUBYOPT without wiping parent flags."""
    parts = os.environ.get("RUBYOPT", "").split()
    if "-rbundler/setup" not in parts:
        parts.append("-rbundler/setup")
    flag = f"-r{INJECTOR_RB}"
    if flag not in parts:
        parts.append(flag)
    return " ".join(parts)


def _run_go_test_with_fault(fault_name: str) -> subprocess.CompletedProcess:
    """Run go test with PROP_TEST_FAULT and RUBYOPT -r injector (private verifier tree)."""
    env = {
        **os.environ,
        "CGO_ENABLED": "0",
        "PROP_TEST_FAULT": fault_name,
        "RUBYOPT": _rubyopt_with_injector(),
    }
    return subprocess.run(
        ["go", "test", "-v", "-count=1", "-timeout", "120s", "./..."],
        cwd=PROP_TEST,
        capture_output=True,
        text=True,
        timeout=150,
        env=env,
    )


def _go_test_failed(output: str, test_name: str) -> bool:
    """True if go -v output shows an explicit FAIL for the named test."""
    return f"--- FAIL: {test_name}" in output


def _wait_for_rate_limit_bucket_headroom(needed_seconds: int = 15):
    """Sleep until the current 60s rate-limit bucket has enough time left for a burst."""
    remaining = 60 - (int(time.time()) % 60)
    if remaining < needed_seconds:
        time.sleep(remaining + 0.05)


class TestAdminAuth:
    """Admin endpoints gated behind HMAC-SHA256, timestamp window, and nonce replay prevention."""

    def test_admin_secret_exists_in_settings_yaml(self):
        """settings.yaml must have a non-empty admin_secret."""
        secret = get_admin_secret()
        assert secret and str(secret).strip(), (
            "admin_secret in settings.yaml is missing or empty. Add it."
        )

    def test_debug_dump_returns_403_without_any_headers(self):
        """POST /admin/debug-dump must return 403 when no auth headers are provided."""
        port = find_free_port()
        proc, base = start_server(port)
        try:
            status, _ = http_post(f"{base}/admin/debug-dump")
            assert status == 403, f"expected 403, got {status}"
        finally:
            stop_server(proc)

    def test_force_unlock_returns_403_without_any_headers(self):
        """POST /admin/force-unlock must return 403 when no auth headers are provided."""
        port = find_free_port()
        proc, base = start_server(port)
        try:
            status, _ = http_post(f"{base}/admin/force-unlock")
            assert status == 403, f"expected 403, got {status}"
        finally:
            stop_server(proc)

    def test_debug_dump_returns_200_with_valid_sha256_signature(self):
        """POST /admin/debug-dump must return 200 when SHA-256 HMAC headers are correct."""
        port = find_free_port()
        proc, base = start_server(port)
        try:
            secret = get_admin_secret()
            headers = signed_admin_headers("/admin/debug-dump", secret)
            status, _ = http_post(f"{base}/admin/debug-dump", headers=headers)
            assert status == 200, f"expected 200 with valid SHA-256 signature, got {status}"
        finally:
            stop_server(proc)

    def test_sha1_signature_is_rejected(self):
        """A SHA-1 HMAC (wrong algorithm) must return 403 even with correct timestamp and nonce."""
        port = find_free_port()
        proc, base = start_server(port)
        try:
            secret = get_admin_secret()
            ts = int(time.time())
            n = str(uuid.uuid4())
            msg = f"/admin/debug-dump:{ts}:{n}".encode("utf-8")
            bad_sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha1).hexdigest()
            headers = {"X-Timestamp": str(ts), "X-Nonce": n, "X-Admin-Signature": bad_sig}
            status, _ = http_post(f"{base}/admin/debug-dump", headers=headers)
            assert status == 403, (
                f"SHA-1 signature was accepted (got {status}); only SHA-256 must be accepted."
            )
        finally:
            stop_server(proc)

    def test_timestamp_near_window_boundary_is_accepted(self):
        """A timestamp near the 90-second boundary (-88s) must be accepted."""
        port = find_free_port()
        proc, base = start_server(port)
        try:
            secret = get_admin_secret()
            headers = signed_admin_headers("/admin/debug-dump", secret, ts_offset=-88)
            status, _ = http_post(f"{base}/admin/debug-dump", headers=headers)
            assert status == 200, (
                f"Timestamp at -88s was rejected (got {status}); "
                "the window check should accept timestamps within 90 seconds."
            )
        finally:
            stop_server(proc)

    def test_timestamp_beyond_window_is_rejected(self):
        """A timestamp 91 seconds old must return 403."""
        port = find_free_port()
        proc, base = start_server(port)
        try:
            secret = get_admin_secret()
            headers = signed_admin_headers("/admin/debug-dump", secret, ts_offset=-91)
            status, _ = http_post(f"{base}/admin/debug-dump", headers=headers)
            assert status == 403, f"expected 403 for timestamp at -91s, got {status}"
        finally:
            stop_server(proc)

    def test_replay_attack_returns_403(self):
        """Sending the same nonce a second time must return 403 (replay prevention)."""
        port = find_free_port()
        proc, base = start_server(port)
        try:
            secret = get_admin_secret()
            fixed_nonce = str(uuid.uuid4())
            headers = signed_admin_headers("/admin/debug-dump", secret, nonce=fixed_nonce)
            status1, _ = http_post(f"{base}/admin/debug-dump", headers=headers)
            assert status1 == 200, f"first request with valid nonce expected 200, got {status1}"
            headers2 = signed_admin_headers("/admin/debug-dump", secret, nonce=fixed_nonce)
            status2, _ = http_post(f"{base}/admin/debug-dump", headers=headers2)
            assert status2 == 403, (
                f"Replay with same nonce returned {status2}; expected 403. "
                "Ensure NonceStore rejects already-used nonces."
            )
        finally:
            stop_server(proc)

    def test_hint_endpoint_unaffected(self):
        """GET /hint must return 200 — unaffected by admin hardening."""
        port = find_free_port()
        proc, base = start_server(port)
        try:
            status, _ = http_get(f"{base}/hint?puzzle_id=cipher_alpha")
            assert status == 200, f"GET /hint returned {status}"
        finally:
            stop_server(proc)

    def test_state_endpoint_unaffected(self):
        """GET /state must return 200 with a 'puzzles' key — unaffected by admin hardening."""
        port = find_free_port()
        proc, base = start_server(port)
        try:
            status, body = http_get(f"{base}/state")
            assert status == 200, f"GET /state returned {status}"
            data = json.loads(body)
            assert "puzzles" in data, "GET /state response missing 'puzzles' key"
        finally:
            stop_server(proc)

    def test_command_endpoint_unaffected(self):
        """POST /command with a game verb must still return 200 — unaffected by admin hardening."""
        port = find_free_port()
        proc, base = start_server(port)
        try:
            data = json.dumps({"verb": "examine", "payload": {"target": "room", "data": None}}).encode()
            req = urllib.request.Request(
                f"{base}/command",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    status = r.status
            except urllib.error.HTTPError as e:
                status = e.code
            assert status == 200, f"POST /command (examine) returned {status}; must stay reachable."
        finally:
            stop_server(proc)


class TestPuzzleConcurrency:
    """PuzzleEngine race conditions fixed; SHA-256 hashing in use."""

    def test_concurrent_attempts_are_serialized(self):
        """Concurrent attempts must strictly respect attempts_remaining (3 for cipher_alpha)."""
        port = find_free_port()
        proc, base = start_server(port, rate_limit_rpm=10000)
        try:
            session_id = new_session(base)
            url = f"{base}/command"
            body = {"verb": "attempt", "payload": {"target": "cipher_alpha", "data": "wrong"}}
            headers = {"X-Session-Token": session_id}

            results = []

            def make_req():
                _, resp = http_post(url, body, headers)
                results.append(resp)

            threads = [threading.Thread(target=make_req) for _ in range(100)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            evaluated = sum(
                1 for r in results
                if r.get("reason") == "wrong_answer" or r.get("ok") is True
            )
            no_attempts = sum(1 for r in results if r.get("reason") == "no_attempts")

            assert evaluated == 3, (
                f"Expected exactly 3 evaluated attempts (cipher_alpha has 3 limit). "
                f"Got {evaluated} evaluations and {no_attempts} 'no_attempts'."
            )
            assert no_attempts >= 95, (
                f"Expected at least 95 'no_attempts' rejections, got {no_attempts}."
            )
            assert evaluated + no_attempts <= 100, (
                f"Expected evaluated + no_attempts <= 100, got {evaluated + no_attempts} "
                f"({evaluated} evaluated, {no_attempts} 'no_attempts')."
            )
        finally:
            stop_server(proc)

    def test_prereq_race_is_fixed(self):
        """Concurrent attempts to cipher_beta (with cipher_alpha unsolved) must all return prereq_unmet."""
        port = find_free_port()
        proc, base = start_server(port, rate_limit_rpm=10000)
        try:
            session_id = new_session(base)
            url = f"{base}/command"
            body = {"verb": "attempt", "payload": {"target": "cipher_beta", "data": "anything"}}
            headers = {"X-Session-Token": session_id}

            results = []

            def make_req():
                _, resp = http_post(url, body, headers)
                results.append(resp)

            threads = [threading.Thread(target=make_req) for _ in range(50)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            bypassed = [
                r for r in results
                if r.get("reason") not in ("prereq_unmet", "no_attempts")
                and r.get("status") != 429
            ]
            assert not bypassed, (
                f"{len(bypassed)} request(s) bypassed the prerequisite check: {bypassed[:3]}. "
                "prereq_met? must be inside the synchronize block."
            )
        finally:
            stop_server(proc)

    def test_sha256_answer_hashing(self):
        """The correct answer for cipher_alpha ('delta') must be accepted — confirms SHA-256 is in use."""
        port = find_free_port()
        proc, base = start_server(port, rate_limit_rpm=10000)
        try:
            session_id = new_session(base)
            url = f"{base}/command"
            body = {"verb": "attempt", "payload": {"target": "cipher_alpha", "data": "delta"}}
            headers = {"X-Session-Token": session_id}
            _, resp = http_post(url, body, headers)
            assert resp.get("ok") is True, (
                f"Expected ok=true for answer 'delta' (SHA-256 hash), got: {resp}. "
                "Ensure puzzle_engine uses SHA-256 not MD5."
            )
        finally:
            stop_server(proc)

    def test_game_command_still_works(self):
        """POST /command with examine verb must still function for regular game flow."""
        port = find_free_port()
        proc, base = start_server(port, rate_limit_rpm=10000)
        try:
            data = json.dumps({"verb": "examine", "payload": {"target": "room", "data": None}}).encode()
            req = urllib.request.Request(
                f"{base}/command",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    status = r.status
            except urllib.error.HTTPError as e:
                status = e.code
            assert status == 200, f"POST /command (examine) returned {status}"
        finally:
            stop_server(proc)

    def test_game_command_attempt_still_works(self):
        """POST /command with attempt verb must still function for regular game flow."""
        port = find_free_port()
        proc, base = start_server(port, rate_limit_rpm=10000)
        try:
            session_id = new_session(base)
            data = json.dumps({"verb": "attempt", "payload": {"target": "cipher_alpha", "data": "wrong"}}).encode()
            req = urllib.request.Request(
                f"{base}/command",
                data=data,
                headers={"Content-Type": "application/json", "X-Session-Token": session_id},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    status = r.status
            except urllib.error.HTTPError as e:
                status = e.code
            assert status == 200, f"POST /command (attempt) returned {status}"
        finally:
            stop_server(proc)

    def test_game_command_unlock_still_works(self):
        """POST /command with unlock verb must still function for regular game flow."""
        port = find_free_port()
        proc, base = start_server(port, rate_limit_rpm=10000)
        try:
            session_id = new_session(base)
            data = json.dumps({"verb": "unlock", "payload": {"target": "vault_door", "data": "21"}}).encode()
            req = urllib.request.Request(
                f"{base}/command",
                data=data,
                headers={"Content-Type": "application/json", "X-Session-Token": session_id},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    status = r.status
            except urllib.error.HTTPError as e:
                status = e.code
            assert status == 422, f"POST /command (unlock) expected 422 for incomplete puzzles, returned {status}"
        finally:
            stop_server(proc)


class TestModeratorAndRateLimit:
    """Moderator HMAC and rate limiter correctness."""

    def test_moderator_key_is_non_empty_in_settings(self):
        """settings.yaml must have a non-empty moderator_key."""
        key = get_moderator_key()
        assert key and str(key).strip(), (
            f"moderator_key in settings.yaml is {key!r}; it must be a non-empty string."
        )

    def test_moderator_verb_without_signature_returns_403(self):
        """POST /command with a moderator verb and no signature must return 403."""
        port = find_free_port()
        proc, base = start_server(port, rate_limit_rpm=30)
        try:
            status, _ = http_post(
                f"{base}/command",
                {"verb": "reset_puzzle", "payload": {"puzzle_id": "cipher_alpha"}},
            )
            assert status == 403, f"Expected 403 for moderator verb without signature, got {status}."
        finally:
            stop_server(proc)

    def test_moderator_verb_with_wrong_signature_returns_403(self):
        """POST /command with a moderator verb and incorrect signature must return 403."""
        port = find_free_port()
        proc, base = start_server(port, rate_limit_rpm=30)
        try:
            status, _ = http_post(
                f"{base}/command",
                {"verb": "set_attempts", "payload": {"puzzle_id": "cipher_alpha", "attempts": 10}},
                headers={"X-Moderator-Signature": "deadbeef"},
            )
            assert status == 403, f"Expected 403 for wrong moderator signature, got {status}."
        finally:
            stop_server(proc)

    def test_moderator_verb_with_correct_signature_is_accepted(self):
        """POST /command with correct X-Moderator-Signature must not return 403."""
        port = find_free_port()
        proc, base = start_server(port, rate_limit_rpm=30)
        key = get_moderator_key()
        try:
            payload = {"verb": "reset_puzzle", "payload": {"puzzle_id": "cipher_alpha"}}
            raw_body = json.dumps(payload).encode()
            sig = hmac.new(key.encode(), raw_body, hashlib.sha256).hexdigest()
            status, _ = http_post(
                f"{base}/command",
                raw_data=raw_body,
                headers={"X-Moderator-Signature": sig},
            )
            assert status != 403, "Correct moderator signature was rejected with 403."
        finally:
            stop_server(proc)

    def test_empty_configured_key_denies_access(self):
        """If moderator_key is empty or absent in settings, all moderator access must be denied (403)."""
        with open(SETTINGS_PATH, "r") as f:
            orig_cfg = yaml.safe_load(f)

        cfg = orig_cfg.copy()
        cfg["moderator_key"] = ""
        with open(SETTINGS_PATH, "w") as f:
            yaml.safe_dump(cfg, f)

        port = find_free_port()
        proc, base = start_server(port, rate_limit_rpm=30)
        try:
            payload = {"verb": "reset_puzzle", "payload": {"puzzle_id": "cipher_alpha"}}
            raw_body = json.dumps(payload).encode()
            sig = hmac.new(b"", raw_body, hashlib.sha256).hexdigest()
            status, _ = http_post(
                f"{base}/command",
                raw_data=raw_body,
                headers={"X-Moderator-Signature": sig},
            )
            assert status == 403, f"Expected 403 when configured key is empty, got {status}."
        finally:
            stop_server(proc)
            with open(SETTINGS_PATH, "w") as f:
                yaml.safe_dump(orig_cfg, f)

    def test_game_verb_works_without_signature(self):
        """POST /command with a game verb must succeed without a moderator signature."""
        port = find_free_port()
        proc, base = start_server(port, rate_limit_rpm=30)
        try:
            status, _ = http_post(
                f"{base}/command",
                {"verb": "examine", "payload": {"target": "room", "data": None}},
            )
            assert status == 200, f"Game verb without signature returned {status}."
        finally:
            stop_server(proc)

    def test_rate_limit_is_enforced(self):
        """After rate_limit_rpm requests from one IP, subsequent requests must return 429."""
        port = find_free_port()
        proc, base = start_server(port, rate_limit_rpm=30)
        try:
            with open(SETTINGS_PATH) as f:
                cfg = yaml.safe_load(f)
            rpm = cfg.get("rate_limit_rpm", 30)

            _wait_for_rate_limit_bucket_headroom(needed_seconds=rpm + 15)

            statuses = []
            for _ in range(rpm + 10):
                status, _ = http_post(
                    f"{base}/command",
                    {"verb": "examine", "payload": {"target": "room", "data": None}},
                )
                statuses.append(status)

            rate_limited = statuses.count(429)
            assert rate_limited >= 1, (
                f"After {rpm + 10} rapid requests (limit={rpm}), expected at least 1 x 429. "
                f"Got: {dict((s, statuses.count(s)) for s in set(statuses))}. "
                "Ensure RateLimiter.allow? is wired into the dispatcher."
            )
        finally:
            stop_server(proc)

    def test_rate_limiter_is_thread_safe(self):
        """Concurrent requests must not bypass the rate limit due to a race condition."""
        port = find_free_port()
        proc, base = start_server(port, rate_limit_rpm=30)
        try:
            with open(SETTINGS_PATH) as f:
                cfg = yaml.safe_load(f)
            rpm = cfg.get("rate_limit_rpm", 30)

            _wait_for_rate_limit_bucket_headroom(needed_seconds=15)

            statuses = []
            lock = threading.Lock()

            def fire():
                status, _ = http_post(
                    f"{base}/command",
                    {"verb": "examine", "payload": {"target": "room", "data": None}},
                )
                with lock:
                    statuses.append(status)

            threads = [threading.Thread(target=fire) for _ in range(rpm * 2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            accepted = statuses.count(200)
            rate_limited = statuses.count(429)
            assert accepted <= rpm + 2, (
                f"Rate limiter allowed {accepted} requests under concurrent load "
                f"(limit={rpm}). Mutex missing in RateLimiter?"
            )
            assert rate_limited >= rpm - 2, (
                f"Expected at least {rpm - 2} rate-limited responses, got {rate_limited}."
            )
        finally:
            stop_server(proc)


class TestGoPropertySuite:
    """Go property-based tests compile and pass against the hardened service."""

    def test_go_module_compiles(self):
        """The prop_test Go module must compile without errors."""
        result = subprocess.run(
            ["go", "build", "./..."],
            cwd=PROP_TEST,
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "CGO_ENABLED": "0"},
        )
        assert result.returncode == 0, (
            f"go build failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

    def test_start_server_implemented(self):
        """StartServer must be implemented (not the stub); StopServer must exist."""
        with open(HARNESS, "r") as f:
            src = f.read()
        assert "StartServer not implemented" not in src, (
            "StartServer is still the stub that returns an error."
        )
        assert "func StopServer(" in src, "StopServer must be defined in server_harness.go."

    def test_all_five_test_functions_present(self):
        """prop_test.go must define all five required test functions."""
        with open(TESTS_GO, "r") as f:
            src = f.read()
        for name in REQUIRED_TESTS:
            assert f"func {name}(" in src, f"Missing test function {name} in prop_test.go"

    def test_property_tests_pass(self):
        """go test ./prop_test/... must exit 0 with all tests green — no skipped tests."""
        result = subprocess.run(
            ["go", "test", "-v", "-count=1", "-timeout", "120s", "./..."],
            cwd=PROP_TEST,
            capture_output=True,
            text=True,
            timeout=150,
            env={**os.environ, "CGO_ENABLED": "0"},
        )
        assert result.returncode == 0, (
            f"go test failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}\n"
            "Implement StartServer/StopServer and all five test bodies."
        )
        assert "--- SKIP" not in result.stdout, (
            "Some tests were skipped (t.Skip still present). Replace all stubs with real tests.\n"
            f"Output:\n{result.stdout}"
        )

    def test_go_sources_do_not_read_tests_dir(self):
        """Go harness/suite must not reference /tests (verifier tree is not for the service)."""
        for path in (HARNESS, TESTS_GO):
            with open(path, "r") as f:
                src = f.read()
            assert "/tests" not in src, (
                f"{path} references /tests; the Go harness must not read verifier files."
            )

    def test_server_has_no_fault_injector_scaffolding(self):
        """Fault injection belongs on the verifier side — not in the agent-visible app tree."""
        assert not os.path.exists("/app/lib/prop_test_fault_injector.rb"), (
            "/app/lib/prop_test_fault_injector.rb must not ship in the app tree."
        )
        with open(SERVER_RB, "r") as f:
            src = f.read()
        assert "prop_test_fault_injector" not in src, (
            "server.rb must not require a verifier fault injector."
        )
        assert "PropTestFaultInjector" not in src, (
            "server.rb must not call PropTestFaultInjector."
        )

    def test_property_tests_catch_unsigned_admin_access(self):
        """If admin signature checks are disabled, the fuzz test must fail."""
        result = _run_go_test_with_fault("unsigned_admin")
        out = result.stdout + "\n" + result.stderr
        assert result.returncode != 0, (
            "go test PASSED even when admin signature checks were disabled! "
            "TestDebugEndpointsReturn403UnderDefaultConfig must reject unsigned requests."
        )
        assert _go_test_failed(out, "TestDebugEndpointsReturn403UnderDefaultConfig"), (
            "Expected --- FAIL: TestDebugEndpointsReturn403UnderDefaultConfig when "
            "unsigned_admin fault is active. Output:\n" + out
        )

    def test_property_tests_fail_when_iterations_too_low(self):
        """If a debug endpoint becomes vulnerable after 10 requests, 50+ iterations should catch it."""
        result = _run_go_test_with_fault("intermittent_admin_leak")
        out = result.stdout + "\n" + result.stderr
        assert result.returncode != 0, (
            "go test PASSED even though the debug endpoint became vulnerable on the 11th request! "
            "The test suite is not performing 50+ random iterations."
        )
        assert _go_test_failed(out, "TestDebugEndpointsReturn403UnderDefaultConfig"), (
            "Expected --- FAIL: TestDebugEndpointsReturn403UnderDefaultConfig when "
            "intermittent_admin_leak is active (low iteration counts must not satisfy this). "
            "Output:\n" + out
        )

    def test_property_tests_fail_when_game_endpoint_broken(self):
        """If the game endpoint returns a 500 status code, the test suite must fail."""
        result = _run_go_test_with_fault("broken_command")
        out = result.stdout + "\n" + result.stderr
        assert result.returncode != 0, (
            "go test PASSED even when POST /command always returns 500! "
            "The test suite is missing actual HTTP validation."
        )
        assert _go_test_failed(out, "TestGameEndpointAcceptsValidCommand"), (
            "Expected --- FAIL: TestGameEndpointAcceptsValidCommand when broken_command "
            "fault is active. Output:\n" + out
        )

    def test_property_tests_fail_when_attempts_not_serialized(self):
        """If attempt budgets are ignored, TestPuzzleAttemptIsThreadSafe must fail."""
        result = _run_go_test_with_fault("broken_attempts")
        out = result.stdout + "\n" + result.stderr
        assert result.returncode != 0, (
            "go test PASSED even when attempt evaluation ignores attempts_remaining! "
            "TestPuzzleAttemptIsThreadSafe must assert the concurrency invariant over live HTTP."
        )
        assert _go_test_failed(out, "TestPuzzleAttemptIsThreadSafe"), (
            "Expected --- FAIL: TestPuzzleAttemptIsThreadSafe when broken_attempts "
            "fault is active. Output:\n" + out
        )

    def test_property_tests_fail_when_moderator_hmac_open(self):
        """If moderator verbs skip HMAC checks, TestModeratorEndpointsRequireHMAC must fail."""
        result = _run_go_test_with_fault("open_moderator")
        out = result.stdout + "\n" + result.stderr
        assert result.returncode != 0, (
            "go test PASSED even when moderator verbs accept unsigned/forged requests! "
            "TestModeratorEndpointsRequireHMAC must exercise live HMAC rejection."
        )
        assert _go_test_failed(out, "TestModeratorEndpointsRequireHMAC"), (
            "Expected --- FAIL: TestModeratorEndpointsRequireHMAC when open_moderator "
            "fault is active. Output:\n" + out
        )

    def test_property_tests_fail_when_admin_replay_accepted(self):
        """If admin nonce replay is accepted, TestAdminEndpointRejectsReplay must fail."""
        result = _run_go_test_with_fault("accept_replay")
        out = result.stdout + "\n" + result.stderr
        assert result.returncode != 0, (
            "go test PASSED even when admin nonce replay was accepted! "
            "TestAdminEndpointRejectsReplay must exercise live replay rejection."
        )
        assert _go_test_failed(out, "TestAdminEndpointRejectsReplay"), (
            "Expected --- FAIL: TestAdminEndpointRejectsReplay when accept_replay "
            "fault is active. Output:\n" + out
        )
