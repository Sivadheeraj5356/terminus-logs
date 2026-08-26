#!/usr/bin/env bash
set -euo pipefail
export GNUPGHOME="${1:-/app/fixtures/gnupg}"
mkdir -p "$GNUPGHOME"
chmod 700 "$GNUPGHOME"
if gpg --list-secret-keys --with-colons 2>/dev/null | grep -q '^sec:'; then
  exit 0
fi
cat > /tmp/reelseal-gpg-batch <<'BATCH'
%no-protection
Key-Type: RSA
Key-Length: 2048
Name-Real: ReelSeal Desk
Name-Email: reelseal@local
Expire-Date: 0
%commit
BATCH
gpg --batch --generate-key /tmp/reelseal-gpg-batch
rm -f /tmp/reelseal-gpg-batch
