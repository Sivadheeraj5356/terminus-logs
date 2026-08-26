#!/bin/bash
# Reference solution: bring the DHCP lease appliance into full production
# operation on this host, hardened. Host administration only — a dedicated
# service account, one configuration file the tools read, private state/log/backup
# directories with least privilege, a shared helper library, the administrative
# and maintenance commands on PATH (with a config validator, an integrity checker,
# a reconciling multi-pool provisioner that rejects overlapping CIDRs and is
# lock-serialised and drift-checkable, integrity-checked and retained backups with
# pre-restore safety snapshots, an admin audit trail, and a per-pool report), a
# WAL-mode state database, resource limits, log rotation, and scheduled jobs. The
# lease daemon ships pre-built under /opt/dhcpd and is not touched.
set -euo pipefail

# 1. Dedicated, unprivileged service account, and an operator group for delegation.
getent group dhcpd >/dev/null || groupadd --system dhcpd
getent passwd dhcpd >/dev/null || \
    useradd --system --gid dhcpd --home-dir /var/lib/dhcpd \
            --no-create-home --shell /usr/sbin/nologin dhcpd
getent group dhcpdops >/dev/null || groupadd --system dhcpdops

# 2. Private state, log, and backup directories owned by the service account.
install -d -o dhcpd -g dhcpd -m 0750 /var/lib/dhcpd
install -d -o dhcpd -g dhcpd -m 0750 /var/log/dhcpd
install -d -o dhcpd -g dhcpd -m 0700 /var/lib/dhcpd/backups
install -d -o dhcpd -g dhcpd -m 0750 /var/lib/dhcpd/run

# 3. Configuration tree and the service configuration file the tools read.
install -d -m 0755 /etc/dhcpd /etc/dhcpd/pools.d
cat > /etc/dhcpd/dhcpd.conf <<'CONF'
# DHCP lease appliance configuration - sourced by every administrative command.
STATE_DB=/var/lib/dhcpd/dhcp.db
POOL_DIR=/etc/dhcpd/pools.d
LOG_DIR=/var/log/dhcpd
BACKUP_DIR=/var/lib/dhcpd/backups
RUN_DIR=/var/lib/dhcpd/run
BACKUP_KEEP=7
RUN_USER=dhcpd
CONF
chmod 0644 /etc/dhcpd/dhcpd.conf

# 4. Resource limits for the service account.
cat > /etc/security/limits.d/dhcpd.conf <<'LIM'
dhcpd soft nofile 4096
dhcpd hard nofile 8192
dhcpd soft nproc  256
LIM
chmod 0644 /etc/security/limits.d/dhcpd.conf

# 5. Shared helper library sourced by the tooling: config resolution, CIDR
#    arithmetic, overlap detection, and the admin audit trail.
install -d -m 0755 /usr/local/lib/dhcpd
cat > /usr/local/lib/dhcpd/common.sh <<'COMMON'
#!/bin/bash
CONF=/etc/dhcpd/dhcpd.conf
[ -f "$CONF" ] && . "$CONF"
DB="${DHCPD_DB:-${STATE_DB:-/var/lib/dhcpd/dhcp.db}}"
POOLDIR="${DHCPD_POOLS_DIR:-${POOL_DIR:-/etc/dhcpd/pools.d}}"
BACKUPDIR="${DHCPD_BACKUP_DIR:-${BACKUP_DIR:-/var/lib/dhcpd/backups}}"
LOGDIR="${LOG_DIR:-/var/log/dhcpd}"
RUNDIR="${DHCPD_RUN_DIR:-${RUN_DIR:-/var/lib/dhcpd/run}}"
KEEP="${DHCPD_BACKUP_KEEP:-${BACKUP_KEEP:-7}}"
ADMIN_LOG="$LOGDIR/admin.log"
DAEMON=/opt/dhcpd/libexec/dhcpd

admin_audit() {  # <command> <outcome> [detail...]
    printf '%s cmd=%s %s\n' "$(date -u +%FT%TZ)" "$1" "${*:2}" >> "$ADMIN_LOG" 2>/dev/null || true
}

valid_cidr() {   # a.b.c.d/p
    local cidr="$1" ip p a b c d o
    [[ "$cidr" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/[0-9]{1,2}$ ]] || return 1
    ip="${cidr%/*}"; p="${cidr#*/}"
    IFS=. read -r a b c d <<<"$ip"
    for o in "$a" "$b" "$c" "$d"; do [ "$o" -le 255 ] || return 1; done
    [ "$p" -le 32 ]
}

cidr_lo_hi() {   # a.b.c.d/p -> "lo hi" (unsigned 32-bit ints)
    local cidr="$1" ip p a b c d base mask
    ip="${cidr%/*}"; p="${cidr#*/}"
    IFS=. read -r a b c d <<<"$ip"
    base=$(( (a<<24)|(b<<16)|(c<<8)|d ))
    if [ "$p" -le 0 ]; then mask=0; else mask=$(( (0xFFFFFFFF << (32-p)) & 0xFFFFFFFF )); fi
    echo "$(( base & mask )) $(( (base & mask) | (~mask & 0xFFFFFFFF) ))"
}

overlaps() {     # lo1 hi1 lo2 hi2 -> 0 if the two ranges intersect
    [ "$1" -le "$4" ] && [ "$3" -le "$2" ]
}
COMMON
chmod 0644 /usr/local/lib/dhcpd/common.sh

# 6. Administrative front-end: run a request document through the daemon.
cat > /usr/local/sbin/dhcpdctl <<'CTL'
#!/bin/bash
CONF=/etc/dhcpd/dhcpd.conf
[ -f "$CONF" ] && . "$CONF"
export DHCPD_DB="${DHCPD_DB:-${STATE_DB:-/var/lib/dhcpd/dhcp.db}}"
exec /opt/dhcpd/libexec/dhcpd "$@"
CTL
chmod 0755 /usr/local/sbin/dhcpdctl

# 7. Config validator: the config file and every declared pool must be well formed.
cat > /usr/local/sbin/dhcpd-check <<'CHECK'
#!/bin/bash
set -uo pipefail
. /usr/local/lib/dhcpd/common.sh
rc=0
for key in STATE_DB POOL_DIR LOG_DIR BACKUP_DIR; do
    grep -qE "^$key=" "$CONF" || { echo "config missing $key" >&2; rc=1; }
done
shopt -s nullglob
for f in "$POOLDIR"/*.json; do
    if ! jq -e . "$f" >/dev/null 2>&1; then echo "invalid JSON: $f" >&2; rc=1; continue; fi
    cidr="$(jq -r '.cidr // empty' "$f")"; ls="$(jq -r '.lease_secs // empty' "$f")"
    valid_cidr "$cidr" || { echo "invalid cidr in $f: $cidr" >&2; rc=1; }
    case "$ls" in ''|*[!0-9]*) echo "invalid lease_secs in $f: $ls" >&2; rc=1 ;; *)
        [ "$ls" -gt 0 ] || { echo "non-positive lease_secs in $f" >&2; rc=1; } ;; esac
done
exit $rc
CHECK
chmod 0755 /usr/local/sbin/dhcpd-check

# 8. Integrity checker: the database must be structurally sound and carry the schema.
cat > /usr/local/sbin/dhcpd-fsck <<'FSCK'
#!/bin/bash
set -uo pipefail
. /usr/local/lib/dhcpd/common.sh
[ -f "$DB" ] || { echo "no database at $DB" >&2; exit 1; }
res="$(sqlite3 "$DB" 'PRAGMA integrity_check;' 2>/dev/null)" || { echo "cannot open $DB" >&2; exit 1; }
[ "$res" = "ok" ] || { echo "integrity check failed: $res" >&2; exit 1; }
for t in pools leases reservations declines; do
    sqlite3 "$DB" "SELECT 1 FROM $t LIMIT 0;" >/dev/null 2>&1 || { echo "missing table $t" >&2; exit 1; }
done
echo "ok"
FSCK
chmod 0755 /usr/local/sbin/dhcpd-fsck

# 9. Reconciling provisioner: lock-serialised, rejects overlapping CIDRs, supports
#    a non-mutating drift --check, and reconciles the live set to the declared set.
cat > /usr/local/sbin/dhcpd-provision <<'PROV'
#!/bin/bash
set -uo pipefail
. /usr/local/lib/dhcpd/common.sh
CHECK_ONLY=0; [ "${1:-}" = "--check" ] && CHECK_ONLY=1
shopt -s nullglob

# validate every declaration before touching the database: a single malformed
# pool file aborts the whole run with no partial changes.
for f in "$POOLDIR"/*.json; do
    [ -e "$f" ] || continue
    jq -e . "$f" >/dev/null 2>&1 || { echo "invalid pool file: $f" >&2; exit 2; }
    c="$(jq -r '.cidr // empty' "$f")"; l="$(jq -r '.lease_secs // empty' "$f")"
    valid_cidr "$c" || { echo "invalid cidr in $f: $c" >&2; exit 2; }
    case "$l" in ''|*[!0-9]*) echo "invalid lease_secs in $f" >&2; exit 2 ;; *)
        [ "$l" -gt 0 ] || { echo "non-positive lease_secs in $f" >&2; exit 2; } ;; esac
done

# serialise concurrent provisions
install -d -m 0750 "$RUNDIR" 2>/dev/null || true
exec 9>"$RUNDIR/provision.lock" 2>/dev/null || true
flock 9 2>/dev/null || true

declare -A want_ls want_file
for f in "$POOLDIR"/*.json; do
    cidr="$(jq -r '.cidr // empty' "$f")"; [ -n "$cidr" ] || continue
    want_ls["$cidr"]="$(jq -r '.lease_secs // empty' "$f")"; want_file["$cidr"]="$f"
done

mapfile -t have_cidrs < <(sqlite3 "$DB" "SELECT cidr FROM pools;")
declare -A have_ls
while IFS='|' read -r c l; do [ -n "$c" ] && have_ls["$c"]="$l"; done \
    < <(sqlite3 "$DB" "SELECT cidr||'|'||lease_secs FROM pools;")

# drift = any declared pool missing/changed, or any live pool not declared
drift=0
for c in "${!want_ls[@]}"; do
    [ "${have_ls[$c]+x}" ] || { drift=1; break; }
    [ "${have_ls[$c]}" = "${want_ls[$c]}" ] || { drift=1; break; }
done
if [ "$drift" -eq 0 ]; then
    for c in "${have_cidrs[@]}"; do [ -n "$c" ] || continue; [ "${want_ls[$c]+x}" ] || { drift=1; break; }; done
fi
if [ "$CHECK_ONLY" -eq 1 ]; then
    [ "$drift" -eq 0 ] && exit 0 || { echo "drift detected" >&2; exit 3; }
fi

rc=0
# remove pools no longer declared, cascading their state
for c in "${have_cidrs[@]}"; do
    [ -n "$c" ] || continue
    if [ -z "${want_ls[$c]+x}" ]; then
        pid="$(sqlite3 "$DB" "SELECT id FROM pools WHERE cidr='$c';")"
        sqlite3 "$DB" "DELETE FROM leases WHERE pool_id=$pid; DELETE FROM reservations WHERE pool_id=$pid;
                       DELETE FROM declines WHERE pool_id=$pid; DELETE FROM pools WHERE id=$pid;"
        unset "have_ls[$c]"
    fi
done

# ranges currently kept, for overlap checks
declare -A keep_lo keep_hi
for c in "${!have_ls[@]}"; do read -r lo hi <<<"$(cidr_lo_hi "$c")"; keep_lo["$c"]=$lo; keep_hi["$c"]=$hi; done

for cidr in "${!want_ls[@]}"; do
    if [ "${have_ls[$cidr]+x}" ]; then
        [ "${have_ls[$cidr]}" != "${want_ls[$cidr]}" ] && \
            sqlite3 "$DB" "UPDATE pools SET lease_secs=${want_ls[$cidr]} WHERE cidr='$cidr';"
        continue
    fi
    read -r lo hi <<<"$(cidr_lo_hi "$cidr")"
    clash=""
    for c in "${!keep_lo[@]}"; do
        overlaps "$lo" "$hi" "${keep_lo[$c]}" "${keep_hi[$c]}" && { clash="$c"; break; }
    done
    if [ -n "$clash" ]; then
        echo "pool $cidr overlaps $clash; refusing" >&2; rc=1; continue
    fi
    DHCPD_DB="$DB" "$DAEMON" "${want_file[$cidr]}" >/dev/null && { keep_lo["$cidr"]=$lo; keep_hi["$cidr"]=$hi; }
done
admin_audit dhcpd-provision "rc=$rc db=$DB"
exit $rc
PROV
chmod 0755 /usr/local/sbin/dhcpd-provision

# 10. Reaper: drop leases whose lifetime has elapsed, and record the run.
cat > /usr/local/sbin/dhcpd-reap <<'REAP'
#!/bin/bash
set -euo pipefail
. /usr/local/lib/dhcpd/common.sh
NOW="${DHCPD_NOW_MS:-$(( $(date +%s) * 1000 ))}"
sqlite3 "$DB" "DELETE FROM leases WHERE state='active' AND expires_ms <= ${NOW};"
printf '%s reap db=%s now_ms=%s\n' "$(date -u +%FT%TZ)" "$DB" "$NOW" >> "$LOGDIR/reap.log" 2>/dev/null || true
REAP
chmod 0755 /usr/local/sbin/dhcpd-reap

# 11. Backup: a private snapshot with a companion checksum, retained to KEEP.
cat > /usr/local/sbin/dhcpd-backup <<'BACKUP'
#!/bin/bash
set -euo pipefail
. /usr/local/lib/dhcpd/common.sh
install -d -m 0700 "$BACKUPDIR"
ts="$(date +%s%N)"; out="$BACKUPDIR/dhcp-$ts.sql"
while [ -e "$out" ] || [ -e "$out.sha256" ]; do ts=$((ts + 1)); out="$BACKUPDIR/dhcp-$ts.sql"; done
( umask 077; sqlite3 "$DB" ".dump" > "$out" ); chmod 0600 "$out"
sha256sum "$out" | awk '{print $1}' > "$out.sha256"; chmod 0600 "$out.sha256"
ls -1t "$BACKUPDIR"/dhcp-*.sql 2>/dev/null | tail -n +"$((KEEP+1))" | while IFS= read -r old; do
    rm -f "$old" "$old.sha256"
done
admin_audit dhcpd-backup "out=$out"
echo "$out"
BACKUP
chmod 0755 /usr/local/sbin/dhcpd-backup

# 12. Restore: verify the checksum, snapshot the current DB for safety, then rebuild.
cat > /usr/local/sbin/dhcpd-restore <<'RESTORE'
#!/bin/bash
set -euo pipefail
. /usr/local/lib/dhcpd/common.sh
SRC="${1:?usage: dhcpd-restore <backup.sql>}"
[ -f "$SRC" ] || { echo "backup not found: $SRC" >&2; exit 1; }
if [ -f "$SRC.sha256" ]; then
    got="$(sha256sum "$SRC" | awk '{print $1}')"
    [ "$got" = "$(cat "$SRC.sha256")" ] || { admin_audit dhcpd-restore "REFUSED checksum src=$SRC"; echo "checksum mismatch for $SRC" >&2; exit 2; }
fi
# pre-restore safety snapshot of the current live database
if [ -f "$DB" ]; then
    install -d -m 0700 "$BACKUPDIR"
    safe="$BACKUPDIR/pre-restore-$(date +%s%N).sql"
    ( umask 077; sqlite3 "$DB" ".dump" > "$safe" ) 2>/dev/null || true
    if [ -f "$safe" ]; then
        chmod 0600 "$safe"
        sha256sum "$safe" | awk '{print $1}' > "$safe.sha256"; chmod 0600 "$safe.sha256"
    fi
fi
tmp="${DB}.restore.$$"
rm -f "$tmp" "$tmp-wal" "$tmp-shm"
sqlite3 "$tmp" < "$SRC"
mv -f "$tmp" "$DB"; rm -f "$DB-wal" "$DB-shm"
sqlite3 "$DB" "PRAGMA journal_mode=WAL;" >/dev/null 2>&1 || true
admin_audit dhcpd-restore "src=$SRC safe=${safe:-none}"
RESTORE
chmod 0755 /usr/local/sbin/dhcpd-restore

# 13. Report: per-pool utilisation, one JSON object per pool.
cat > /usr/local/sbin/dhcpd-report <<'REPORT'
#!/bin/bash
set -euo pipefail
. /usr/local/lib/dhcpd/common.sh
NOW="${DHCPD_NOW_MS:-$(( $(date +%s) * 1000 ))}"
tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
while IFS='|' read -r pid cidr; do
    [ -z "$pid" ] && continue
    printf '{"op":"status","pool_id":%d,"now_ms":%d}' "$pid" "$NOW" > "$tmp"
    st="$(DHCPD_DB="$DB" "$DAEMON" "$tmp")"
    total="$(printf '%s' "$st" | jq -r '.total')"; active="$(printf '%s' "$st" | jq -r '.active')"
    avail="$(printf '%s' "$st" | jq -r '.available')"
    util=0; [ "$total" -gt 0 ] && util=$(( active * 100 / total ))
    printf '{"pool_id":%d,"cidr":"%s","total":%d,"active":%d,"available":%d,"utilization":%d}\n' \
        "$pid" "$cidr" "$total" "$active" "$avail" "$util"
done < <(sqlite3 "$DB" "SELECT id||'|'||cidr FROM pools ORDER BY id;")
REPORT
chmod 0755 /usr/local/sbin/dhcpd-report

# 13a. Renumber: move a pool to a new CIDR in one transaction, re-homing its
#      reservations, leases, and declines by their offset from the network
#      address and dropping any that no longer fit; refuse an overlap.
cat > /usr/local/sbin/dhcpd-renumber <<'RENUM'
#!/bin/bash
set -uo pipefail
. /usr/local/lib/dhcpd/common.sh
OLD="${1:?usage: dhcpd-renumber <old_cidr> <new_cidr>}"
NEW="${2:?usage: dhcpd-renumber <old_cidr> <new_cidr>}"
valid_cidr "$OLD" || { echo "invalid old cidr: $OLD" >&2; exit 2; }
valid_cidr "$NEW" || { echo "invalid new cidr: $NEW" >&2; exit 2; }
row="$(sqlite3 "$DB" "SELECT id||'|'||network||'|'||broadcast FROM pools WHERE cidr='$OLD';")"
[ -n "$row" ] || { echo "no such pool: $OLD" >&2; exit 3; }
IFS='|' read -r pid old_net old_bcast <<<"$row"
read -r new_net new_bcast <<<"$(cidr_lo_hi "$NEW")"
new_prefix="${NEW#*/}"
if [ "$NEW" != "$OLD" ]; then
    while IFS='|' read -r c n b; do
        [ -n "$c" ] || continue
        [ "$c" = "$OLD" ] && continue
        if overlaps "$new_net" "$new_bcast" "$n" "$b"; then
            echo "new range $NEW overlaps pool $c; refusing" >&2; exit 1
        fi
    done < <(sqlite3 "$DB" "SELECT cidr||'|'||network||'|'||broadcast FROM pools;")
fi
install -d -m 0750 "$RUNDIR" 2>/dev/null || true
exec 9>"$RUNDIR/provision.lock" 2>/dev/null || true
flock 9 2>/dev/null || true
usable() { [ "$1" -gt "$new_net" ] && [ "$1" -lt "$new_bcast" ]; }
esc() { printf '%s' "$1" | sed "s/'/''/g"; }
resv_sql=""; lease_sql=""; decl_sql=""
while IFS='|' read -r ip cid; do
    [ -n "$ip" ] || continue
    nip=$(( new_net + (ip - old_net) )); usable "$nip" || continue
    resv_sql+="INSERT INTO reservations(pool_id,ip,client_id) VALUES($pid,$nip,'$(esc "$cid")');"
done < <(sqlite3 "$DB" "SELECT ip||'|'||client_id FROM reservations WHERE pool_id=$pid;")
while IFS='|' read -r ip cid exp cms st; do
    [ -n "$ip" ] || continue
    nip=$(( new_net + (ip - old_net) )); usable "$nip" || continue
    lease_sql+="INSERT INTO leases(ip,pool_id,client_id,expires_ms,created_ms,state) VALUES($nip,$pid,'$(esc "$cid")',$exp,$cms,'$(esc "$st")');"
done < <(sqlite3 "$DB" "SELECT ip||'|'||client_id||'|'||expires_ms||'|'||created_ms||'|'||state FROM leases WHERE pool_id=$pid;")
while IFS='|' read -r ip; do
    [ -n "$ip" ] || continue
    nip=$(( new_net + (ip - old_net) )); usable "$nip" || continue
    decl_sql+="INSERT INTO declines(ip,pool_id) VALUES($nip,$pid);"
done < <(sqlite3 "$DB" "SELECT ip FROM declines WHERE pool_id=$pid;")
sqlite3 "$DB" "BEGIN;
DELETE FROM reservations WHERE pool_id=$pid;
DELETE FROM leases WHERE pool_id=$pid;
DELETE FROM declines WHERE pool_id=$pid;
UPDATE pools SET cidr='$NEW', network=$new_net, broadcast=$new_bcast, prefix=$new_prefix WHERE id=$pid;
$resv_sql
$lease_sql
$decl_sql
COMMIT;" || { echo "renumber failed" >&2; exit 4; }
admin_audit dhcpd-renumber "pid=$pid old=$OLD new=$NEW db=$DB"
echo "renumbered $OLD -> $NEW"
RENUM
chmod 0755 /usr/local/sbin/dhcpd-renumber

# 13b. Audit: reconcile the live tables against the pool ranges and reservations,
#      one JSON object per pool plus an orphan/total summary; --strict fails on any.
cat > /usr/local/sbin/dhcpd-audit <<'AUDIT'
#!/bin/bash
set -uo pipefail
. /usr/local/lib/dhcpd/common.sh
STRICT=0; [ "${1:-}" = "--strict" ] && STRICT=1
total=0
while IFS='|' read -r pid cidr net bcast; do
    [ -n "$pid" ] || continue
    loor=$(sqlite3 "$DB" "SELECT COUNT(*) FROM leases WHERE pool_id=$pid AND (ip<=$net OR ip>=$bcast);")
    lexc=$(sqlite3 "$DB" "SELECT COUNT(*) FROM leases WHERE pool_id=$pid AND ip IN (SELECT ip FROM reservations WHERE pool_id=$pid AND client_id='');")
    ldec=$(sqlite3 "$DB" "SELECT COUNT(*) FROM leases WHERE pool_id=$pid AND ip IN (SELECT ip FROM declines WHERE pool_id=$pid);")
    lwrong=$(sqlite3 "$DB" "SELECT COUNT(*) FROM leases l JOIN reservations r ON r.pool_id=$pid AND r.ip=l.ip AND r.client_id<>'' WHERE l.pool_id=$pid AND l.client_id<>r.client_id;")
    roor=$(sqlite3 "$DB" "SELECT COUNT(*) FROM reservations WHERE pool_id=$pid AND (ip<=$net OR ip>=$bcast);")
    total=$(( total + loor + lexc + ldec + lwrong + roor ))
    printf '{"pool_id":%d,"cidr":"%s","lease_out_of_range":%d,"lease_on_exclusion":%d,"lease_on_decline":%d,"lease_wrong_client":%d,"resv_out_of_range":%d}\n' \
        "$pid" "$cidr" "$loor" "$lexc" "$ldec" "$lwrong" "$roor"
done < <(sqlite3 "$DB" "SELECT id||'|'||cidr||'|'||network||'|'||broadcast FROM pools ORDER BY id;")
orphl=$(sqlite3 "$DB" "SELECT COUNT(*) FROM leases WHERE pool_id NOT IN (SELECT id FROM pools);")
orphr=$(sqlite3 "$DB" "SELECT COUNT(*) FROM reservations WHERE pool_id NOT IN (SELECT id FROM pools);")
total=$(( total + orphl + orphr ))
printf '{"orphan_leases":%d,"orphan_reservations":%d,"inconsistencies":%d}\n' "$orphl" "$orphr" "$total"
[ "$STRICT" -eq 1 ] && [ "$total" -gt 0 ] && exit 1
exit 0
AUDIT
chmod 0755 /usr/local/sbin/dhcpd-audit

# 13c. Verify: a canonical, HMAC-signed manifest of the live database state,
#      so a deployment's state can be attested and compared byte for byte.
cat > /usr/local/sbin/dhcpd-verify <<'VERIFY'
#!/bin/bash
set -uo pipefail
. /usr/local/lib/dhcpd/common.sh
[ -f "$DB" ] || { echo "no database at $DB" >&2; exit 1; }
KEYHEX="$(printf '%s' 'dhcpd-verify-v1' | sha256sum | awk '{print $1}')"
tmp="$(mktemp)"; trap 'rm -f "$tmp"' EXIT
{
    sqlite3 "$DB" "SELECT 'POOL '||cidr||' '||lease_secs FROM pools ORDER BY network;"
    sqlite3 "$DB" "SELECT 'RESV '||p.cidr||' '||r.ip||' '||CASE WHEN r.client_id='' THEN '-' ELSE r.client_id END FROM reservations r JOIN pools p ON p.id=r.pool_id ORDER BY p.network, r.ip, r.client_id;"
    sqlite3 "$DB" "SELECT 'LEASE '||p.cidr||' '||l.ip||' '||l.client_id||' '||l.expires_ms||' '||l.state FROM leases l JOIN pools p ON p.id=l.pool_id ORDER BY p.network, l.ip;"
    sqlite3 "$DB" "SELECT 'DECLINE '||p.cidr||' '||d.ip FROM declines d JOIN pools p ON p.id=d.pool_id ORDER BY p.network, d.ip;"
} > "$tmp"
tag="$(openssl dgst -sha256 -mac HMAC -macopt hexkey:"$KEYHEX" "$tmp" | awk '{print $NF}')"
cat "$tmp"
echo "TAG $tag"
VERIFY
chmod 0755 /usr/local/sbin/dhcpd-verify

# 14. Initialise the state database in WAL mode; create the admin audit log.
sqlite3 /var/lib/dhcpd/dhcp.db < /opt/dhcpd/share/schema.sql >/dev/null
sqlite3 /var/lib/dhcpd/dhcp.db "PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;" >/dev/null
: > /var/log/dhcpd/admin.log

# 15. Pool definitions: site LAN, guest (/22 -> 1022 usable), and VoIP.
cat > /etc/dhcpd/pools.d/lan.json <<'POOL'
{"op":"create_pool","cidr":"10.10.0.0/24","lease_secs":3600,"reserved":["10.10.0.1",{"ip":"10.10.0.10","client_id":"printer"}]}
POOL
cat > /etc/dhcpd/pools.d/guest.json <<'POOL'
{"op":"create_pool","cidr":"10.20.0.0/22","lease_secs":600,"reserved":["10.20.0.1"]}
POOL
cat > /etc/dhcpd/pools.d/voip.json <<'POOL'
{"op":"create_pool","cidr":"10.30.0.0/24","lease_secs":86400,"reserved":["10.30.0.1",{"ip":"10.30.0.5","client_id":"pbx"}]}
POOL
DHCPD_DB=/var/lib/dhcpd/dhcp.db /usr/local/sbin/dhcpd-provision

# 16. Restrict and hand the whole state tree to the service account (no world access).
chown -R dhcpd:dhcpd /var/lib/dhcpd /var/log/dhcpd
chmod 0640 /var/lib/dhcpd/dhcp.db
chmod 0700 /var/lib/dhcpd/backups
chmod 0640 /var/log/dhcpd/admin.log
find /var/lib/dhcpd -exec chmod o-rwx {} + 2>/dev/null || true

# 17. Log rotation for the service logs, rotated as the service account.
cat > /etc/logrotate.d/dhcpd <<'LR'
/var/log/dhcpd/*.log {
    daily
    rotate 14
    missingok
    notifempty
    compress
    delaycompress
    su dhcpd dhcpd
    create 0640 dhcpd dhcpd
}
LR
chmod 0644 /etc/logrotate.d/dhcpd

# 18. Schedule maintenance from cron, as the service account.
cat > /etc/cron.d/dhcpd <<'CRON'
# DHCP appliance maintenance, run as the unprivileged service account.
*/5  * * * * dhcpd /usr/local/sbin/dhcpd-reap
17   3 * * * dhcpd /usr/local/sbin/dhcpd-backup
*/15 * * * * dhcpd /usr/local/sbin/dhcpd-report >> /var/log/dhcpd/utilization.log 2>&1
*/10 * * * * dhcpd /usr/local/sbin/dhcpd-provision --check >> /var/log/dhcpd/drift.log 2>&1
CRON
chmod 0644 /etc/cron.d/dhcpd

# 19. Operator delegation: members of dhcpdops may run only the read-only
#     maintenance commands, and only as the service account, without a password.
cat > /etc/sudoers.d/dhcpd <<'SUDO'
# DHCP operators (group dhcpdops) may run only the read-only maintenance
# commands as the dhcpd service account. Nothing else is delegated; the
# state-changing commands (backup, restore, reap, renumber, and an
# unqualified provision) are deliberately excluded.
%dhcpdops ALL=(dhcpd) NOPASSWD: /usr/local/sbin/dhcpd-report, /usr/local/sbin/dhcpd-verify, /usr/local/sbin/dhcpd-audit, /usr/local/sbin/dhcpd-fsck, /usr/local/sbin/dhcpd-check, /usr/local/sbin/dhcpd-provision --check
SUDO
chmod 0440 /etc/sudoers.d/dhcpd
visudo -cf /etc/sudoers.d/dhcpd >/dev/null

echo "DHCP lease service provisioned"
