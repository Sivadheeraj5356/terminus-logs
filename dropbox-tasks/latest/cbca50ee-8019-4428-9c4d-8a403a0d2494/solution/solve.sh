#!/bin/bash
set -euo pipefail

db_path="/app/ops/state/export_ledger.sqlite"

cat > /app/ops/state/export_state.json <<'JSON'
{
  "schema_version": 2,
  "service_unit": "rotlog-export.service",
  "status": "complete",
  "succeeded_after_partition": "part-0004",
  "high_water_cursor": "s=32;b=boot-b",
  "last_complete_event_seq": 6,
  "resume_generation": "gen-42/reload-1",
  "lineage": ["part-0001", "part-0002", "part-0004"],
  "omitted_partitions": ["part-0003"]
}
JSON

cat > /app/ops/manifests/bundle_manifest.json <<'JSON'
{
  "schema_version": 2,
  "bundle_id": "rot-bundle-2026-07-14",
  "service_unit": "rotlog-export.service",
  "reload_generation": "gen-42/reload-1",
  "partition_entries": [
    {
      "partition_id": "part-0001",
      "sequence": 1,
      "path": "logs/part-0001.journal",
      "status": "export",
      "cursor_start": "s=0;b=boot-a",
      "cursor_end": "s=8;b=boot-a",
      "prev_cursor": "",
      "digest_hex": "b9b20dc433b681eb0750cc75912139d0557992ac9124cd418497441927f0c37f"
    },
    {
      "partition_id": "part-0002",
      "sequence": 2,
      "path": "logs/part-0002.journal",
      "status": "export",
      "cursor_start": "s=9;b=boot-a",
      "cursor_end": "s=17;b=boot-a",
      "prev_cursor": "s=8;b=boot-a",
      "digest_hex": "5fa0d2d1697f7d694fead3f767e522720a072d7c69ccc982cc16ca2c35131e72"
    },
    {
      "partition_id": "part-0003",
      "sequence": 4,
      "path": "logs/part-0003.journal",
      "status": "omit",
      "cursor_start": "s=18;b=boot-b",
      "cursor_end": "s=25;b=boot-b",
      "prev_cursor": "s=17;b=boot-a",
      "digest_hex": "f0803159ce3e380fe0bc8c74f5fced935aa0be9d0eee81b86afc589bd52db8f5",
      "omission_reason": "rollback-superseded",
      "omission_digest_hex": "83baa1a8b9d2681f0f218cd90689b5a3e5f1f164444e9a4667f7bb0665225fae"
    },
    {
      "partition_id": "part-0004",
      "sequence": 6,
      "path": "logs/part-0004.journal",
      "status": "export",
      "cursor_start": "s=18;b=boot-b",
      "cursor_end": "s=32;b=boot-b",
      "prev_cursor": "s=17;b=boot-a",
      "digest_hex": "4122793617f506df194ea575b9af17b63f90c9d5a3aa458561ae42f0b1a07180"
    }
  ],
  "signer": {
    "key_id": "local-offline-ed25519",
    "signed_at": "2026-07-14T04:12:00Z",
    "lineage_hash_hex": "c5ea4458bf0f93f6aa52e7c9acd79751f1e111e872a99ecf7bd8311252c0734f"
  }
}
JSON

sqlite3 "$db_path" <<'SQL'
begin immediate;
delete from checkpoint;
insert into checkpoint values ('part-0001',1,'export','s=0;b=boot-a','s=8;b=boot-a','','b9b20dc433b681eb0750cc75912139d0557992ac9124cd418497441927f0c37f','','','gen-42/reload-1','batch-20260714',1);
insert into checkpoint values ('part-0002',2,'export','s=9;b=boot-a','s=17;b=boot-a','s=8;b=boot-a','5fa0d2d1697f7d694fead3f767e522720a072d7c69ccc982cc16ca2c35131e72','','','gen-42/reload-1','batch-20260714',1);
insert into checkpoint values ('part-0003',4,'omit','s=18;b=boot-b','s=25;b=boot-b','s=17;b=boot-a','f0803159ce3e380fe0bc8c74f5fced935aa0be9d0eee81b86afc589bd52db8f5','rollback-superseded','83baa1a8b9d2681f0f218cd90689b5a3e5f1f164444e9a4667f7bb0665225fae','gen-42/reload-1','batch-20260714',1);
insert into checkpoint values ('part-0004',6,'export','s=18;b=boot-b','s=32;b=boot-b','s=17;b=boot-a','4122793617f506df194ea575b9af17b63f90c9d5a3aa458561ae42f0b1a07180','','','gen-42/reload-1','batch-20260714',1);
commit;
SQL

rm -rf /app/output/current
/usr/local/bin/rotlogctl verify --root /app/ops --out /app/output/current
/usr/local/bin/rotlogctl legacy-verify --root /app/ops
