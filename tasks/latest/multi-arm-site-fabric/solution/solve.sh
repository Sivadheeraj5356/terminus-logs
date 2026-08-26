#!/usr/bin/env bash
set -euo pipefail

log() { printf '[solve] %s\n' "$1"; }

STAGE=/app/environment/bringup
ETC=/etc/sitefab

log "author bring-up fabric under /app/environment/bringup"
mkdir -p \
  "$STAGE/policy.d" \
  "$STAGE/templates" \
  "$STAGE/units/alpha" \
  "$STAGE/units/beta/data.mount.d" \
  "$STAGE/units/gamma/data.mount.d" \
  "$STAGE/units/remote"

cat > "$STAGE/sitefab.conf" <<'EOF'
[Journal]
Path=/var/lib/sitefab/journal.json

[Reconcile]
Mode=gen-hand-bs
RequireDropIns=yes

[Barrier]
BumpRev=yes
ClearStale=yes
CommitPending=yes
ClearLatch=yes

[Visibility]
EpochOnRwAfterRo=yes
OmitStaleRefs=yes
DependentHold=until-propagate
DependToken=x-hold
MaintLatch=yes
EOF

cat > "$STAGE/policy.d/20-digest.conf" <<'EOF'
[Digest]
Source=durable-store
EOF

cat > "$STAGE/policy.d/40-carry.conf" <<'EOF'
[Journal]
Carry=epochs,last_ro,stale_ref,pending_arms,latch
EOF

cat > "$STAGE/policy.d/60-compile.conf" <<'EOF'
[Compile]
PreferUnit=strict
SealPaths=yes
EOF

cat > "$STAGE/templates/local-arm.mount" <<'EOF'
[Mount]
Type=none
X-Sitefab-Remote=no
EOF

cat > "$STAGE/templates/remote-nf.mount" <<'EOF'
[Mount]
Type=none
X-Sitefab-Remote=yes
EOF

# --- alpha ---
cat > "$STAGE/units/alpha/data.mount" <<'EOF'
[Unit]
Description=sitefab alpha/data
X-Sitefab-Inherit=local-arm

[Mount]
What=/srv/backing/alpha/data
Where=/srv/arms/alpha/data
Options=ro
X-Sitefab-OrderHint=10
EOF

cat > "$STAGE/units/alpha/share.mount" <<'EOF'
[Unit]
Description=sitefab alpha/share
X-Sitefab-Inherit=local-arm
X-Sitefab-Depends=data

[Mount]
What=/srv/backing/alpha/share
Where=/srv/arms/alpha/share
Options=rw,x-hold
X-Sitefab-OrderHint=20
X-Sitefab-Propagate=rshared
EOF

cat > "$STAGE/units/alpha/cache.mount" <<'EOF'
[Unit]
Description=sitefab alpha/cache
X-Sitefab-Inherit=local-arm
X-Sitefab-Depends=share
X-Sitefab-LinkAfter=share

[Mount]
What=/srv/backing/alpha/cache
Where=/srv/arms/alpha/cache
Options=rw,x-hold
X-Sitefab-OrderHint=30
X-Sitefab-Propagate=slave
EOF

# --- beta ---
cat > "$STAGE/units/beta/data.mount" <<'EOF'
[Unit]
Description=sitefab beta/data
X-Sitefab-Inherit=local-arm

[Mount]
What=/srv/backing/beta/data
Where=/srv/arms/beta/data
Options=ro
X-Sitefab-OrderHint=10
EOF

cat > "$STAGE/units/beta/work.mount" <<'EOF'
[Unit]
Description=sitefab beta/work
X-Sitefab-Inherit=local-arm

[Mount]
What=/srv/backing/beta/work
Where=/srv/arms/beta/work
Options=rw
X-Sitefab-OrderHint=15
EOF

cat > "$STAGE/units/beta/spill.mount" <<'EOF'
[Unit]
Description=sitefab beta/spill
X-Sitefab-Inherit=local-arm
X-Sitefab-Depends=work
X-Sitefab-LinkAfter=work

[Mount]
What=/srv/backing/beta/spill
Where=/srv/arms/beta/spill
Options=rw,x-hold
X-Sitefab-OrderHint=25
X-Sitefab-Propagate=private
EOF

cat > "$STAGE/units/beta/data.mount.d/10-generator.conf" <<'EOF'
[Mount]
Options=ro,bs=work
EOF

cat > "$STAGE/units/beta/data.mount.d/20-hand.conf" <<'EOF'
[Mount]
Options=ro
EOF

# --- gamma ---
cat > "$STAGE/units/gamma/root.mount" <<'EOF'
[Unit]
Description=sitefab gamma/root
X-Sitefab-Inherit=local-arm

[Mount]
What=/srv/backing/gamma/root
Where=/srv/arms/gamma/root
Options=ro
X-Sitefab-OrderHint=5
EOF

cat > "$STAGE/units/gamma/stage.mount" <<'EOF'
[Unit]
Description=sitefab gamma/stage
X-Sitefab-Inherit=local-arm
X-Sitefab-Depends=root

[Mount]
What=/srv/backing/gamma/stage
Where=/srv/arms/gamma/stage
Options=rw,x-hold
X-Sitefab-OrderHint=12
X-Sitefab-Propagate=rshared
EOF

cat > "$STAGE/units/gamma/publish.mount" <<'EOF'
[Unit]
Description=sitefab gamma/publish
X-Sitefab-Inherit=local-arm
X-Sitefab-Depends=stage
X-Sitefab-LinkAfter=stage

[Mount]
What=/srv/backing/gamma/publish
Where=/srv/arms/gamma/publish
Options=rw,x-hold
X-Sitefab-OrderHint=18
X-Sitefab-Propagate=slave
EOF

cat > "$STAGE/units/gamma/data.mount.d/10-generator.conf" <<'EOF'
[Mount]
Options=ro,bs=stage
EOF

cat > "$STAGE/units/gamma/data.mount.d/20-hand.conf" <<'EOF'
[Mount]
Options=ro
EOF

# --- remote ---
cat > "$STAGE/units/remote/data.mount" <<'EOF'
[Unit]
Description=sitefab remote/data
X-Sitefab-Inherit=remote-nf

[Mount]
What=/srv/backing/remote/data
Where=/srv/arms/remote/data
Options=rw
X-Sitefab-OrderHint=10
EOF

cat > "$STAGE/units/remote/scratch.mount" <<'EOF'
[Unit]
Description=sitefab remote/scratch
X-Sitefab-Inherit=remote-nf
X-Sitefab-LinkAfter=data

[Mount]
What=/srv/backing/remote/scratch
Where=/srv/arms/remote/scratch
Options=rw,_nf
X-Sitefab-OrderHint=20
X-Sitefab-Propagate=rslave
EOF

cat > "$STAGE/units/remote/archive.mount" <<'EOF'
[Unit]
Description=sitefab remote/archive
X-Sitefab-Inherit=remote-nf
X-Sitefab-LinkAfter=scratch

[Mount]
What=/srv/backing/remote/archive
Where=/srv/arms/remote/archive
Options=ro,_nf
X-Sitefab-OrderHint=30
X-Sitefab-Propagate=slave
EOF

cat > "$STAGE/units/remote/mirror.mount" <<'EOF'
[Unit]
Description=sitefab remote/mirror
X-Sitefab-Inherit=remote-nf
X-Sitefab-LinkAfter=archive

[Mount]
What=/srv/backing/remote/mirror
Where=/srv/arms/remote/mirror
Options=ro
X-Sitefab-OrderHint=40
X-Sitefab-Propagate=private
EOF


log "install fabric into /etc/sitefab"
rm -rf "$ETC"
mkdir -p "$ETC"
cp -a "$STAGE/." "$ETC/"
mkdir -p /var/lib/sitefab /app/output

log "smoke durable toggle"
rm -f /var/lib/sitefab/journal.json /app/output/sitefab_report.json
/app/bin/sitefab --script=/app/environment/scenarios/n02_rw_toggle.script
python3 - <<'PY'
import json
from pathlib import Path
rep = json.loads(Path("/app/output/sitefab_report.json").read_text())
epochs = {c["arm"]: c["epoch"] for c in rep["consumer_refs"]}
assert epochs.get("data", 0) > 0
assert len(rep["durable_digest"]) == 64
assert "maintenance_latch" in rep
print("ok", rep["durable_digest"][:12], sorted(epochs))
PY

log "done"
