# Claim docket frame layout

Each *.cdk file is a byte stream of sealed frames laid out back to back.

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | Magic CDKT |
| 4 | 1 | Format version (1) |
| 5 | 1 | Frame kind (1 record, 2 void marker, 3 tombstone) |
| 6 | 4 | Epoch, uint32 little-endian |
| 10 | 8 | Sequence, uint64 little-endian |
| 18 | 4 | Payload length, uint32 little-endian |
| 22 | N | UTF-8 JSON payload |
| 22+N | 4 | CRC32C (Castagnoli), uint32 little-endian over bytes [0 .. 22+N) |

Payload JSON carries account, kind, region, seq, an optional amount, and an optional replaces_seq on superseding rows. Kind values are upsert, transfer, void, and tombstone.

Checksum failures increment crc_failure_count and the frame is skipped for digest and settlement tallies.

If the header parses but the declared payload plus trailing checksum would run past the end of the shard, the frame is treated as unreadable: crc_failure_count rises, scanning stops for that shard, and earlier validated frames in the same or other shards are kept.

The Python helpers in ci/ parse header integers with struct little-endian unpackers and validate checksums with the crc32c module over the same byte range.
