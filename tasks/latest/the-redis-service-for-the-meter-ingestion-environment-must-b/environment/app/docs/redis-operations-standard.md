# Meter Redis Operations Standard

Status: approved for production after amendment OPS-17. This document is the controlling source for service configuration, access policy, publication fields, and post-migration verification. Earlier examples in tickets and migration comments are non-normative.

## Service identity and endpoint

The meter store runs as one local Redis process. Its published endpoint identifier is `redis://127.0.0.1:6380/0`; TCP must bind only to `127.0.0.1`, protected mode must remain enabled, and database 0 is the only approved logical database. Attempts to select any other logical database must be rejected by the live service. The process is daemonized with PID file `/app/runtime/redis-meter.pid` and log file `/var/log/redis-meter/redis.log`.

## Authentication and ACL state

The default principal is disabled. Credentials are provisioned in `/app/secrets/redis-credentials.ini`; they must not be copied into the receipt. The migration principal is named `meter_ingest`. It may write only keys matching `meter:*` and may use only the data commands needed by the supplied importer. After a successful load it is disabled. The read-only principal is `meter_audit`; it may authenticate, ping, select database 0, enumerate only the `meter:*` namespace, count keys in the approved database, test key existence, read strings, hashes, sets, sorted sets, and lists, inspect key TTLs, and read server status through INFO. It must not read keys outside `meter:*`, write data, or administer the server. The enabled audit principal must require its configured password; broad ACL categories are acceptable only when the resulting live permissions remain within this role.

The following commands are globally unavailable and must be absent from the live command table: `CONFIG`, `DEBUG`, `EVAL`, `EVALSHA`, `FLUSHALL`, `FLUSHDB`, `FUNCTION`, `MODULE`, `SCRIPT`, and `SHUTDOWN`. Unauthenticated commands other than the protocol-level authentication exchange must be rejected.

## Persistence and filesystem controls

The persistence root is `/var/lib/redis-meter`, owned by the Redis runtime user and not accessible to group or other users. The required database filename is `meter.rdb`. AOF persistence is enabled with append-only directory name `appendonly-meter`, fsync policy `everysec`, and RDB snapshots `900 1`, `300 10`, and `60 10000`. The memory ceiling is `96mb` with `noeviction` behavior.

## Fixture package and normalized keyspace

The approved dataset identifier is `redis-hardened-meter-fixtures/2026-07-14`. The local package `/app/input/redis-hardened-meter-fixtures.tar.gz` is the offline mirror of the originally published object. The supplied PHP utility is authoritative for parsing the package. It creates one hash per meter (`meter:device:<id>`), the set `meter:index`, the sorted set `meter:ranking:kwh`, the hash `meter:tariffs`, and the list `meter:events`.

For publication, meter hashes are ordered by meter ID. The canonical keyspace checksum is calculated from the live server, not from the archive: enumerate all `meter:*` keys in bytewise ascending order; for each key append the UTF-8 key name, one NUL byte, the Redis type, one NUL byte, and the canonical value bytes. String values are raw bytes. Hashes use field names in bytewise order and append `field`, NUL, `value`, NUL. Sets use members in bytewise order, each followed by NUL. Sorted sets use member names in bytewise order and append `member`, NUL, the score rendered by Redis without surrounding whitespace, NUL. Lists use element order with each element followed by NUL. Feed the concatenation into SHA-256 and publish lowercase hexadecimal.

## Migration receipt contract

The receipt schema identifier is `meter-redis-migration/v2`. `redis_endpoint` is the approved endpoint identifier above. `dataset` contains `identifier`, `archive_sha256`, and `source_files`; source files are listed in bytewise ascending order. `keyspace` contains `database`, `total_keys`, `meter_count`, `event_count`, and `canonical_sha256`. `security` contains `default_user_disabled`, `ingest_user_disabled`, `audit_user`, `blocked_commands`, `bind`, `protected_mode`, and `maxmemory_policy`. `persistence` contains `dir`, `dbfilename`, `appendonly`, `appenddirname`, `appendfsync`, and `save_rules`. Boolean values are JSON booleans. `blocked_commands` and `save_rules` use the order shown in this document.
