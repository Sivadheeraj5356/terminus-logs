# Operator Runbook

## Build

```bash
cd /app
make build
# or
./scripts/build.sh
```

Produces `/app/bin/proxy-local`, `/app/bin/backend-capture`, and `/app/bin/spool-inspect`.

## Start backend capture

```bash
bin/backend-capture --listen-unix /tmp/backend.sock --output /tmp/backend-capture.json
```

## Start proxy

```bash
mkdir -p /output /logs/agent state/spool
bin/proxy-local serve \
  --listen-unix /tmp/proxy.sock \
  --backend-unix /tmp/backend.sock \
  --config config/proxy.json \
  --profiles config/profiles \
  --keyring config/keyring-public.json \
  --state-dir state \
  --audit-log /logs/agent/proxy-audit.jsonl \
  --trace /output/request-trace.json \
  --ready-file /tmp/proxy.ready
```

## Recover spool

```bash
bin/proxy-local recover \
  --backend-unix /tmp/backend.sock \
  --config config/proxy.json \
  --trace /output/request-trace.json
```

## Inspect spool

```bash
bin/spool-inspect --dir state/spool
bin/spool-inspect --dir state/spool --record <record-id>
```

## Public demos

```bash
./scripts/demo-current.sh
./scripts/demo-duplicate.sh
./scripts/demo-epoch.sh
./scripts/demo-restart.sh
./scripts/reset-demo-state.sh
```

## Paths

| Path | Purpose |
|------|---------|
| `/app/config/proxy.json` | Default operational config |
| `/app/state/spool` | Durable queued requests |
| `/output/request-trace.json` | Required trace artifact |
| `/logs/agent/proxy-audit.jsonl` | Audit JSONL |
| `/app/docs/request-semantics.md` | Normative contract |

## Send raw requests

Use `socat` or similar to write exact bytes to the proxy Unix socket:

```bash
socat - UNIX-CONNECT:/tmp/proxy.sock < data/requests/simple-current.http
```
