#!/bin/bash
set -euo pipefail

CONF=/app/config/redis.conf
ACL=/app/config/users.acl
CREDS=/app/secrets/redis-credentials.ini
ARCHIVE=/app/input/redis-hardened-meter-fixtures.tar.gz

INGEST_USER=$(php -r '$x=parse_ini_file($argv[1],true); echo $x["ingest"]["username"];' "$CREDS")
INGEST_PASS=$(php -r '$x=parse_ini_file($argv[1],true); echo $x["ingest"]["password"];' "$CREDS")
AUDIT_USER=$(php -r '$x=parse_ini_file($argv[1],true); echo $x["audit"]["username"];' "$CREDS")
AUDIT_PASS=$(php -r '$x=parse_ini_file($argv[1],true); echo $x["audit"]["password"];' "$CREDS")

install -d -m 0700 -o redis -g redis /var/lib/redis-meter /var/log/redis-meter
install -d -m 0750 -o redis -g redis /app/runtime
cat > "$ACL" <<EOF_ACL
user default off
user $INGEST_USER on >$INGEST_PASS ~meter:* &* +ping +select +hset +hmset +sadd +zadd +rpush +save
user $AUDIT_USER on >$AUDIT_PASS ~meter:* &* +ping +select +get +mget +hget +hmget +hgetall +hkeys +scard +smembers +zcard +zrange +zscore +llen +lrange +type +exists +ttl +pttl +dbsize +scan +info
EOF_ACL
chown redis:redis "$ACL"
chmod 0600 "$ACL"

cat > "$CONF" <<EOF_CONF
bind 127.0.0.1
protected-mode yes
port 6380
tcp-backlog 128
timeout 0
tcp-keepalive 300
daemonize yes
supervised no
pidfile /app/runtime/redis-meter.pid
loglevel notice
logfile /var/log/redis-meter/redis.log
databases 1
aclfile $ACL
dir /var/lib/redis-meter
dbfilename meter.rdb
appendonly yes
appenddirname appendonly-meter
appendfsync everysec
save 900 1
save 300 10
save 60 10000
maxmemory 96mb
maxmemory-policy noeviction
rename-command CONFIG ""
rename-command DEBUG ""
rename-command EVAL ""
rename-command EVALSHA ""
rename-command FLUSHALL ""
rename-command FLUSHDB ""
rename-command FUNCTION ""
rename-command MODULE ""
rename-command SCRIPT ""
rename-command SHUTDOWN ""
EOF_CONF

rm -f /app/runtime/redis-meter.pid
runuser -u redis -- redis-server "$CONF"
for _ in $(seq 1 50); do
    if redis-cli -h 127.0.0.1 -p 6380 --user "$INGEST_USER" --pass "$INGEST_PASS" --no-auth-warning ping >/dev/null 2>&1; then
        break
    fi
    sleep 0.1
done

php /app/bin/import-fixtures.php "$ARCHIVE" 127.0.0.1 6380 "$CREDS"
PID=$(cat /app/runtime/redis-meter.pid)
kill "$PID"
for _ in $(seq 1 50); do
    if ! kill -0 "$PID" 2>/dev/null; then
        break
    fi
    sleep 0.1
done
sed -i "s/^user $INGEST_USER on /user $INGEST_USER off /" "$ACL"
runuser -u redis -- redis-server "$CONF"
for _ in $(seq 1 50); do
    if redis-cli -h 127.0.0.1 -p 6380 --user "$AUDIT_USER" --pass "$AUDIT_PASS" --no-auth-warning ping >/dev/null 2>&1; then
        break
    fi
    sleep 0.1
done

python3 - <<'PY'
import hashlib
import json
import subprocess
from pathlib import Path

HOST = "127.0.0.1"
PORT = "6380"
CREDS = Path("/app/secrets/redis-credentials.ini").read_text()

def ini_value(section: str, key: str) -> str:
    active = None
    for line in CREDS.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            active = line[1:-1]
        elif active == section and line.startswith(key + " "):
            return line.split("=", 1)[1].strip().strip('"')
    raise KeyError((section, key))

USER = ini_value("audit", "username")
PASSWORD = ini_value("audit", "password")

def cli(*args: str) -> bytes:
    cmd = ["redis-cli", "-h", HOST, "-p", PORT, "--user", USER, "--pass", PASSWORD, "--no-auth-warning", "--raw", *args]
    return subprocess.check_output(cmd)

def lines(*args: str) -> list[bytes]:
    out = cli(*args)
    return out.splitlines()

keys = sorted(lines("--scan", "--pattern", "meter:*"))
blob = bytearray()
for key_b in keys:
    key = key_b.decode()
    typ = cli("TYPE", key).strip().decode()
    blob += key_b + b"\0" + typ.encode() + b"\0"
    if typ == "string":
        blob += cli("GET", key).rstrip(b"\n")
    elif typ == "hash":
        fields = lines("HKEYS", key)
        for field in sorted(fields):
            value = cli("HGET", key, field.decode()).rstrip(b"\n")
            blob += field + b"\0" + value + b"\0"
    elif typ == "set":
        for member in sorted(lines("SMEMBERS", key)):
            blob += member + b"\0"
    elif typ == "zset":
        members = lines("ZRANGE", key, "0", "-1")
        for member in sorted(members):
            score = cli("ZSCORE", key, member.decode()).strip()
            blob += member + b"\0" + score + b"\0"
    elif typ == "list":
        for item in lines("LRANGE", key, "0", "-1"):
            blob += item + b"\0"
    else:
        raise RuntimeError(typ)

archive = Path("/app/input/redis-hardened-meter-fixtures.tar.gz")
policy = {
    "dataset": {
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "identifier": "redis-hardened-meter-fixtures/2026-07-14",
        "source_files": ["events.log", "meters.json", "tariffs.ini"],
    },
    "keyspace": {
        "canonical_sha256": hashlib.sha256(blob).hexdigest(),
        "database": 0,
        "event_count": int(cli("LLEN", "meter:events").strip()),
        "meter_count": int(cli("SCARD", "meter:index").strip()),
        "total_keys": int(cli("DBSIZE").strip()),
    },
    "persistence": {
        "appenddirname": "appendonly-meter",
        "appendfsync": "everysec",
        "appendonly": True,
        "dbfilename": "meter.rdb",
        "dir": "/var/lib/redis-meter",
        "save_rules": ["900 1", "300 10", "60 10000"],
    },
    "redis_endpoint": "redis://127.0.0.1:6380/0",
    "schema_version": "meter-redis-migration/v2",
    "security": {
        "audit_user": USER,
        "bind": ["127.0.0.1"],
        "blocked_commands": ["CONFIG", "DEBUG", "EVAL", "EVALSHA", "FLUSHALL", "FLUSHDB", "FUNCTION", "MODULE", "SCRIPT", "SHUTDOWN"],
        "default_user_disabled": True,
        "ingest_user_disabled": True,
        "maxmemory_policy": "noeviction",
        "protected_mode": True,
    },
}
Path("/app/output").mkdir(parents=True, exist_ok=True)
raw = (json.dumps(policy, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
Path("/app/output/migration-receipt.json").write_bytes(raw)
Path("/app/output/migration-receipt.sha256").write_text(hashlib.sha256(raw).hexdigest() + "\n")
PY
