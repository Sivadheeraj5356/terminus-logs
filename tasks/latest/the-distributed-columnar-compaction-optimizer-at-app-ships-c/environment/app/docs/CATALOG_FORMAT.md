# CLFC catalog binary format

Catalog files begin with the four-byte magic CLFC. All multi-byte integers are little-endian unless noted otherwise.

## Header (12 bytes total)

| Field | Size | Notes |
|-------|------|-------|
| magic | 4 | ASCII CLFC |
| version | 2 | Must be 1 |
| fragment_count | 2 | Number of records that follow |
| reserved | 4 | Must be zero in version 1 |

Record data begins immediately after the 12-byte header.

## Fragment record

Records appear back-to-back in file order:

| Field | Size |
|-------|------|
| id | u16 |
| partition_id | u16 |
| seq | u16 |
| flags | u16 |
| row_start | u32 |
| row_end | u32 |
| byte_size | u32 |
| replica_mask | u16 |
| column_name_len | u16 |
| column_name | column_name_len bytes UTF-8 |

Duplicate id values in one catalog are invalid. row_end must be greater than or equal to row_start.

## Semantics

id is the stable fragment identifier referenced in merge plan JSON. partition_id groups fragments that may chain together. seq is the semantic ordering key used during validation and tie-breaking. flags bit 0 marks an anchor fragment.

Column names are normalized before comparison using the same rules as /app/docs/COMPACTION_CONTRACT.md.

Sample catalogs under /app/data/catalogs/ show common overlap chains; they do not cover every valid id or seq assignment.
