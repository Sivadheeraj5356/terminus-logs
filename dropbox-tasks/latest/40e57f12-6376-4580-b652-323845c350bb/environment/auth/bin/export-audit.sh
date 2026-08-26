#!/bin/bash
set -euo pipefail
exec /app/auth/bin/tokensvc export-audit
