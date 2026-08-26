#!/bin/bash
set -euo pipefail
go build -C /app/environment -o /tmp/fxctl ./cmd/fxctl
