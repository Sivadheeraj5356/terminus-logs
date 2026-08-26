#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
cat > /logs/verifier/ctrf.json <<'EOF'
{
  "results": {
    "tool": {"name": "pytest"},
    "summary": {"tests": 0, "passed": 0, "failed": 0, "pending": 0, "skipped": 0, "other": 0, "start": 0, "stop": 0},
    "tests": []
  }
}
EOF

ensure_files() {
  [ -f /logs/verifier/reward.txt ] || echo 0 > /logs/verifier/reward.txt
  [ -f /logs/verifier/ctrf.json ] || cat > /logs/verifier/ctrf.json <<'EOF'
{
  "results": {
    "tool": {"name": "pytest"},
    "summary": {"tests": 0, "passed": 0, "failed": 0, "pending": 0, "skipped": 0, "other": 0, "start": 0, "stop": 0},
    "tests": []
  }
}
EOF
}
trap ensure_files EXIT

if [ "$PWD" = "/" ]; then
  echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script." >&2
  exit 1
fi

/opt/verifier-venv/bin/pytest \
  --ctrf /logs/verifier/ctrf.json \
  --timeout=120 \
  /tests/test_outputs.py -rA

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
