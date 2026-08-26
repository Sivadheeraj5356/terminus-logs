#!/usr/bin/env bash
set -euo pipefail

python3 <<'PY'
import json
import re
from pathlib import Path

INPUT = Path("/app/input")
OUTPUT = Path("/app/output")
OUTPUT.mkdir(parents=True, exist_ok=True)

TEST_CONFIG_ENV = ["TELNYX_API_KEY", "TELNYX_PHONE_NUMBER"]
MOUNT_PATH = "/api/sms"
SEND_ENDPOINT = f"{MOUNT_PATH}/send"
HTTP_LINE = re.compile(
    r"^(?P<timestamp>\S+)\s+(?P<method>GET|POST|PUT|PATCH|DELETE)\s+(?P<path>\S+)\s+(?P<status>\d{3})$"
)
RESPONSE_LINE = re.compile(r"^(?P<timestamp>\S+)\s+response=(?P<payload>.+)$")
SEND_BODY_FIELDS = re.compile(r"const\s*\{\s*([^}]+)\s*\}\s*=\s*req\.body")
FROM_VAR_LINE = re.compile(r"process\.env\.(TELNYX_\w+)")


def load_env_snapshot() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (INPUT / "env_snapshot.txt").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def load_body_keys(filename: str) -> list[str]:
    data = json.loads((INPUT / filename).read_text())
    return sorted(data["body"].keys())


def parse_body_destructuring(raw: str) -> tuple[list[str], list[str]]:
    required: list[str] = []
    optional: list[str] = []
    for part in raw.split(","):
        part = part.strip()
        if "=" in part:
            optional.append(part.split("=")[0].strip())
        else:
            required.append(part)
    return required, optional


def load_body_fields() -> tuple[list[str], list[str]]:
    sms = (INPUT / "sms.js").read_text()
    match = SEND_BODY_FIELDS.search(sms)
    if not match:
        raise RuntimeError("Could not parse send handler body fields from sms.js")
    return parse_body_destructuring(match.group(1))


def referenced_telnyx_vars() -> list[str]:
    seen: list[str] = []
    for filename in ("sms.js", "smsService.js"):
        for match in FROM_VAR_LINE.finditer((INPUT / filename).read_text()):
            name = match.group(1)
            if name not in seen:
                seen.append(name)
    return seen


def parse_pm2_events() -> list[dict]:
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


def extract_function_body(text: str, function_name: str) -> str:
    pattern = re.compile(
        rf"function\s+{re.escape(function_name)}\s*\([^)]*\)\s*\{{",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        raise RuntimeError(f"{function_name} not found in smsService.js")
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
    raise RuntimeError(f"Unbalanced braces in {function_name}")


def from_var_precedence() -> list[str]:
    text = (INPUT / "smsService.js").read_text()
    body = extract_function_body(text, "resolveFromNumber")
    seen: list[str] = []
    for match in FROM_VAR_LINE.finditer(body):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def webhook_error_codes() -> list[str]:
    codes: list[str] = []
    for line in (INPUT / "pm2_sms.log").read_text().splitlines():
        if "Message failed" not in line:
            continue
        for match in re.finditer(r'"code"\s*:\s*"(\d+)"', line):
            codes.append(match.group(1))
    return codes


def spam_filter_line_count() -> int:
    return sum(
        1
        for line in (INPUT / "pm2_sms_error.log").read_text().splitlines()
        if "40002" in line
    )


def normalizer_wired_in_server() -> bool:
    server = (INPUT / "server.js").read_text()
    return "sms_body_normalizer" in server or "normalizeSmsBody" in server


def exact_send_events(events: list[dict]) -> list[dict]:
    return [
        event
        for event in events
        if event["method"] == "POST" and event["path"] == SEND_ENDPOINT
    ]


def query_send_events(events: list[dict]) -> list[dict]:
    return [
        event
        for event in events
        if event["method"] == "POST" and event["path"].startswith(f"{SEND_ENDPOINT}?")
    ]


def build_response_audit(events: list[dict]) -> dict:
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
        entries.append(
            {
                "response_timestamp": response_match.group("timestamp"),
                "request_timestamp": last_http["timestamp"],
                "method": last_http["method"],
                "path": last_http["path"],
                "http_status": last_http["status"],
        "success": False if payload.get("success") is None else bool(payload.get("success")),
        "error": str(payload.get("error", "") or ""),
            }
        )
    return {"entries": entries}


env = load_env_snapshot()
required_fields, optional_fields = load_body_fields()
initial_fields = load_body_keys("frontend_request.json")
retry_fields = load_body_keys("frontend_retry.json")
final_fields = load_body_keys("frontend_final.json")
events = parse_pm2_events()
exact_sends = exact_send_events(events)
query_sends = query_send_events(events)
precedence = from_var_precedence()
effective_from = next((env[name] for name in precedence if env.get(name)), "")
spam_count = spam_filter_line_count()
referenced = set(referenced_telnyx_vars())
present_env = sorted(key for key in env if key.startswith("TELNYX_"))
missing_env = sorted(name for name in TEST_CONFIG_ENV if name not in env)
unused_env = sorted(key for key in present_env if key not in referenced)

route_contract = {
    "send_endpoint": SEND_ENDPOINT,
    "mounted_base_path": MOUNT_PATH,
    "required_body_fields": required_fields,
    "optional_body_fields": optional_fields,
    "initial_frontend_fields": initial_fields,
    "retry_frontend_fields": retry_fields,
    "final_frontend_fields": final_fields,
    "initial_contract_mismatch": set(required_fields) != set(initial_fields),
    "retry_has_required_user": "user" in retry_fields,
    "final_includes_country_code": "countryCode" in final_fields,
    "normalizer_wired_in_server": normalizer_wired_in_server(),
    "first_send_status": exact_sends[0]["status"],
    "retry_send_status": exact_sends[1]["status"],
    "third_send_status": exact_sends[2]["status"],
    "query_send_status": query_sends[0]["status"],
}

env_audit = {
    "required_env_vars": sorted(TEST_CONFIG_ENV),
    "present_env_vars": present_env,
    "missing_env_vars": missing_env,
    "unused_telnyx_vars": unused_env,
    "provider_ready": len(missing_env) == 0,
    "test_config_ready": "TELNYX_PHONE_NUMBER" in env,
}

sms_service_audit = {
    "from_var_precedence": precedence,
    "test_config_vars": sorted(TEST_CONFIG_ENV),
    "snapshot_effective_from": effective_from,
    "test_config_reports_missing_from": "TELNYX_PHONE_NUMBER" not in env,
}

response_audit = build_response_audit(events)

decoy_log_audit = {
    "error_log_file": "pm2_sms_error.log",
    "spam_filter_code": "40002",
    "spam_filter_line_count": spam_count,
    "is_root_cause_for_send_failures": False,
}

ops_text = (INPUT / "ops_note.txt").read_text().lower()
nginx_v2_404 = sum(
    1
    for line in (INPUT / "nginx_access.log").read_text().splitlines()
    if "POST /api/v2/sms/send" in line and " 404 " in line
)

red_herring_audit = {
    "ops_note_file": "ops_note.txt",
    "ops_note_recommends_v2_rollback": "/api/v2/sms/send" in ops_text,
    "ops_note_blames_spam_filter": "spam" in ops_text or "40002" in ops_text,
    "ops_note_is_primary_root_cause": False,
    "nginx_log_file": "nginx_access.log",
    "nginx_v2_sms_404_count": nginx_v2_404,
    "v2_route_is_root_cause": False,
    "stderr_spam_filter_code": "40002",
    "stderr_spam_filter_line_count": spam_count,
    "stderr_spam_is_root_cause": False,
}

response_entries = response_audit["entries"]
exact_send_list = exact_send_events(events)
send_failures = []
for idx, send in enumerate(exact_send_list):
    entry = next(
        (row for row in response_entries if row["request_timestamp"] == send["timestamp"]),
        {},
    )
    err = str(entry.get("error", "") or "")
    failed_gate = "provider_send"
    if send["status"] == 400 and "user" in err.lower():
        failed_gate = "user"
    elif send["status"] == 400 and "message" in err.lower():
        failed_gate = "message"
    send_failures.append(
        {
            "attempt_index": idx + 1,
            "failed_gate": failed_gate,
            "http_status": send["status"],
            "response_error": err,
        }
    )

send_validation_audit = {
    "validation_gates": [
        {"order": 1, "gate": "user", "failure_http_status": 400},
        {"order": 2, "gate": "message", "failure_http_status": 400},
        {"order": 3, "gate": "provider_send", "failure_http_status": 500},
    ],
    "send_failures": send_failures,
}

sources = ["frontend_request.json", "frontend_retry.json", "frontend_final.json"]
chain_attempts = []
for idx, send in enumerate(exact_send_list):
    entry = next(
        (row for row in response_entries if row["request_timestamp"] == send["timestamp"]),
        {},
    )
    err = str(entry.get("error", "") or "")
    category = "contract_mismatch" if idx == 0 and send["status"] == 400 else "provider_from_number"
    chain_attempts.append(
        {
            "attempt_index": idx + 1,
            "frontend_source": sources[idx],
            "http_status": send["status"],
            "response_error": err,
            "failure_category": category,
        }
    )

query_send = query_sends[0]
query_entry = next(
    (row for row in response_entries if row["request_timestamp"] == query_send["timestamp"]),
    {},
)
failure_chain = {
    "send_attempts": chain_attempts,
    "query_send": {
        "http_status": query_send["status"],
        "response_error": str(query_entry.get("error", "") or ""),
        "failure_category": "provider_from_number",
    },
}

incident_summary = {
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
    "webhook_error_codes": webhook_error_codes(),
    "error_log_spam_blocks": spam_count,
}

root_cause = f"""# Root Cause Report

The SMS routes mount at `{MOUNT_PATH}`; the send endpoint is `{SEND_ENDPOINT}`.

**Request contract (attempt 1):** `frontend_request.json` sends `to` and `message`, but `sms.js` destructures `user` and `message` (with optional `countryCode`). The missing `user` field produces HTTP {exact_sends[0]["status"]}.

**Request contract (attempt 2):** `frontend_retry.json` sends `user`, fixing the field name, but still fails with HTTP {exact_sends[1]["status"]} because provider validation rejects the from number.

**Request contract (attempt 3):** `frontend_final.json` includes `countryCode`, yet the third exact-path send still returns HTTP {exact_sends[2]["status"]} for the same provider issue.

**Unused middleware:** `sms_body_normalizer.js` would map `to` → `user`, but it is **not** wired in `server.js`, so the first attempt still fails.

**Env / readiness split:** `/api/sms/test-config` only treats `TELNYX_PHONE_NUMBER` as the from-number env var. The snapshot defines `TELNYX_FROM_NUMBER` instead, so test-config reports `fromNumber` as Missing and `ready` false even though `smsService.resolveFromNumber()` can read `TELNYX_FROM_NUMBER` as a fallback. Decoy vars `TELNYX_SMS_FROM` and `TELNYX_MESSAGING_PROFILE_ID` are present but unused by routes/service.

**smsService.js:** `resolveFromNumber()` prefers `TELNYX_PHONE_NUMBER`, then `TELNYX_FROM_NUMBER`. With only `TELNYX_FROM_NUMBER` set, sends use `{effective_from}`, but readiness checks still fail.

**Provider evidence:** PM2 webhook narrative reports Telnyx error code 40304 (`Invalid from number`) on both webhook failures.

**Stderr red herring:** `pm2_sms_error.log` shows spam filter code 40002, which is **unrelated** to the `/send` contract and env failures investigated here.

**Ops / nginx red herrings:** `ops_note.txt` suggests rolling back `/api/v2/sms/send` and blames spam filter 40002 — both are **unrelated**. `nginx_access.log` shows a 404 on `/api/v2/sms/send`, but the real Express app serves `/api/sms/send` and PM2 timeline matches nginx statuses for that path.
"""

fix_plan = """# Fix Plan

1. Update the frontend to send `user` (not `to`) when calling `/api/sms/send`.
2. Align env naming: set `TELNYX_PHONE_NUMBER` to the approved Telnyx from number (or teach `/test-config` to accept `TELNYX_FROM_NUMBER`).
3. Restart the backend with updated environment variables using `pm2 restart all --update-env`.
4. Verify configuration readiness by calling `/api/sms/test-config` and confirming `ready` is true.
5. Retry `/api/sms/send` and confirm HTTP 200 with queued status instead of 400/500.
6. Monitor `/api/sms/webhook` for `message.failed` events and provider error codes such as 40304.
"""

checklist = """# Verification Checklist

- Confirm `server.js` mounts SMS routes at `/api/sms`.
- Confirm the frontend sends `user` and `message` to `/api/sms/send`.
- Confirm `/api/sms/test-config` returns both Telnyx API key and from number as set.
- Confirm `smsService.resolveFromNumber()` and `/test-config` agree on the from-number env var.
- Confirm the production environment contains `TELNYX_PHONE_NUMBER` (or aligned alias).
- Restart PM2 using `pm2 restart all --update-env`.
- Send a test SMS and confirm the response is successful or queued.
- Monitor webhook logs for `message.failed`, `Invalid from number`, and delivery events.
- Ignore stderr spam filter 40002 lines when triaging `/send` HTTP failures.
"""

(OUTPUT / "route_contract.json").write_text(json.dumps(route_contract, indent=2) + "\n")
(OUTPUT / "env_audit.json").write_text(json.dumps(env_audit, indent=2) + "\n")
(OUTPUT / "sms_service_audit.json").write_text(json.dumps(sms_service_audit, indent=2) + "\n")
(OUTPUT / "response_audit.json").write_text(json.dumps(response_audit, indent=2) + "\n")
(OUTPUT / "decoy_log_audit.json").write_text(json.dumps(decoy_log_audit, indent=2) + "\n")
(OUTPUT / "red_herring_audit.json").write_text(json.dumps(red_herring_audit, indent=2) + "\n")
(OUTPUT / "send_validation_audit.json").write_text(json.dumps(send_validation_audit, indent=2) + "\n")
(OUTPUT / "failure_chain.json").write_text(json.dumps(failure_chain, indent=2) + "\n")
(OUTPUT / "incident_timeline.json").write_text(json.dumps({"events": events}, indent=2) + "\n")
(OUTPUT / "incident_summary.json").write_text(json.dumps(incident_summary, indent=2) + "\n")
(OUTPUT / "root_cause_report.md").write_text(root_cause)
(OUTPUT / "fix_plan.md").write_text(fix_plan)
(OUTPUT / "verification_checklist.md").write_text(checklist)
PY
