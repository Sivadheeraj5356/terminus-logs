#!/usr/bin/env bash
set -euo pipefail

cp /opt/task_data/tribunal-game /workspace/tribunal-game
chmod +x /workspace/tribunal-game
echo "[solve] tribunal-game binary deployed to /workspace/tribunal-game"
