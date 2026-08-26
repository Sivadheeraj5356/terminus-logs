"""Verifier for yourlist_sms_incident_debugger — expectations derived from /app/input."""

import json
import re
from pathlib import Path

INPUT = Path("/app/input")
OUTPUT = Path("/app/output")

TEST_CONFIG_ENV = ["TELNYX_API_KEY", "TELNYX_PHONE_NUMBER"]
MOUNT_PATH = "/api/sms"
SEND_ENDPOINT = f"{MOUNT_PATH}/send"
HTTP_LINE = re.compile(
    r"^(?P<timestamp>\S+)\s+(?P<method>GET|POST|PUT|PATCH|DELETE)\s+(?P<path>\S+)\s+(?P<status>\d{3})$"
)
RESPONSE_LINE = re.compile(r"^(?P<timestamp>\S+)\s+response=(?P<payload>.+)$")
SEND_BODY_FIELDS = re.compile(r"const\s*\{\s*([^}]+)\s*\}\s*=\s*req\.body")
FROM_VAR_LINE = re.compile(r"process\.env\.(TELNYX_\w+)")


def _load_env_snapshot() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (INPUT / "env_snapshot.txt").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def _load_body_keys(filename: str) -> list[str]:
    data = json.loads((INPUT / filename).read_text())
    return sorted(data["body"].keys())


def _parse_body_destructuring(raw: str) -> tuple[list[str], list[str]]:
    required: list[str] = []
    optional: list[str] = []
    for part in raw.split(","):
        part = part.strip()
        if "=" in part:
            optional.append(part.split("=")[0].strip())
        else:
            required.append(part)
    return required, optional


def _load_body_fields() -> tuple[list[str], list[str]]:
    sms = (INPUT / "sms.js").read_text()
    match = SEND_BODY_FIELDS.search(sms)
    assert match, "sms.js send handler body fields must be parseable"
    return _parse_body_destructuring(match.group(1))


def _referenced_telnyx_vars() -> list[str]:
    seen: list[str] = []
    for filename in ("sms.js", "smsService.js"):
        for match in FROM_VAR_LINE.finditer((INPUT / filename).read_text()):
            name = match.group(1)
            if name not in seen:
                seen.append(name)
    return seen


def _parse_pm2_events() -> list[dict]:
    events: list[dict] = []
    for line in (INPUT / "pm2_sms.log").read_text().splitlines():
        match = HTTP_LINE.match(line.strip())
        if not match:
            continue
        events.append(
            {
                "timestamp": match.group("timestamp"),
                "method": match.group("method"),
                "path": match.group("path"),
                "status": int(match.group("status")),
            }
        )
    return events


def _extract_function_body(text: str, function_name: str) -> str:
    pattern = re.compile(
        rf"function\s+{re.escape(function_name)}\s*\([^)]*\)\s*\{{",
        re.DOTALL,
    )
    match = pattern.search(text)
    assert match, f"{function_name} must be defined in smsService.js"
    start = match.end() - 1
    depth = 0
    for idx in range(start, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : idx]
    raise AssertionError(f"Unbalanced braces in {function_name}")


def _from_var_precedence() -> list[str]:
    text = (INPUT / "smsService.js").read_text()
    body = _extract_function_body(text, "resolveFromNumber")
    seen: list[str] = []
    for match in FROM_VAR_LINE.finditer(body):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def _webhook_error_codes() -> list[str]:
    codes: list[str] = []
    for line in (INPUT / "pm2_sms.log").read_text().splitlines():
        if "Message failed" not in line:
            continue
        for match in re.finditer(r'"code"\s*:\s*"(\d+)"', line):
            codes.append(match.group(1))
    return codes


def _spam_filter_line_count() -> int:
    return sum(
        1
        for line in (INPUT / "pm2_sms_error.log").read_text().splitlines()
        if "40002" in line
    )


def _normalizer_wired_in_server() -> bool:
    server = (INPUT / "server.js").read_text()
    return "sms_body_normalizer" in server or "normalizeSmsBody" in server


def _exact_send_events(events: list[dict]) -> list[dict]:
    return [
        event
        for event in events
        if event["method"] == "POST" and event["path"] == SEND_ENDPOINT
    ]


def _query_send_events(events: list[dict]) -> list[dict]:
    return [
        event
        for event in events
        if event["method"] == "POST" and event["path"].startswith(f"{SEND_ENDPOINT}?")
    ]


def _expected_response_audit(events: list[dict]) -> dict:
    entries: list[dict] = []
    last_http: dict | None = None
    event_idx = 0
    for line in (INPUT / "pm2_sms.log").read_text().splitlines():
        http_match = HTTP_LINE.match(line.strip())
        if http_match:
            while event_idx < len(events) and events[event_idx]["timestamp"] != http_match.group(
                "timestamp"
            ):
                event_idx += 1
            if event_idx < len(events):
                last_http = events[event_idx]
                event_idx += 1
            continue
        response_match = RESPONSE_LINE.match(line.strip())
        if not response_match or last_http is None:
            continue
        payload = json.loads(response_match.group("payload"))
        raw_success = payload.get("success")
        entries.append(
            {
                "response_timestamp": response_match.group("timestamp"),
                "request_timestamp": last_http["timestamp"],
                "method": last_http["method"],
                "path": last_http["path"],
                "http_status": last_http["status"],
                "success": False if raw_success is None else bool(raw_success),
                "error": str(payload.get("error", "") or ""),
            }
        )
    return {"entries": entries}


def _expected_route_contract(events: list[dict]) -> dict:
    required, optional = _load_body_fields()
    initial = _load_body_keys("frontend_request.json")
    retry = _load_body_keys("frontend_retry.json")
    final = _load_body_keys("frontend_final.json")
    exact_sends = _exact_send_events(events)
    query_sends = _query_send_events(events)
    assert len(exact_sends) == 3, "PM2 log must contain three exact-path POST /api/sms/send lines"
    assert len(query_sends) == 1, "PM2 log must contain one POST /api/sms/send?... line"
    return {
        "send_endpoint": SEND_ENDPOINT,
        "mounted_base_path": MOUNT_PATH,
        "required_body_fields": required,
        "optional_body_fields": optional,
        "initial_frontend_fields": initial,
        "retry_frontend_fields": retry,
        "final_frontend_fields": final,
        "initial_contract_mismatch": set(required) != set(initial),
        "retry_has_required_user": "user" in retry,
        "final_includes_country_code": "countryCode" in final,
        "normalizer_wired_in_server": _normalizer_wired_in_server(),
        "first_send_status": exact_sends[0]["status"],
        "retry_send_status": exact_sends[1]["status"],
        "third_send_status": exact_sends[2]["status"],
        "query_send_status": query_sends[0]["status"],
    }


def _expected_env_audit(env: dict[str, str]) -> dict:
    present = sorted(key for key in env if key.startswith("TELNYX_"))
    missing = sorted(name for name in TEST_CONFIG_ENV if name not in env)
    referenced = set(_referenced_telnyx_vars())
    unused = sorted(key for key in present if key not in referenced)
    return {
        "required_env_vars": sorted(TEST_CONFIG_ENV),
        "present_env_vars": present,
        "missing_env_vars": missing,
        "unused_telnyx_vars": unused,
        "provider_ready": len(missing) == 0,
        "test_config_ready": "TELNYX_PHONE_NUMBER" in env,
    }


def _expected_sms_service_audit(env: dict[str, str]) -> dict:
    precedence = _from_var_precedence()
    effective = ""
    for name in precedence:
        if env.get(name):
            effective = env[name]
            break
    return {
        "from_var_precedence": precedence,
        "test_config_vars": sorted(TEST_CONFIG_ENV),
        "snapshot_effective_from": effective,
        "test_config_reports_missing_from": "TELNYX_PHONE_NUMBER" not in env,
    }


def _expected_decoy_log_audit() -> dict:
    return {
        "error_log_file": "pm2_sms_error.log",
        "spam_filter_code": "40002",
        "spam_filter_line_count": _spam_filter_line_count(),
        "is_root_cause_for_send_failures": False,
    }


def _expected_incident_summary(events: list[dict]) -> dict:
    exact_sends = _exact_send_events(events)
    query_sends = _query_send_events(events)
    spam_count = _spam_filter_line_count()
    return {
        "http_event_count": len(events),
        "sms_send_attempts": len(exact_sends),
        "sms_send_with_query_attempts": len(query_sends),
        "sms_send_statuses": [event["status"] for event in exact_sends],
        "test_config_calls": sum(
            1
            for event in events
            if event["method"] == "GET" and event["path"] == f"{MOUNT_PATH}/test-config"
        ),
        "webhook_post_count": sum(
            1 for event in events if event["method"] == "POST" and event["path"] == f"{MOUNT_PATH}/webhook"
        ),
        "webhook_error_codes": _webhook_error_codes(),
        "error_log_spam_blocks": spam_count,
    }


def _nginx_v2_404_count() -> int:
    return sum(
        1
        for line in (INPUT / "nginx_access.log").read_text().splitlines()
        if "POST /api/v2/sms/send" in line and " 404 " in line
    )


def _expected_red_herring_audit() -> dict:
    spam_count = _spam_filter_line_count()
    ops = (INPUT / "ops_note.txt").read_text().lower()
    return {
        "ops_note_file": "ops_note.txt",
        "ops_note_recommends_v2_rollback": "/api/v2/sms/send" in ops,
        "ops_note_blames_spam_filter": "spam" in ops or "40002" in ops,
        "ops_note_is_primary_root_cause": False,
        "nginx_log_file": "nginx_access.log",
        "nginx_v2_sms_404_count": _nginx_v2_404_count(),
        "v2_route_is_root_cause": False,
        "stderr_spam_filter_code": "40002",
        "stderr_spam_filter_line_count": spam_count,
        "stderr_spam_is_root_cause": False,
    }


def _failed_gate_for_send(http_status: int, response_error: str) -> str:
    err = str(response_error or "").lower()
    if http_status == 500:
        return "provider_send"
    if http_status == 400 and "user" in err:
        return "user"
    if http_status == 400 and "message" in err:
        return "message"
    return "provider_send"


def _expected_send_validation_audit(events: list[dict], response_entries: list[dict]) -> dict:
    exact_sends = _exact_send_events(events)
    send_failures: list[dict] = []
    for idx, send in enumerate(exact_sends):
        entry = next(
            (row for row in response_entries if row["request_timestamp"] == send["timestamp"]),
            {},
        )
        err = str(entry.get("error", "") or "")
        send_failures.append(
            {
                "attempt_index": idx + 1,
                "failed_gate": _failed_gate_for_send(send["status"], err),
                "http_status": send["status"],
                "response_error": err,
            }
        )
    return {
        "validation_gates": [
            {"order": 1, "gate": "user", "failure_http_status": 400},
            {"order": 2, "gate": "message", "failure_http_status": 400},
            {"order": 3, "gate": "provider_send", "failure_http_status": 500},
        ],
        "send_failures": send_failures,
    }


def _failure_category(http_status: int, attempt_index: int) -> str:
    if attempt_index == 1 and http_status == 400:
        return "contract_mismatch"
    return "provider_from_number"


def _expected_failure_chain(events: list[dict], response_entries: list[dict]) -> dict:
    exact_sends = _exact_send_events(events)
    sources = ["frontend_request.json", "frontend_retry.json", "frontend_final.json"]
    send_attempts: list[dict] = []
    for idx, send in enumerate(exact_sends):
        entry = next(
            (row for row in response_entries if row["request_timestamp"] == send["timestamp"]),
            {},
        )
        err = str(entry.get("error", "") or "")
        send_attempts.append(
            {
                "attempt_index": idx + 1,
                "frontend_source": sources[idx],
                "http_status": send["status"],
                "response_error": err,
                "failure_category": _failure_category(send["status"], idx + 1),
            }
        )
    query = _query_send_events(events)[0]
    query_entry = next(
        (row for row in response_entries if row["request_timestamp"] == query["timestamp"]),
        {},
    )
    query_err = str(query_entry.get("error", "") or "")
    return {
        "send_attempts": send_attempts,
        "query_send": {
            "http_status": query["status"],
            "response_error": query_err,
            "failure_category": "provider_from_number",
        },
    }


def test_required_files_exist():
    """Verify all thirteen required output files exist."""
    required = [
        "root_cause_report.md",
        "fix_plan.md",
        "route_contract.json",
        "env_audit.json",
        "sms_service_audit.json",
        "response_audit.json",
        "decoy_log_audit.json",
        "red_herring_audit.json",
        "send_validation_audit.json",
        "failure_chain.json",
        "incident_timeline.json",
        "incident_summary.json",
        "verification_checklist.md",
    ]

    for name in required:
        assert (OUTPUT / name).exists(), f"Missing {name}"


def test_root_cause_contains_findings():
    """Verify root cause mentions contract, env split, failures, red herrings, and nginx v2 decoy."""
    text = (OUTPUT / "root_cause_report.md").read_text().lower()

    for token in (
        "to",
        "user",
        "countrycode",
        "sms_body_normalizer",
        "telnyx_phone_number",
        "telnyx_from_number",
        "smsservice",
        "resolvefromnumber",
        "400",
        "500",
        "40304",
        "40002",
        "unrelated",
        "v2",
        "nginx",
        "ops",
    ):
        assert token in text, f"root_cause_report.md must mention {token}"


def test_json_files_parse():
    """Verify JSON outputs are valid."""
    for name in (
        "route_contract.json",
        "env_audit.json",
        "sms_service_audit.json",
        "response_audit.json",
        "decoy_log_audit.json",
        "red_herring_audit.json",
        "send_validation_audit.json",
        "failure_chain.json",
        "incident_timeline.json",
        "incident_summary.json",
    ):
        json.loads((OUTPUT / name).read_text())


def _fix_plan_recommends_normalizer_wiring(text: str) -> bool:
    """True only when fix_plan positively recommends wiring the unused middleware."""
    for line in text.splitlines():
        lower = line.lower()
        if "sms_body_normalizer" not in lower and "normalize sms body" not in lower:
            continue
        if re.search(r"\b(do not|don't|not recommend|avoid|skip|never|no need|unnecessary)\b", lower):
            continue
        if re.search(r"\b(wire|enable|mount|activate|add)\b", lower):
            return True
    return False


def test_fix_plan_contains_actions():
    """Verify fix plan includes PM2 restart and test-config; no wiring normalizer or v2 rollback."""
    text = (OUTPUT / "fix_plan.md").read_text().lower()

    assert "pm2 restart all --update-env" in text
    assert "/api/sms/test-config" in text
    assert "telnyx_from_number" in text or "telnyx_phone_number" in text
    assert "rollback" not in text or "/api/v2" not in text
    assert not _fix_plan_recommends_normalizer_wiring(text)


def test_route_contract():
    """Verify route contract JSON matches values derived from inputs."""
    events = _parse_pm2_events()
    expected = _expected_route_contract(events)
    actual = json.loads((OUTPUT / "route_contract.json").read_text())
    assert actual == expected


def test_env_audit():
    """Verify env audit JSON matches Telnyx vars derived from env snapshot."""
    env = _load_env_snapshot()
    expected = _expected_env_audit(env)
    actual = json.loads((OUTPUT / "env_audit.json").read_text())
    assert actual == expected


def test_sms_service_audit():
    """Verify sms_service_audit.json matches smsService.js precedence and env snapshot."""
    env = _load_env_snapshot()
    expected = _expected_sms_service_audit(env)
    actual = json.loads((OUTPUT / "sms_service_audit.json").read_text())
    assert actual == expected


def test_response_audit():
    """Verify response_audit.json pairs response= lines with preceding HTTP events."""
    events = _parse_pm2_events()
    expected = _expected_response_audit(events)
    actual = json.loads((OUTPUT / "response_audit.json").read_text())
    assert actual == expected


def test_decoy_log_audit():
    """Verify decoy_log_audit.json counts stderr spam blocks separately from root cause."""
    expected = _expected_decoy_log_audit()
    actual = json.loads((OUTPUT / "decoy_log_audit.json").read_text())
    assert actual == expected


def test_red_herring_audit():
    """Verify red_herring_audit.json rejects ops note and nginx v2 path as root cause."""
    expected = _expected_red_herring_audit()
    actual = json.loads((OUTPUT / "red_herring_audit.json").read_text())
    assert actual == expected


def test_send_validation_audit():
    """Verify send_validation_audit.json maps each failed send to a validation gate in sms.js."""
    events = _parse_pm2_events()
    response = _expected_response_audit(events)
    expected = _expected_send_validation_audit(events, response["entries"])
    actual = json.loads((OUTPUT / "send_validation_audit.json").read_text())
    assert actual == expected


def test_failure_chain():
    """Verify failure_chain.json links frontend snapshots to PM2 send outcomes."""
    events = _parse_pm2_events()
    response = _expected_response_audit(events)
    expected = _expected_failure_chain(events, response["entries"])
    actual = json.loads((OUTPUT / "failure_chain.json").read_text())
    assert actual == expected


def test_incident_timeline_from_pm2():
    """Verify PM2 HTTP request lines were parsed into incident_timeline.json."""
    expected_events = _parse_pm2_events()
    data = json.loads((OUTPUT / "incident_timeline.json").read_text())
    assert data["events"] == expected_events

    exact_sends = [event for event in data["events"] if event["path"] == SEND_ENDPOINT]
    assert [event["status"] for event in exact_sends] == [400, 500, 500]


def test_incident_summary():
    """Verify incident_summary.json rollups match PM2 HTTP and webhook narrative."""
    events = _parse_pm2_events()
    expected = _expected_incident_summary(events)
    actual = json.loads((OUTPUT / "incident_summary.json").read_text())
    assert actual == expected


def test_checklist():
    """Verify checklist mentions route, PM2, webhooks, and config test."""
    text = (OUTPUT / "verification_checklist.md").read_text().lower()

    assert "pm2" in text
    assert "webhook" in text
    assert "route" in text
    assert "test-config" in text or "test_config" in text
