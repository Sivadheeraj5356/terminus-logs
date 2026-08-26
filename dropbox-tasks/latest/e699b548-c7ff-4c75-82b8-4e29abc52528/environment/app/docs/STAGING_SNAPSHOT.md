# Staging snapshot contract

The ingest stage writes a JSON snapshot at /app/state/compaction-snapshot.json unless --snapshot overrides the path. Export reads that snapshot and must not re-derive the fragment chain from live graph tracing when a valid snapshot is present.

## Required fields

version must be 1. catalog_path records the catalog file ingested. open_fragment_id is the chain start chosen during ingest. chain_fragment_ids and chain_overlaps describe the greedy merge chain computed at ingest time. replica_summary is a boolean summary of replica mask coverage across all fragments. catalog_digest is a 16-digit lowercase hex digest of fragment id, seq, and partition_id tuples in catalog order.

## Digest and repeat runs

export and plan must reject a snapshot whose catalog_digest does not match the catalog being read. The error token is STALE_SNAPSHOT. export, plan, and ingest fail with STAGING_ERROR when the snapshot file is missing or cannot be read at the resolved path (default /app/state/compaction-snapshot.json or a --snapshot override). Re-running plan on the same catalog and policy without an intervening repair must write byte-identical snapshot JSON at the default path. After a successful repair command, one subsequent plan or ingest may refresh the snapshot even when digest or formatting would otherwise change.

Repair records a one-shot reset token at /app/state/repair-snapshot-reset.token keyed by catalog digest.

## Pipeline

ingest parses the CLFC catalog, normalizes column names, traces the ingest merge chain per /app/docs/COMPACTION_CONTRACT.md, and writes the snapshot. export loads the snapshot, applies scan cost and fragmentation accounting from /app/docs/SCAN_COST.md, and emits merge plan JSON per /app/docs/OUTPUT_SCHEMA.md. plan runs ingest then export in one invocation. Chain order and junction overlaps always come from the staging snapshot fields chain_fragment_ids and chain_overlaps.
