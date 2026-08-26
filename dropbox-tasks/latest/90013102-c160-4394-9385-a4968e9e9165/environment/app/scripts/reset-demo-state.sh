#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p /output /logs/agent state/spool
rm -f /output/request-trace.json /logs/agent/proxy-audit.jsonl
find state/spool -mindepth 1 -delete 2>/dev/null || true
rm -f /tmp/demo-*.sock /tmp/demo-proxy.ready /tmp/demo-backend-capture.json 2>/dev/null || true
echo "demo state reset"
