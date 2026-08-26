#!/bin/bash
set -euo pipefail
cd /app
if patch -p1 --dry-run < /solution/ctc-caption-repair.patch >/dev/null 2>&1; then
  patch -p1 < /solution/ctc-caption-repair.patch
fi
/app/rehearse_caption_beam.sh
