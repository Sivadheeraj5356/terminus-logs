# YourList SMS Service Operations Runbook

Build an **offline system-administration runbook package** for the YourList SMS microservice. Inputs are frozen production snapshots under `/app/input/` (PM2 process logs, nginx edge access log, environment file, Express mount sources, and sample request bodies). Write all artifacts under `/app/output/`. Do not modify the host, call Telnyx, or send SMS.

Treat this as **configuration and log inventory work**: inventory env keys, document route mounts, parse process-manager HTTP lines, and emit the ops markdown/JSON pack the on-call runbook expects. Values must come from the inputs (exact JSON equality is checked).

**Noise sources:** `ops_note.txt` and `nginx_access.log` can be misleading. PM2 stderr and some stdout lines are unrelated login/items traffic — exclude them from SMS send accounting where the rules below say so.

## Inputs (`/app/input/`)

| File | Role |
|------|------|
| `sms.js` | Express SMS router (`/send`, `/test-config`, `/webhook`) |
| `smsService.js` | Telnyx client helpers and from-number env precedence |
| `sms_body_normalizer.js` | Optional middleware (`to` → `user`); may be unwired |
| `server.js` | Router mount path |
| `env_snapshot.txt` | Deployed env (`KEY=value`; `#` comments allowed) |
| `frontend_request.json` / `frontend_retry.json` / `frontend_final.json` | Client bodies for three `/api/sms/send` posts |
| `pm2_sms.log` | PM2 stdout (HTTP access lines + `response=` JSON) |
| `pm2_sms_error.log` | PM2 stderr |
| `nginx_access.log` | Reverse-proxy access log |
| `ops_note.txt` | Ops note (may be inaccurate) |

## Required outputs (`/app/output/`)

Emit these thirteen paths (names are fixed):

`root_cause_report.md`, `fix_plan.md`, `route_contract.json`, `env_audit.json`, `sms_service_audit.json`, `response_audit.json`, `decoy_log_audit.json`, `red_herring_audit.json`, `send_validation_audit.json`, `failure_chain.json`, `incident_timeline.json`, `incident_summary.json`, `verification_checklist.md`

### PM2 HTTP inventory → `incident_timeline.json`

Shape: `{"events": [...]}`.

One event per `pm2_sms.log` line matching `TIMESTAMP METHOD PATH STATUS` where `METHOD` ∈ {GET,POST,PUT,PATCH,DELETE}, `STATUS` is a 3-digit int, and `PATH` is the full path token (query string allowed). Skip PM2 startup lines, `response=` lines, and narrative lines. Keep log order. Fields: `timestamp`, `method`, `path`, `status` (int).

**Send-path classes:** exact path `path == "/api/sms/send"`; query send `path` starts with `"/api/sms/send?"`.

### Express contract → `route_contract.json`

Exact keys (names must match):

- `send_endpoint`: `"/api/sms/send"`
- `mounted_base_path`: `"/api/sms"`
- `required_body_fields` — `/send` destructuring names **without** defaults, **source order** (not sorted)
- `optional_body_fields` — `/send` destructuring names **with** `= default`, **source order** (names only)
- `initial_frontend_fields`, `retry_frontend_fields`, `final_frontend_fields` — **sorted** keys of each frontend JSON `body`
- `initial_contract_mismatch`, `retry_has_required_user`, `final_includes_country_code`, `normalizer_wired_in_server`
- `first_send_status`, `retry_send_status`, `third_send_status`, `query_send_status` (from timeline)

Do **not** use names like `required_bindings` / `optional_bindings`.


### Environment inventory → `env_audit.json`

Use **test-config required vars only** (from `GET /api/sms/test-config` in `sms.js`), not `smsService.js` fallback names:

1. `required_env_vars` — `TELNYX_API_KEY`, `TELNYX_PHONE_NUMBER`, sorted. Do not add `TELNYX_FROM_NUMBER`.
2. `present_env_vars` — every `TELNYX_*` key in `env_snapshot.txt`, sorted.
3. `missing_env_vars` — required names absent from the snapshot, sorted. Formula: `[name for name in required_env_vars if name not in env_snapshot]`.
4. `unused_telnyx_vars` — present keys not referenced as `process.env.TELNYX_*` in `sms.js` + `smsService.js` (merge references first-seen across both files), sorted.
5. `provider_ready` — **`len(missing_env_vars) == 0`**. Remains `false` if a required key is missing even when `TELNYX_FROM_NUMBER` is set.
6. `test_config_ready` — **`"TELNYX_PHONE_NUMBER" in env_snapshot`** (exact key only).

### Service from-number config → `sms_service_audit.json`

Keys: `from_var_precedence`, `test_config_vars`, `snapshot_effective_from`, `test_config_reports_missing_from` (`TELNYX_PHONE_NUMBER` absent from snapshot).

### Response pairing → `response_audit.json`

```json
{ "entries": [ { "response_timestamp", "request_timestamp", "method", "path", "http_status", "success", "error" } ] }
```

For each `response=` line in log order, pair with the most recent earlier timeline HTTP event. `success`: JSON null/missing → `false`. `error`: missing/null → `""`.

### Send attempt ledger → `failure_chain.json`

Top-level keys: **`send_attempts`** (array) and **`query_send`** (object) — not `attempts`.

| attempt_index | frontend_source |
|---------------|-----------------|
| 1 | `frontend_request.json` |
| 2 | `frontend_retry.json` |
| 3 | `frontend_final.json` |

Each `send_attempts` element keys: `attempt_index`, `frontend_source`, `http_status`, `response_error`, `failure_category` (`contract_mismatch` or `provider_from_number`).

`query_send` object keys **only**: `http_status`, `response_error`, `failure_category` (use `provider_from_number`). Identify the row as the POST whose path starts with `"/api/sms/send?"`, but **do not** include a `path` field in `query_send`.

### Validation gates → `send_validation_audit.json`

Exact top-level keys: `validation_gates` and `send_failures` (not `gates`).

`validation_gates`: ordered checks in `/send` before `SMSService.sendSMS`. Each element keys: `order` (int), `gate` (`user` | `message` | `provider_send`), `failure_http_status` (400 or 500):

1. `user` → 400  
2. `message` → 400  
3. `provider_send` → 500  

`send_failures`: one object per exact-path `POST /api/sms/send` (three, log order). Each element keys: `attempt_index`, `failed_gate`, `http_status`, `response_error` (not `error`).

`failed_gate` rules: HTTP 400 + error mentions user → `user`; HTTP 400 + error mentions message → `message`; HTTP 500 → `provider_send`.

### Summary / decoy / nginx notes

- **`incident_summary.json` keys:** `http_event_count`, `sms_send_attempts` (exact-path count), `sms_send_with_query_attempts`, `sms_send_statuses` (**exact-path sends only**, in log order — do not include query-send statuses), `test_config_calls`, `webhook_post_count`, `webhook_error_codes` (Telnyx `"code"` from `Message failed` lines, log order, **keep duplicates**), `error_log_spam_blocks`.
- **`decoy_log_audit.json` keys:** `error_log_file`, `spam_filter_code`, `spam_filter_line_count`, `is_root_cause_for_send_failures` (`false`).
- **`red_herring_audit.json` exact keys:**
  - `ops_note_file` = `"ops_note.txt"`
  - `ops_note_recommends_v2_rollback` (not `ops_note_mentions_v2_rollback`) — `true` if note mentions `/api/v2/sms/send`
  - `ops_note_blames_spam_filter` — `true` if note mentions spam / 40002
  - `ops_note_is_primary_root_cause` = `false`
  - `nginx_log_file` = `"nginx_access.log"`
  - `nginx_v2_sms_404_count` — lines with `POST /api/v2/sms/send` and status 404
  - `v2_route_is_root_cause` = `false`
  - `stderr_spam_filter_code` = `"40002"` (not `stderr_spam_code`)
  - `stderr_spam_filter_line_count` — count in `pm2_sms_error.log` (not `stderr_spam_line_count`)
  - `stderr_spam_is_root_cause` = `false`

### Markdown ops docs

- **`root_cause_report.md`:** cover `to` vs `user`, `countryCode`, unwired normalizer, `TELNYX_PHONE_NUMBER` vs `TELNYX_FROM_NUMBER`, `resolveFromNumber`, HTTP 400 then 500, Telnyx `40304`, stderr `40002` as unrelated, and that `/api/v2/sms/send` / ops note / nginx 404 are red herrings.
- **`fix_plan.md`:** include `pm2 restart all --update-env`, `/api/sms/test-config`, and `TELNYX_PHONE_NUMBER` or `TELNYX_FROM_NUMBER`. Focus on frontend `user` and Telnyx env alignment. You may note the normalizer is unused — **do not** list wiring it as a step. **Do not** recommend v2 route rollback.
- **`verification_checklist.md`:** mention `pm2`, `webhook`, `route`, and `test-config` or `test_config`.

All JSON must parse.
