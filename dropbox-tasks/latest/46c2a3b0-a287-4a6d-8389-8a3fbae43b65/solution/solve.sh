#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p /app/bin /app/output /app/src
cp "$SCRIPT_DIR/main.go" /app/main.go
cp "$SCRIPT_DIR/go.mod" /app/go.mod
cat > /app/run.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
export CGO_ENABLED=0
export GOPROXY=off
export PATH="/usr/local/go/bin:${PATH}"
mkdir -p /app/bin /app/output
cd /app
go build -o /app/bin/backup-dedup /app/main.go
exec /app/bin/backup-dedup
EOF
chmod +x /app/run.sh
bash /app/run.sh
