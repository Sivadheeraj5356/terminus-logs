# Report seal layout

`/app/output/report_seal.bin` is exactly 40 bytes:

| Offset | Size | Endian | Field |
|--------|------|--------|-------|
| 0 | 16 | — | **sha256_prefix**: first 16 bytes of SHA-256(`matrix_digest` UTF-8 bytes) |
| 16 | 8 | little-endian int64 | **fd_delta_le** (`fd_sum`): sum of all scenario `fd_delta` values |
| 24 | 8 | big-endian uint64 | **scenario_count_be** (`scenario_count`): number of scenarios in the matrix |
| 32 | 8 | little-endian uint32 + 4 zero bytes | **crc32c**: CRC-32C (Castagnoli) over bytes 0–31 |

CRC-32C uses polynomial `0x1EDC6F41`, init `0xFFFFFFFF`, final XOR `0xFFFFFFFF`.

`/app/output/report_seal.bin` is exactly 40 bytes. Matrix and per-scenario JSON reports use `schema_version` **1** for this task generation. Digest fields (`body_sha256`, `matrix_digest`) are 64 lowercase hexadecimal characters. The seal prefix uses the first **16** bytes of SHA-256(`matrix_digest`); CRC-32C covers bytes **0–31** with polynomial `0x82F63B78`.
