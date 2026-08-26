# VSW1 journal layout

Binary journals use magic `VSW1` followed by a 32-byte header and a sequence of records.

## Header (32 bytes, little-endian except where noted)

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | Magic `VSW1` |
| 4 | 4 | `rotate_gen` u32 LE |
| 8 | 4 | `bound_rotate` u32 LE |
| 12 | 4 | `slack` u32 LE |
| 16 | 4 | `record_count` u32 LE |
| 20 | 12 | Reserved (zero) |

## Record body

| Field | Type |
|-------|------|
| `scope_id` | u32 LE |
| `action_mask` | u32 LE |
| `size_delta` | i32 LE signed |
| `seq_num` | u32 LE |
| `ts_ms` | u64 LE |
| `path_len` | u16 LE |
| `rel_path` | UTF-8 bytes |
| `payload_len` | u32 LE |
| `payload` | opaque bytes |

Read exactly `record_count` records from the byte stream after the header.
