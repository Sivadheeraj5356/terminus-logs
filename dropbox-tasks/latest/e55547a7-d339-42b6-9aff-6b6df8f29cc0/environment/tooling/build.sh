#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
npm run build
mkdir -p bin
cat > bin/cascade-ingest <<'EOF'
#!/usr/bin/env bash
exec node /app/dist/bin/ingest.js "$@"
EOF
cat > bin/cascade-export <<'EOF'
#!/usr/bin/env bash
exec node /app/dist/bin/export.js "$@"
EOF
chmod +x bin/cascade-ingest bin/cascade-export
