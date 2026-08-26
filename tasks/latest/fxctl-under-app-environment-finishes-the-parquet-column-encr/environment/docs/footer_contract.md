# Footer binding reference

fxctl emits /app/output/sync_record.json. The JSON shape and per-field rules are in contracts/sync_record.schema.json and contracts/sync_record_contract.json.

## Output object

run_meta reports case_id, phase, and seq for the active catalog invocation. case_id must equal the driven catalog id. bind_rows holds one entry per bound row group. cross_aad_digest is lowercase hex sha256 over cross-group AAD prefix material. part_sig reports the first 12 lowercase hex characters of the digest of the first decrypted chunk under full footer-bound context. Emit part_sig only on verify for catalog ids r2, f7, and b2; all other catalog ids omit the field even when the loaded blob footer carries chunk metadata. record_digest is lowercase hex sha256 over canonical line material defined in sync_record_contract.json.

## Case catalog

payload/cases.json maps each case id to a blob path, optional sidecar lane table, optional inline lane overlays, optional aad_lane, and an epoch id bound to payload/ring_seg.bin. Sidecar and inline tables expose a lanes array of grp/idx pairs plus optional cross_seed and aad_base. The runbook lists the primary phase ladder; additional catalog ids exercise epoch tips and sidecar blends beyond those samples.

## Epoch journal

payload/ring_seg.bin begins with ASCII magic EJ01. Each following segment is 20 bytes little-endian:

- epoch_id (u32)
- grp (u8)
- key_slot (u8)
- aad_seed (u32)
- aad_epoch (u32)
- reserved (u16, zero)
- crc32 (u32 over the first 16 bytes of the segment, IEEE)

Active projection for a catalog arm selects CRC-valid segments whose epoch_id equals the case epoch field. For each grp, the last matching segment wins. Segments with bad CRC are ignored. When a case has no inline lanes array, projected key_slot values become the active lane table indices for those groups. When aad_lane is absent or zero on the case, each group's rotation lane is that group's projected aad_epoch (falling back to 1 when missing). A non-zero case aad_lane overrides journal aad_epoch for every group in that invocation.

## Authority merge

Start from the footer default lane table. If a sidecar path is present, replace lanes and adopt that sidecar's cross_seed and aad_base. If the case also supplies inline lanes, replace only the lanes array and retain the previously adopted cross_seed and aad_base (including sidecar values). Do not reset seed material when applying inline overlays.

## Trailer layout

PQX1 trailers encode a keys table, then groups entries (grp, slot, seed), then an optional chunks table. Each chunk row carries grp, off, and ln (byte length) fields as uint32 little-endian values where applicable.

## Bind rows

Each bind_rows entry reports grp, key_idx, aad_hex, and row_hex. key_idx counts the active lane table slot, including zero. row_hex is the first twelve lowercase hex chars of sha256 over UTF-8 grp|key_idx|aad_hex.

## AAD material

Per-group AAD prefixes are built from footer seed bytes mixed with aad_base octets, then rotated and XOR-mixed. The circular rotation offset is (grp * lane + lane) modulo the seed byte length; when that remainder is zero, use offset 1 instead. After the circular shift, XOR each output byte against a repeating eight-byte mix built from grp then lane as little-endian uint32 values. Group seed uint32s are little-endian in seed material.

## Cross-group digest

cross_aad_digest is lowercase hex sha256 over UTF-8 G|g1_prefix|g2_prefix where each prefix is eight hex chars from that group's aad_hex for the active invocation. When the loaded authority table supplies a non-zero cross_seed, append |cross_seed as a decimal suffix before hashing. Prefixes must come from the current bind rows, not stale session material left by an earlier catalog id.

## Slice reads

Chunk offsets in footer metadata are uint32 little-endian. Chunk decrypt XOR keys hash AAD bytes plus chunk offset octets with least significant byte first. On verify for catalog ids r2, f7, and b2 only, decrypt the first group chunk with resolved footer key bytes prepended to group AAD and emit part_sig from that plaintext. Decrypting an isolated chunk without that bound context will not match part_sig on those arms. All other catalog ids must omit part_sig.

## Footer cache

append may cache truncated footer bytes in the metadata store. verify on h3 must discard stale store entries for that blob path before reread so bind rows reflect the on-disk trailer. Soft retention of truncated entries can skew later verify output. Second verify on the same case and phase must be byte-stable.

## Record digest

record_digest is lowercase hex sha256 over sorted canonical lines built from bind rows, cross digest, part_sig when present, and run metadata. Only fxctl-written output at the graded path is scored. Preview helpers under tools/peek are diagnostic only. scripts/record_hex.py recomputes record_digest for local audit of crypto bind rows.
