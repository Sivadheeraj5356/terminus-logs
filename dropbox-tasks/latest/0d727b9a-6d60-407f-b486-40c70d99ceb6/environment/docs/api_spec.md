# Obsidian Vault Service — API Specification (Security Contract)

Service: `obsidian-vault` (WEBrick, Ruby)
Base URL: `http://localhost:8080`

This document is the **authoritative security and API contract** for all clients and is
used as the reference when hardening the service against auth bypass, replay, privilege
escalation, race conditions, and abuse. Where the current implementation diverges from
this spec, the spec wins.

---

## Authentication Model

### Admin Endpoints (`/admin/*`)

Both admin endpoints require three HTTP request headers:

| Header | Format | Description |
|---|---|---|
| `X-Timestamp` | Unix epoch integer (seconds) | Request timestamp. Rejected if more than **90 seconds** in the past or future relative to the server's current time (i.e., `|server_time − timestamp| <= 90`). |
| `X-Nonce` | Arbitrary non-empty string | One-time value. Each nonce may only be used once per server lifetime. A repeated nonce returns 403 even if the signature is valid. |
| `X-Admin-Signature` | HMAC hex digest (lowercase) | `HMAC-SHA256(admin_secret, "<path>:<X-Timestamp>:<X-Nonce>")` |

The signing algorithm is **HMAC-SHA256**. The `admin_secret` is read from
`settings.yaml`. Requests missing any of the three headers return `403 Forbidden`.

**Response 200** when all headers are valid and the action succeeds.

**Response 403** when:
- Any required header is missing.
- The timestamp falls outside the ±90-second window.
- The HMAC signature does not match.
- The nonce has already been used (replay attack).

### Moderator Verbs (`POST /command` with a moderator verb)

Moderator verbs (`reset_puzzle`, `set_attempts`, `reveal_answer`, `grant_hint_token`)
require the `X-Moderator-Signature` request header:

| Header | Format | Description |
|---|---|---|
| `X-Moderator-Signature` | HMAC hex digest (lowercase) | `HMAC-SHA256(moderator_key, <raw request body bytes>)` |

The signature is computed over the **exact raw bytes** of the JSON request body,
before any parsing. The `moderator_key` is read from `settings.yaml`. An empty or
absent `moderator_key` must deny all moderator access.

**Response 403** for missing or incorrect signature.

### Session Tokens

The `attempt` and `unlock` verbs require a valid session token:

| Header | Format |
|---|---|
| `X-Session-Token` | UUID obtained from `POST /session/new` |

**Response 401** when the header is missing or the session has expired.

### Rate Limiting

All `/command` requests are rate-limited per client IP to **`rate_limit_rpm`** requests
per 60-second sliding window (default: 30). The `RATE_LIMIT_RPM` environment variable,
when set, overrides the YAML value for the process lifetime (used by the property-test
harness). Excess requests return:

```json
{"error": "rate limit exceeded", "status": 429}
```

---

## Endpoints

### GET /health

Liveness check. Always returns 200 when the service is running.

**Response 200:**
```json
{"status": "ok", "service": "obsidian-vault"}
```

---

### GET /state

Returns current puzzle and vault state for all puzzles.

**Response 200:**
```json
{
  "puzzles": [
    {"id": "cipher_alpha", "solved": false, "attempts_remaining": 3},
    {"id": "cipher_beta",  "solved": false, "attempts_remaining": 3},
    {"id": "cipher_gamma", "solved": false, "attempts_remaining": 3}
  ],
  "vault": {"id": "vault_door", "state": "locked"}
}
```

`vault.state` is `"locked"` or `"open"`.

---

### GET /hint?puzzle_id=\<id\>

Returns a contextual hint string for the named puzzle.

**Query Parameters:**
- `puzzle_id` (required) — one of `cipher_alpha`, `cipher_beta`, `cipher_gamma`

**Response 200:**
```json
{"puzzle_id": "cipher_alpha", "hint": "A faint inscription reads: ..."}
```

**Response 400:** `puzzle_id` query parameter missing.

**Response 404:** `puzzle_id` not recognised.

---

### POST /session/new

Creates a new game session. Returns a session token for use with stateful verbs.

**Request:** any body (ignored)

**Response 200:**
```json
{"session_id": "550e8400-e29b-41d4-a716-446655440000"}
```

---

### POST /command

Dispatches a game or moderator verb. All request bodies must be valid JSON.

**Request headers:**
- `Content-Type: application/json` (required)
- `X-Session-Token: <uuid>` (required for `attempt` and `unlock` verbs)
- `X-Moderator-Signature: <hex>` (required for moderator verbs)

**Request body schema:**
```json
{
  "verb": "<string>",
  "payload": {
    "target": "<string>",
    "data": "<string|null>"
  }
}
```

**Game verbs:** `examine`, `inspect`, `attempt`, `unlock`, `hint`, `use`

**Moderator verbs:** `reset_puzzle`, `set_attempts`, `reveal_answer`, `grant_hint_token`

#### Verb: attempt

Submits an answer for a named puzzle. Requires `X-Session-Token`.

Answers are normalised to lowercase and stripped of leading/trailing whitespace before
hashing with **SHA-256**.

Request:
```json
{"verb": "attempt", "payload": {"target": "cipher_alpha", "data": "delta"}}
```

Response (correct):
```json
{"ok": true, "unlocks": "cipher_beta"}
```

Response (incorrect):
```json
{"ok": false, "reason": "wrong_answer", "attempts_remaining": 2}
```

Response (no attempts left):
```json
{"ok": false, "reason": "no_attempts"}
```

Response (prerequisite puzzle not solved):
```json
{"ok": false, "reason": "prereq_unmet"}
```

#### Verb: unlock

Attempts the vault combination after all puzzles are solved. Requires `X-Session-Token`.

```json
{"verb": "unlock", "payload": {"target": "vault_door", "data": "deltalock"}}
```

Response (correct):
```json
{"ok": true, "vault": {"id": "vault_door", "state": "open"}}
```

#### Verb: examine / inspect

Returns the room description. No session token required.

```json
{"ok": true, "description": "You are locked inside a Victorian-era bank vault..."}
```

#### Moderator verb: reset_puzzle

Resets a puzzle's attempt counter. Requires `X-Moderator-Signature`.

```json
{"verb": "reset_puzzle", "payload": {"puzzle_id": "cipher_alpha"}}
```

**Response 403** if the signature is missing or incorrect.

---

### POST /admin/debug-dump

Dumps internal service state. Requires the three admin authentication headers.

**Response 200** (valid signature):
```json
{
  "debug": true,
  "settings": {"debug_mode": false, "session_timeout": 3600},
  "puzzle_state": {...},
  "vault": {...},
  "sessions": 1
}
```

**Response 403** for any authentication failure (see Authentication section).

---

### POST /admin/force-unlock

Forces the vault to the open state. Requires the three admin authentication headers.

**Response 200** (valid signature):
```json
{"ok": true, "message": "vault force-opened", "vault": {"id": "vault_door", "state": "open"}}
```

**Response 403** for any authentication failure.

---

## Answer Hashing

All puzzle answers are normalised before hashing:
1. Strip leading and trailing whitespace.
2. Convert to lowercase.
3. Hash with **SHA-256** (hex-encoded, lowercase).

The `vault` combination is hashed the same way.

---

## Status Codes

| Code | Meaning |
|---|---|
| 200 | Success |
| 400 | Bad request (missing field, invalid JSON) |
| 401 | Unauthorised (missing or invalid session token) |
| 403 | Forbidden (signature missing/wrong, nonce replayed, timestamp expired) |
| 404 | Not found (unknown puzzle_id, unrecognised path) |
| 405 | Method not allowed |
| 422 | Unprocessable (puzzles incomplete for unlock) |
| 429 | Rate limit exceeded |
