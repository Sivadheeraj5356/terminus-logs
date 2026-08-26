#!/usr/bin/env bash
set -euo pipefail

mkdir -p /usr/lib/sitefab /app/bin /app/output /app/share \
  /etc/sitefab/units /etc/sitefab/policy.d /etc/sitefab/templates /var/lib/sitefab

ln -sfn /app/environment /app/share/sitefab

install -m 0555 /app/environment/lib/sitefab/engine.py /usr/lib/sitefab/engine.py
install -m 0555 /app/environment/lib/sitefab/law_digest.py /usr/lib/sitefab/law_digest.py
install -m 0755 /app/environment/scripts/sitefab_cli /app/bin/sitefab

python3 /app/environment/scripts/write_seal.py

# Keep the appliance under /usr/lib only; ops surface is /etc/sitefab.
rm -rf /app/environment/lib
