"""Behavioral verification for the hardened Redis migration task."""

from __future__ import annotations

import configparser
import grp
import hashlib
import json
import pwd
import shlex
import stat
import subprocess
from pathlib import Path

import pytest

OUTPUT = Path("/app/output/migration-receipt.json")
DIGEST = Path("/app/output/migration-receipt.sha256")
ARCHIVE = Path("/app/input/redis-hardened-meter-fixtures.tar.gz")
STANDARD = Path("/app/docs/redis-operations-standard.md")
IMPORTER = Path("/app/bin/import-fixtures.php")
CREDS = Path("/app/secrets/redis-credentials.ini")
EXPECTED_PIDFILE = Path("/app/runtime/redis-meter.pid")
EXPECTED_LOGFILE = Path("/var/log/redis-meter/redis.log")
EXPECTED_DIR = Path("/var/lib/redis-meter")
AUDIT_USER = "meter_audit"
INGEST_USER = "meter_ingest"
BLOCKED_COMMANDS = [
    "CONFIG",
    "DEBUG",
    "EVAL",
    "EVALSHA",
    "FLUSHALL",
    "FLUSHDB",
    "FUNCTION",
    "MODULE",
    "SCRIPT",
    "SHUTDOWN",
]

SOURCE_HASHES = {
    ARCHIVE: "eda55df22b97c861120292004e6f68533a9b864fffa797e68ad0d44b3dfb4921",
    STANDARD: "1a8cc5af50749a8d9f26a51847d27454a98c0aa3ee0d0cc5ffccb1e67a885488",
    IMPORTER: "137438dea331b45679f529ad001faff3944b7335173fbac99c421740aee8d6df",
    CREDS: "da23bbaa4ca6fd99041f84ba27baf8899e27d189493b75ee260a5802873f4a1e",
}


def credentials() -> configparser.ConfigParser:
    """Load immutable credentials used to exercise the live Redis service."""
    parser = configparser.ConfigParser()
    parser.read(CREDS)
    assert parser["audit"]["username"] == AUDIT_USER
    assert parser["ingest"]["username"] == INGEST_USER
    return parser


def redis_cli(
    *args: str,
    user: str | None = None,
    password: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run redis-cli against the approved endpoint with optional ACL credentials."""
    command = ["redis-cli", "-h", "127.0.0.1", "-p", "6380", "--raw"]
    if user is not None:
        command.extend(["--user", user])
    if password is not None:
        command.extend(["--pass", password, "--no-auth-warning"])
    command.extend(args)
    return subprocess.run(command, text=True, capture_output=True, check=check)


def audit() -> tuple[str, str]:
    """Return the immutable read-only ACL principal."""
    cfg = credentials()
    return AUDIT_USER, cfg["audit"]["password"]


def load_receipt() -> dict:
    """Load the published migration receipt as JSON."""
    return json.loads(OUTPUT.read_text(encoding="utf-8"))


def info(section: str) -> dict[str, str]:
    """Return a parsed Redis INFO section from the live process."""
    user, password = audit()
    result = redis_cli("INFO", section, user=user, password=password).stdout
    parsed: dict[str, str] = {}
    for line in result.splitlines():
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key] = value
    return parsed


def live_process_id() -> int:
    """Return the Redis process ID reported by the live endpoint."""
    pid = int(info("server")["process_id"])
    assert EXPECTED_PIDFILE.read_text(encoding="utf-8").strip() == str(pid)
    assert Path(f"/proc/{pid}").is_dir()
    return pid


def active_config_path() -> Path:
    """Resolve the configuration file reported by the live Redis process."""
    server = info("server")
    reported = server.get("config_file", "").strip()
    if reported:
        config = Path(reported)
        assert config.is_absolute(), reported
        assert config.is_file(), reported
        return config

    # Redis rewrites its process title after startup, so /proc/<pid>/cmdline may
    # no longer retain the original config argument. Keep a narrow fallback for
    # builds that do preserve it, but do not require that implementation detail.
    pid = live_process_id()
    cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    candidates = [Path(item.decode()) for item in cmdline if item.endswith(b".conf")]
    assert len(candidates) == 1, (reported, cmdline)
    config = candidates[0]
    assert config.is_file()
    return config


def parse_redis_config(path: Path) -> dict[str, list[list[str]]]:
    """Parse active Redis directives while preserving repeated settings."""
    directives: dict[str, list[list[str]]] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = shlex.split(stripped, comments=True, posix=True)
        if not parts:
            continue
        directives.setdefault(parts[0].lower(), []).append(parts[1:])
    return directives


def one(config: dict[str, list[list[str]]], name: str) -> list[str]:
    """Return the single value of an active Redis directive."""
    values = config.get(name)
    assert values is not None and len(values) == 1, (name, values)
    return values[0]


def active_acl_path() -> Path:
    """Resolve the ACL file referenced by the active Redis configuration."""
    path = Path(one(parse_redis_config(active_config_path()), "aclfile")[0])
    assert path.is_absolute()
    assert path.is_file()
    return path


def parse_acl(path: Path) -> dict[str, list[str]]:
    """Parse the active ACL file into one token list per exact principal."""
    users: dict[str, list[str]] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = shlex.split(stripped, comments=True, posix=True)
        assert len(parts) >= 3 and parts[0] == "user"
        assert parts[1] not in users
        users[parts[1]] = parts[2:]
    return users


def canonical_keyspace_checksum(user: str, password: str) -> str:
    """Recompute the standard's canonical checksum from the live Redis keyspace."""
    scan = redis_cli("--scan", "--pattern", "meter:*", user=user, password=password).stdout.splitlines()
    blob = bytearray()
    for key in sorted(scan):
        kind = redis_cli("TYPE", key, user=user, password=password).stdout.strip()
        blob.extend(key.encode() + b"\0" + kind.encode() + b"\0")
        if kind == "hash":
            fields = redis_cli("HKEYS", key, user=user, password=password).stdout.splitlines()
            for field in sorted(fields):
                value = redis_cli("HGET", key, field, user=user, password=password).stdout.rstrip("\n")
                blob.extend(field.encode() + b"\0" + value.encode() + b"\0")
        elif kind == "set":
            members = redis_cli("SMEMBERS", key, user=user, password=password).stdout.splitlines()
            for member in sorted(members):
                blob.extend(member.encode() + b"\0")
        elif kind == "zset":
            members = redis_cli("ZRANGE", key, "0", "-1", user=user, password=password).stdout.splitlines()
            for member in sorted(members):
                score = redis_cli("ZSCORE", key, member, user=user, password=password).stdout.strip()
                blob.extend(member.encode() + b"\0" + score.encode() + b"\0")
        elif kind == "list":
            items = redis_cli("LRANGE", key, "0", "-1", user=user, password=password).stdout.splitlines()
            for item in items:
                blob.extend(item.encode() + b"\0")
        elif kind == "string":
            value = redis_cli("GET", key, user=user, password=password).stdout.rstrip("\n")
            blob.extend(value.encode())
        else:
            raise AssertionError(f"unexpected Redis type: {kind}")
    return hashlib.sha256(blob).hexdigest()


def test_required_artifacts_and_exact_output_scope() -> None:
    """Verify that only the two required publication artifacts exist in the output directory."""
    assert OUTPUT.is_file()
    assert DIGEST.is_file()
    assert sorted(path.name for path in OUTPUT.parent.iterdir()) == [
        "migration-receipt.json",
        "migration-receipt.sha256",
    ]


def test_receipt_serialization_and_digest() -> None:
    """Verify canonical JSON formatting and the digest of the exact published bytes."""
    raw = OUTPUT.read_bytes()
    policy = json.loads(raw)
    expected = (json.dumps(policy, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
    assert raw == expected
    assert DIGEST.read_text() == hashlib.sha256(raw).hexdigest() + "\n"


def test_live_endpoint_and_process_identity() -> None:
    """Verify the approved endpoint is live, unauthenticated access is rejected, and the expected process owns it."""
    unauthenticated = redis_cli("PING", check=False)
    assert unauthenticated.returncode != 0 or "NOAUTH" in unauthenticated.stderr + unauthenticated.stdout

    pid = live_process_id()
    cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    assert any("redis-server" in part.decode(errors="replace") for part in cmdline if part)
    server = info("server")
    assert server["tcp_port"] == "6380"
    assert active_config_path().resolve() == Path(server["config_file"]).resolve()

    status = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    uid_line = next(line for line in status.splitlines() if line.startswith("Uid:"))
    gid_line = next(line for line in status.splitlines() if line.startswith("Gid:"))
    uid = int(uid_line.split()[1])
    gid = int(gid_line.split()[1])
    assert pwd.getpwuid(uid).pw_name == "redis"
    assert grp.getgrgid(gid).gr_name == "redis"
    assert EXPECTED_LOGFILE.is_file()


def test_active_configuration_matches_the_operations_standard() -> None:
    """Verify the live process was started with the exact network, persistence, memory, and command controls required by the standard."""
    config = parse_redis_config(active_config_path())
    assert one(config, "bind") == ["127.0.0.1"]
    assert one(config, "protected-mode") == ["yes"]
    assert one(config, "port") == ["6380"]
    assert one(config, "daemonize") == ["yes"]
    assert one(config, "pidfile") == [str(EXPECTED_PIDFILE)]
    assert one(config, "logfile") == [str(EXPECTED_LOGFILE)]
    assert one(config, "dir") == [str(EXPECTED_DIR)]
    assert one(config, "dbfilename") == ["meter.rdb"]
    assert one(config, "appendonly") == ["yes"]
    assert one(config, "appenddirname") == ["appendonly-meter"]
    assert one(config, "appendfsync") == ["everysec"]
    assert config.get("save") == [["900", "1"], ["300", "10"], ["60", "10000"]]
    assert one(config, "maxmemory") == ["96mb"]
    assert one(config, "maxmemory-policy") == ["noeviction"]

    renames = config.get("rename-command", [])
    assert {entry[0].upper(): entry[1:] for entry in renames} == {
        command: [""] for command in BLOCKED_COMMANDS
    }


def test_active_acl_has_only_the_approved_principals_and_rights() -> None:
    """Verify the active ACL exposes only approved principals and enforces their live roles."""
    users = parse_acl(active_acl_path())
    assert set(users) == {"default", INGEST_USER, AUDIT_USER}

    default = users["default"]
    ingest = users[INGEST_USER]
    audit_tokens = users[AUDIT_USER]
    assert "off" in default and "on" not in default
    assert "off" in ingest and "on" not in ingest
    assert "on" in audit_tokens and "off" not in audit_tokens and "nopass" not in audit_tokens

    acl_stat = active_acl_path().stat()
    assert stat.S_IMODE(acl_stat.st_mode) == 0o600
    assert pwd.getpwuid(acl_stat.st_uid).pw_name == "redis"
    assert grp.getgrgid(acl_stat.st_gid).gr_name == "redis"

    cfg = credentials()
    audit_password = cfg["audit"]["password"]
    assert redis_cli("PING", user=AUDIT_USER, password=audit_password).stdout.strip() == "PONG"
    missing_password = redis_cli("PING", user=AUDIT_USER, check=False)
    assert missing_password.returncode != 0 or "NOAUTH" in missing_password.stderr + missing_password.stdout
    wrong_password = redis_cli("PING", user=AUDIT_USER, password="definitely-wrong", check=False)
    assert wrong_password.returncode != 0 or "WRONGPASS" in wrong_password.stderr + wrong_password.stdout

    allowed_calls = [
        ("SELECT", "0"),
        ("TYPE", "meter:index"),
        ("EXISTS", "meter:index"),
        ("TTL", "meter:index"),
        ("PTTL", "meter:index"),
        ("DBSIZE",),
        ("SCAN", "0", "MATCH", "meter:*", "COUNT", "10"),
        ("GET", "meter:missing-string"),
        ("MGET", "meter:missing-string", "meter:missing-string-2"),
        ("HGET", "meter:device:MTR-001", "site"),
        ("HMGET", "meter:device:MTR-001", "site", "status"),
        ("HGETALL", "meter:device:MTR-001"),
        ("HKEYS", "meter:device:MTR-001"),
        ("SCARD", "meter:index"),
        ("SMEMBERS", "meter:index"),
        ("ZCARD", "meter:ranking:kwh"),
        ("ZRANGE", "meter:ranking:kwh", "0", "-1"),
        ("ZSCORE", "meter:ranking:kwh", "MTR-001"),
        ("LLEN", "meter:events"),
        ("LRANGE", "meter:events", "0", "0"),
        ("INFO", "server"),
    ]
    for call in allowed_calls:
        result = redis_cli(*call, user=AUDIT_USER, password=audit_password, check=False)
        assert result.returncode == 0 and "NOPERM" not in result.stderr + result.stdout, call

    denied_calls = [
        ("SELECT", "1"),
        ("GET", "outside:probe"),
        ("SET", "meter:probe", "x"),
        ("HSET", "meter:probe", "field", "x"),
        ("SADD", "meter:probe", "x"),
        ("ZADD", "meter:probe", "1", "x"),
        ("RPUSH", "meter:probe", "x"),
        ("DEL", "meter:probe"),
        ("EXPIRE", "meter:probe", "10"),
        ("SAVE",),
        ("BGSAVE",),
        ("BGREWRITEAOF",),
        ("ACL", "LIST"),
        ("CLIENT", "LIST"),
        ("COMMAND",),
        ("DUMP", "meter:index"),
        ("KEYS", "meter:*"),
        ("MIGRATE", "127.0.0.1", "1", "meter:index", "0", "1000"),
        ("RESTORE", "meter:probe", "0", "x"),
    ]
    for call in denied_calls:
        denied = redis_cli(*call, user=AUDIT_USER, password=audit_password, check=False)
        text = denied.stderr + denied.stdout
        if call == ("SELECT", "1"):
            assert "DB index is out of range" in text
        else:
            assert "NOPERM" in text, (call, text)

    ingest_login = redis_cli(
        "PING",
        user=INGEST_USER,
        password=cfg["ingest"]["password"],
        check=False,
    )
    assert ingest_login.returncode != 0 or "WRONGPASS" in ingest_login.stderr + ingest_login.stdout


@pytest.mark.parametrize("command", BLOCKED_COMMANDS)
def test_prohibited_commands_are_globally_unavailable(command: str) -> None:
    """Verify each prohibited administrative or scripting command is removed from the live command table."""
    user, password = audit()
    result = redis_cli(command, user=user, password=password, check=False)
    assert "unknown command" in (result.stderr + result.stdout).lower()


def test_receipt_contract_matches_live_security_state() -> None:
    """Verify the receipt contract agrees with independently observed live security controls."""
    policy = load_receipt()
    assert set(policy) == {"schema_version", "redis_endpoint", "dataset", "keyspace", "security", "persistence"}
    assert policy["schema_version"] == "meter-redis-migration/v2"
    assert policy["redis_endpoint"] == "redis://127.0.0.1:6380/0"
    assert policy["security"] == {
        "audit_user": AUDIT_USER,
        "bind": ["127.0.0.1"],
        "blocked_commands": BLOCKED_COMMANDS,
        "default_user_disabled": True,
        "ingest_user_disabled": True,
        "maxmemory_policy": "noeviction",
        "protected_mode": True,
    }


def test_dataset_and_live_keyspace_are_complete() -> None:
    """Verify dataset identity, fixture digest, counts, and canonical checksum against the live Redis data."""
    user, password = audit()
    policy = load_receipt()
    assert policy["dataset"] == {
        "archive_sha256": hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
        "identifier": "redis-hardened-meter-fixtures/2026-07-14",
        "source_files": ["events.log", "meters.json", "tariffs.ini"],
    }
    assert policy["keyspace"] == {
        "canonical_sha256": canonical_keyspace_checksum(user, password),
        "database": 0,
        "event_count": 5,
        "meter_count": 4,
        "total_keys": 8,
    }
    assert redis_cli("SCARD", "meter:index", user=user, password=password).stdout.strip() == "4"
    assert redis_cli("LLEN", "meter:events", user=user, password=password).stdout.strip() == "5"


def test_persistence_state_filesystem_and_permissions() -> None:
    """Verify persistence is active, owned by Redis, and backed by non-placeholder RDB and AOF files."""
    policy = load_receipt()
    assert policy["persistence"] == {
        "appenddirname": "appendonly-meter",
        "appendfsync": "everysec",
        "appendonly": True,
        "dbfilename": "meter.rdb",
        "dir": str(EXPECTED_DIR),
        "save_rules": ["900 1", "300 10", "60 10000"],
    }

    directory_stat = EXPECTED_DIR.stat()
    assert stat.S_IMODE(directory_stat.st_mode) == 0o700
    assert pwd.getpwuid(directory_stat.st_uid).pw_name == "redis"
    assert grp.getgrgid(directory_stat.st_gid).gr_name == "redis"

    persistence = info("persistence")
    memory = info("memory")
    assert persistence["aof_enabled"] == "1"
    assert persistence["rdb_last_bgsave_status"] == "ok"
    assert persistence["aof_last_bgrewrite_status"] == "ok"
    assert memory["maxmemory"] == str(96 * 1024 * 1024)
    assert memory["maxmemory_policy"] == "noeviction"

    rdb = EXPECTED_DIR / "meter.rdb"
    aof_dir = EXPECTED_DIR / "appendonly-meter"
    assert rdb.is_file() and rdb.stat().st_size > 16
    assert rdb.read_bytes().startswith(b"REDIS")
    assert aof_dir.is_dir()
    manifest = aof_dir / "appendonly.aof.manifest"
    assert manifest.is_file() and manifest.stat().st_size > 0
    aof_payloads = [path for path in aof_dir.iterdir() if path.is_file() and path.suffix == ".aof"]
    assert aof_payloads
    assert sum(path.stat().st_size for path in aof_payloads) > 0


def test_source_evidence_remains_immutable() -> None:
    """Verify the fixture archive, standard, importer, and credentials remain byte-for-byte unchanged."""
    for path, expected in SOURCE_HASHES.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
