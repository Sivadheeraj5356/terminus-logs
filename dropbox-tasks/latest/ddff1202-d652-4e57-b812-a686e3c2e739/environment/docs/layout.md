# Record Layout Reference

## Binary wire format

Records in the `.bin` fixture files use a fixed-prefix layout followed by an
optional NUL-terminated label.  All multi-byte integers are little-endian.

| Offset | Size | Field          | Notes                                      |
|--------|------|----------------|--------------------------------------------|
| 0      | 4    | `seq_id`       | u32 LE; 1-based sequential identifier      |
| 4      | 4    | `datum_len`    | u32 LE; byte count of the data region      |
| 8      | 2    | `checksum`     | u16 LE; checksum word stored in the record |
| 10     | 1    | status byte    | high nibble: reserved (must be zero for valid records); low nibble: `status_nibble` |
| 11     | 1    | control byte   | bit 7: has_label flag; bits 0–6: `revision_tag` |
| 12+    | var  | label          | NUL-terminated UTF-8; present when has_label = 1 |

Minimum record size (no label): 12 bytes.

## Text export format

Text export files (`.txt`) contain one record per line.  Lines beginning with
`#` are comments and are ignored.  Fields are comma-separated decimal integers;
an optional label field appears last.

```
# columns: seq_id,datum_len,checksum,status_nibble,revision_tag[,label]
1,6720,1234,3,5
2,8192,2048,1,2
3,512,4095,7,0,alpha
4,16384,300,2,6
```

The text export carries the authoritative decoded field values.  When binary
and text surfaces disagree, the text export is the reference.

## Field semantics

- `seq_id`: unique within a sample group; used as the join key between binary
  and text surfaces.
- `datum_len`: byte count of the payload that follows the record header in the
  logical stream.  Must not exceed 0x0FFFFFFF for a valid record.
- `checksum`: 16-bit checksum word; not recomputed by the decoder — stored as-is.
- `status_nibble`: low 4 bits of the status byte; encodes operational state.
- `revision_tag`: low 7 bits of the control byte; version or revision marker.
- `label`: optional human-readable tag; absent on most records.
