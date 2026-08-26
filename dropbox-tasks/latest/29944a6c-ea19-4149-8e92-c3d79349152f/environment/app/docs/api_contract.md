# Release-gate HTTP contract

The gate service listens on `127.0.0.1:8971` and serves two endpoints.
Canonicalization, decision semantics, and temporal semantics are stated in
the shipped standard; this document describes only the request/response
plumbing and the connection contract.

## GET /health

Returns exactly the bytes `{"status":"ok"}` with
`Content-Type: application/json`. No other fields, no trailing newline.

## POST /gate/evaluate

Request body — a JSON object with exactly three required keys:

| Key | Type | Notes |
| --- | --- | --- |
| `repo` | string | Absolute filesystem path to the repository root. |
| `tag` | string | Full tag ref (e.g. `release/v2.1.0`). Must exist in the repo. |
| `evaluationTime` | string | ISO-8601 UTC timestamp, e.g. `2026-07-01T12:00:00Z`. |

A missing key, an extra key, a value with the wrong type, or an
`evaluationTime` that is not a valid ISO-8601 UTC timestamp responds
with HTTP 400 and body `{"error":"malformed request"}`.

Response — HTTP 200 in all decision cases (denials do not use a 4xx status).
The response body's shape is described in the shipped standard.

## Connection contract

The service opens a fresh read-only JDBC connection per request against
`/app/data/approvals.mv.db`, and closes the connection before the response
is sent. The connection URL is:

```
jdbc:h2:file:/app/data/approvals;IFEXISTS=TRUE;ACCESS_MODE_DATA=r;AUTO_SERVER=FALSE
```

Callers may modify the DB file between requests via the H2 `RunScript` CLI;
those modifications must be visible to the next request without restarting
the service.

## Static-only evaluation

The service must not create containers, invoke `docker` in any form, or
shell out to `docker compose` to resolve the compose model. All evaluation
is static.
