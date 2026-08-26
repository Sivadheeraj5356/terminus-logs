This document is the complete normative format and replay contract. Every verifier stream follows it; there are no undisclosed record types, flags, state transitions, rejection reasons, or output fields.

Each frame is exactly 36 bytes, little-endian, with this layout:

| Offset | Size | Field |
| --- | ---: | --- |
| 0 | 2 | magic bytes `0x48 0x42` |
| 2 | 1 | version, valid values `1` and `2` |
| 3 | 1 | type: `1` calibration, `2` snapshot, `3` delta, `4` delete, `5` station beacon, `6` station anchor, `7` station relay, `8` station checkpoint, `9` quorum certificate |
| 4 | 1 | flags |
| 5 | 1 | station id, unsigned |
| 6 | 2 | sequence number, unsigned |
| 8 | 2 | sensor id, unsigned |
| 10 | 2 | base sequence, unsigned |
| 12 | 4 | raw value or raw delta, signed |
| 16 | 4 | scale in parts per million, signed |
| 20 | 4 | offset in milli-units, signed |
| 24 | 8 | timestamp, signed |
| 32 | 4 | IEEE CRC-32 of bytes 0 through 31, unsigned |

All formulas that mention unsigned 32-bit arithmetic wrap modulo `2^32` after each `+`, `*`, or `^` operation. When a formula result is compared with a signed frame field, compare the underlying two's-complement bit pattern, not the mathematical signed value. `rotl16(x, n)` means rotate the low 16 bits of `x` left by `n` bits. When extracting the high or low 16 bits of a signed 32-bit field such as `offset_milli`, reinterpret the field as unsigned 32-bit first. `low16(x)` means `(uint16_t)((uint32_t)x & 0xffff)`, `high16(x)` means `(uint16_t)(((uint32_t)x >> 16) & 0xffff)`, and `low32(timestamp)` means `(uint32_t)((uint64_t)timestamp & 0xffffffff)`.

The CRC uses polynomial `0xedb88320`, initial value `0xffffffff`, and final xor `0xffffffff`. Verifier inputs contain at most 4096 distinct `(station, sensor)` keys. Every accepted delta sum fits in signed 32-bit range, and final calibrated arithmetic fits in signed 64-bit range.

For calibration records, `scale_ppm` and `offset_milli` are meaningful. `raw`, `base_seq`, and `timestamp` are ignored for plain calibrations, but are meaningful for sealed encoded version-2 calibrations. For snapshot records, `raw` and `timestamp` are meaningful and `base_seq`, `scale_ppm`, and `offset_milli` are ignored unless the record is in encoded version-2 mode as described below. For delta records, `base_seq`, `raw`, and `timestamp` are meaningful and calibration fields are ignored unless the record is in encoded version-2 mode. For delete records, `base_seq` and `timestamp` are meaningful and raw/calibration fields are ignored unless the record is in encoded version-2 mode. Beacon, anchor, relay, checkpoint, and quorum records use their decoded fields for station-level authentication; relays reinterpret `sensor` as a source station id and quorums reinterpret its two bytes as witness station ids.

Initially every freshness history is unset, every sensor is inactive with default calibration `scale_ppm=1000000` and `offset_milli=0`, and every authentication key is absent. An unset history accepts its first otherwise-valid record at any sequence, including zero. Key invalidation never erases freshness history. Rejected records never partially mutate state.

Process each complete frame using this exact precedence, stopping at the first failure:

1. wrong physical size for a final fragment is `bad_length` and stops replay;
2. wrong magic is `bad_magic`;
3. CRC mismatch over stored bytes 0 through 31 is `bad_crc`;
4. a version other than 1 or 2 is `bad_version`;
5. invalid version/flag bits are `bad_flags`;
6. a type outside 1 through 9 is `bad_type`;
7. run Beacon-X decoding when selected;
8. invalid decoded record shape is `bad_layout` (this includes a type-5 station beacon whose decoded `raw` does not equal its beacon authentication word);
9. an otherwise-valid record outside its independent freshness horizon is `stale`;
10. a failed prerequisite or authentication check not explicitly classified as decoded layout (notably excluding the type-5 beacon authentication word checked at step 8) is `dependency`;
11. otherwise apply the entire transition and increment `accepted` once.

Every complete frame contributes exactly once to either `accepted` or one rejection counter. `rejected` is the sum of the nine rejection counters, including a possible trailing fragment.

Replay frames in physical file order. Each valid calibration, snapshot, delta, or delete frame belongs to one `(station, sensor)` key. Calibration records have their own sequence history for that key. Snapshot, delta, and delete records share a separate data sequence history for that key. Station beacon, anchor, relay, checkpoint, and quorum-certificate records have separate sequence histories per station. A sequence number is newer than the current sequence when `(candidate - current) mod 65536` is between 1 and 257 inclusive; equal, older, or more than 257 steps ahead is stale.

Station authentication keys form an invalidating hierarchy. An accepted beacon invalidates the station's current anchor, relay, checkpoint, and quorum keys; an anchor invalidates relay, checkpoint, and quorum; a relay invalidates checkpoint and quorum; and a checkpoint invalidates quorum. Invalidation preserves independent sequence histories. A quorum is also dynamically invalid when either external witness beacon sequence changes. Rejected records do not invalidate keys.

Reject a frame before changing state if its magic, CRC, version, flags, type, or layout is invalid. CRC is checked over the first 32 bytes exactly as stored. Version 1 allows no flags. Version 2 allows Beacon-X bit 0 and auth bits 1 through 6 for carry, chain, epoch, relay, checkpoint, and quorum authentication. Bits 1 through 6 are invalid unless bit 0 is set; bit 7 is always invalid. Thus nonzero even values are `bad_flags`, while odd values through 127 can still be `bad_layout`. Beacon, anchor, relay, checkpoint, and quorum records must use exactly `flags=1`.

Version 2 flag bit 0 means bytes at offsets 6 through 31 are stored in encoded Beacon-X form. Decode those bytes only after the magic, CRC, version, flags, and type checks pass. Do not decode bytes 0 through 5 or the CRC. The encoding is symmetric: for each byte offset from 6 through 31, update an 8-bit state and XOR the byte with that state:

1. initialize `state = 0xa5 ^ station ^ (type * 17) ^ version`, using 8-bit unsigned arithmetic,
2. for each offset `off`, rotate `state` left by one bit,
3. XOR `state` with `(0x3d + off * 11) mod 256`,
4. XOR the payload byte at `off` with `state`.

This means the CRC validates the encoded bytes, while replay logic uses the decoded field values.

The flag bit is authoritative: if version is `2` and flag bit `0` is set, always run the Beacon-X transform on bytes 6 through 31 before interpreting `seq`, `sensor`, `base_seq`, `raw`, `scale_ppm`, `offset_milli`, or `timestamp`. Do not try to detect whether the stored bytes "look already decoded"; there is no plaintext exception for flag bit `0`.

Version 2 auth bits 1 through 6 are valid only with bit 0 and only for snapshot, delta, and delete records. If any appears on a decoded calibration, beacon, anchor, relay, checkpoint, or quorum certificate, reject it as `bad_layout`.

The error-category boundary around station beacons is intentionally asymmetric and is normative:

| Record and failed check | Rejection category | Stage |
| --- | --- | --- |
| type-5 station beacon has wrong mode/flags, nonzero decoded `sensor`, or a decoded `raw` value that does not equal the beacon authentication word | `bad_layout` | decoded layout, before beacon freshness |
| encoded snapshot, delta, or delete has no current station beacon, or low16 of decoded `scale_ppm` does not equal the current beacon sequence | `dependency` | after that data record's layout and freshness checks |
| carry-auth snapshot, delta, or delete has no current station beacon or has a wrong carry tag | `dependency` | after normal data/base, beacon-tag, and calibration-tag checks as applicable |

Therefore, do not use one generic "authentication failed" category. In particular, a correctly encoded type-5 frame with `flags=1` and `sensor=0` but an incorrect decoded beacon authentication word increments `bad_layout` exactly once; it never increments `dependency`, and its sequence is not tested for staleness. This exception applies to the type-5 beacon record itself. It does not change the `dependency` classification for beacon-tag or carry-auth prerequisites on types 2 through 4.

A calibration record is accepted only if its sequence is newer than the key's current calibration sequence. It sets that key's `scale_ppm` and `offset_milli`; defaults are `1000000` and `0`.

An encoded version-2 calibration with exactly flag bit `0` set is a sealed calibration. After stale passes, decoded `base_seq` must equal the station's current accepted beacon sequence and decoded `raw` must match this sealed-calibration authentication word, using the station key from that beacon:

`auth = 0x9e3779b9 ^ (timestamp & 0xffffffff)`

`auth = auth + seq * 2246822519`

`auth = auth ^ station_key * 3266489917`

`auth = auth + sensor * 668265263`

`auth = auth ^ scale_ppm * 40503`

`auth = auth + (offset_milli ^ rotl16(base_seq, 7))`

`auth = auth ^ station * 2654435761`

A missing/wrong beacon dependency or bad sealed-calibration authentication word is `dependency`. Plain version-1 and unencoded version-2 calibrations do not have this dependency. An accepted calibration also creates a calibration authentication key:

`cal_key = rotl16(seq, 7) ^ low16(scale_ppm) ^ high16(scale_ppm) ^ rotl16(low16(offset_milli), 3) ^ high16(offset_milli) ^ (station << 8) ^ sensor`

A snapshot record is accepted only if its sequence is newer than the key's current data sequence. It makes the key active, sets raw value to the record raw value, and records that frame's sequence and timestamp as the current data state.

A delta record is accepted only if its sequence is newer than the key's current data sequence, the key is currently active, and `base_seq` equals the key's current data sequence. It adds the record raw value to the current raw value and records the delta frame's sequence and timestamp.

A delete record is accepted only if its sequence is newer than the key's current data sequence and either `base_seq` is `65535` or `base_seq` equals the key's current data sequence. It makes the key inactive and records the delete frame's sequence and timestamp.

A station beacon record is accepted only in encoded version-2 mode with exactly flag bit 0 set, only when `sensor` is `0`, only when decoded `raw` equals the authentication word, and only if its sequence is newer than the station's current beacon sequence. Wrong mode/flags, nonzero decoded `sensor`, or an incorrect decoded beacon authentication word is `bad_layout`. This authentication-word failure is not `dependency`: perform it before the beacon freshness check, count only `bad_layout`, and do not mutate station state.

Compute the beacon authentication word from decoded fields with unsigned 32-bit arithmetic:

`auth = 0x5f3759df ^ (timestamp & 0xffffffff)`

`auth = auth + seq * 1103515245`

`auth = auth ^ station * 2654435761`

`auth = auth + base_seq * 40503`

The decoded signed `raw` field must contain the same 32-bit pattern as `auth`.

An accepted beacon also stores a 16-bit station authentication key:

`station_key = rotl16(seq, 5) ^ (timestamp & 0xffff) ^ base_seq ^ (station << 8)`

Sanity check: for a decoded beacon with `station=21`, `seq=400`, `base_seq=9`, and `timestamp=100`, the authentication word is `0xdfa2af7d` (so decoded signed `raw` is `-542986371`) and `station_key` is `0x276d`.

A station anchor record, type `6`, is accepted only in encoded version-2 mode with exactly flag bit 0 set, only when `sensor` is `0`, only if its sequence is newer than the station's current anchor sequence, only if the station already has an accepted station beacon whose current sequence equals `base_seq`, and only when decoded `raw` equals the station anchor authentication word. Invalid anchor shape is `bad_layout`; stale anchors are `stale`; missing/wrong beacon dependency or bad anchor authentication is `dependency`.

Compute the anchor authentication word from decoded fields and the current `station_key` with unsigned 32-bit arithmetic:

`auth = 0xc2b2ae35 ^ (timestamp & 0xffffffff)`

`auth = auth + seq * 747796405`

`auth = auth ^ station_key * 2891336453`

`auth = auth + station * 40503`

`auth = auth + base_seq * 97`

An accepted anchor stores `epoch_key = rotl16(seq, 9) ^ station_key ^ low16(timestamp) ^ base_seq ^ (station << 8)`.

A station relay record, type `7`, is accepted only in encoded version-2 mode with exactly flag bit 0 set. Its decoded `sensor` field is a source station id and must be at most `255`. The relay's station must already have an accepted anchor whose current anchor sequence equals `base_seq`, and the source station must already have an accepted beacon. The relay sequence must be newer than the station's current relay sequence, and decoded `raw` must equal the relay authentication word. Invalid relay shape is `bad_layout`; stale relays are `stale`; missing/wrong anchor dependency, missing source beacon, or bad relay authentication is `dependency`.

Compute the relay authentication word from decoded fields, the current station `epoch_key`, and the source station's `station_key` with unsigned 32-bit arithmetic:

`auth = 0x85ebca6b ^ (timestamp & 0xffffffff)`

`auth = auth + seq * 1597334677`

`auth = auth ^ epoch_key * 2246822519`

`auth = auth + source_station_key * 3266489917`

`auth = auth ^ station * 40503`

`auth = auth + source_station * 97`

`auth = auth + base_seq * 31`

An accepted relay stores `relay_key = rotl16(seq, 2) ^ epoch_key ^ source_station_key ^ low16(timestamp) ^ (station << 8) ^ source_station`.

A station checkpoint record, type `8`, is accepted only in encoded version-2 mode with exactly flag bit 0 set and decoded `sensor=0`. Its sequence must be newer than the station's checkpoint history. The station must have current beacon and anchor keys, `base_seq` must equal the current anchor sequence, and decoded `raw` must match:

`auth = 0x27d4eb2f ^ (timestamp & 0xffffffff)`

`auth = auth + seq * 2654435761`

`auth = auth ^ station_key * 2246822519`

`auth = auth + epoch_key * 3266489917`

`auth = auth ^ station * 668265263`

`auth = auth + base_seq * 40503`

Invalid shape is `bad_layout`, stale is `stale`, and a missing/mismatched prerequisite or authentication failure is `dependency`. Acceptance stores `checkpoint_key = rotl16(seq, 13) ^ station_key ^ rotl16(epoch_key, 3) ^ low16(timestamp) ^ base_seq ^ (station << 8)`.

A quorum certificate, type `9`, binds a target station to two external beacon witnesses. It is valid only in encoded version-2 mode with `flags=1`. The low and high bytes of decoded `sensor` are witnesses A and B; layout requires `A < B` and neither may equal the target. It has an independent per-target freshness history. After stale, the target must have current beacon, anchor, and checkpoint keys; `base_seq` equals the checkpoint sequence; the low/high halves of `offset_milli` equal target anchor/beacon sequences; both witnesses have beacons; and the low/high halves of `scale_ppm` equal witness A/B beacon sequences. Decoded `raw` must match the following unsigned 32-bit computation, where `witnesses` is decoded `sensor`:

`auth = 0x165667b1 ^ low32(timestamp)`

`auth = auth + seq * 374761393`

`auth = auth ^ checkpoint_key * 668265263`

`auth = auth + station_key * 2246822519`

`auth = auth ^ epoch_key * 3266489917`

`auth = auth + witness_a_station_key * 40503`

`auth = auth ^ witness_b_station_key * 2654435761`

`auth = auth + witnesses * 97 + base_seq * 31`

`auth = auth ^ station * 1597334677`

Acceptance stores all five prerequisite sequences and creates `quorum_key = rotl16(seq, 7) ^ station_key ^ epoch_key ^ checkpoint_key ^ rotl16(witness_a_station_key, 3) ^ rotl16(witness_b_station_key, 11) ^ low16(timestamp) ^ witnesses ^ (station << 8)`. The quorum stays current only while target beacon/anchor/checkpoint and both witness beacon sequences still match; witness updates therefore invalidate certificates at other stations without erasing quorum freshness.

Quorum sanity check: witness beacons `(station=11, seq=40, base_seq=1, timestamp=601)` and `(station=12, seq=50, base_seq=2, timestamp=602)` create keys `0x0c58` and `0x0818`. For station 10, beacon `(seq=100, base_seq=7, timestamp=600)`, anchor `(seq=101, base_seq=100, timestamp=603)`, and checkpoint `(seq=102, base_seq=101, timestamp=604)` create keys `0x04df`, `0xc6e0`, and `0xfbec`. A quorum with `seq=103`, `base_seq=102`, `timestamp=605`, `sensor=0x0c0b`, `scale_ppm=0x00320028`, and `offset_milli=0x00640065` needs raw bits `0x7ce1f6e7` and creates `quorum_key=0xac85`. A quorum-auth data record with `seq=1`, `sensor=77` then needs timestamp low16 `0x2cc8`.

Encoded version-2 snapshot, delta, and delete records have one extra station-level dependency: the low 16 bits of `scale_ppm` contain a beacon tag, and the station must already have an accepted station beacon whose current sequence equals that tag. For encoded deltas and deletes, this beacon dependency is in addition to the normal data/base dependency. For encoded snapshots, it is the first dependency after the stale check. Plain version-1 and unencoded version-2 data records do not have this beacon-tag dependency.

If version 2 flag bit 1 is also set, the decoded high 16 bits of `offset_milli` contain a carry-auth tag. After stale, normal data/base, and beacon-tag checks pass, the carry-auth tag must equal `station_key ^ rotl16(seq, 3) ^ sensor`, using the station's current accepted beacon. Failure is `dependency`. Sanity check continuing the beacon example above: an encoded snapshot for `station=21`, `sensor=5`, `seq=1`, and beacon tag `400` needs carry tag `0x2760`; one valid decoded `offset_milli` bit pattern is `0x27600000`, which is signed decimal `660602880`.

If version 2 flag bit 2 is set, the decoded high 16 bits of `scale_ppm` contain a calibration tag. The key must already have an accepted calibration, and the tag must equal `cal_key ^ rotl16(seq, 1)`. Failure is `dependency`. Chain-auth deltas and deletes also check the low 16 bits of decoded `offset_milli` after carry-auth passes; it must equal `data_key ^ rotl16(base_seq, 5) ^ sensor`, where `data_key` is the key's current rolling data key before applying the record. Deletes with `base_seq=65535` skip this rolling-data tag.

If version 2 flag bit 3 is set, the high 16 bits of the decoded 64-bit `timestamp` bit pattern contain an epoch-auth tag. Extract it as `epoch_tag = (uint16_t)(((uint64_t)timestamp >> 48) & 0xffff)`. This is not `high16(timestamp)` as defined for 32-bit fields, and it is not bits 16 through 31 of the low 32 bits. After normal data/base, beacon-tag, calibration-tag, carry-auth, and rolling chain-auth checks pass, the station must already have an accepted anchor and the tag must equal `epoch_key ^ rotl16(seq, 6) ^ sensor`. Failure is `dependency`. The timestamp is still used as the signed decoded timestamp for output and rolling-key formulas.

If version 2 flag bit 4 is set, bits 32 through 47 of the decoded 64-bit `timestamp` bit pattern contain a relay-auth tag: `(uint16_t)(((uint64_t)timestamp >> 32) & 0xffff)`. After normal data/base, beacon-tag, calibration-tag, carry-auth, rolling chain-auth, and epoch-auth checks pass, the station must already have an accepted relay and the tag must equal `relay_key ^ rotl16(seq, 9) ^ sensor`. Failure is `dependency`. If both epoch-auth and relay-auth are set, the epoch tag uses timestamp bits 48 through 63 and the relay tag uses bits 32 through 47.

If version 2 flag bit 5 is set, bits 16 through 31 of decoded `timestamp` contain a checkpoint-auth tag: `(uint16_t)(((uint64_t)timestamp >> 16) & 0xffff)`. After all earlier dependencies pass, the station must have a current checkpoint and the tag must equal `checkpoint_key ^ rotl16(seq, 12) ^ sensor`. Failure is `dependency`. Epoch, relay, and checkpoint tags occupy timestamp bits 48-63, 32-47, and 16-31 respectively.

If version 2 flag bit 6 is set, low16 of decoded `timestamp` is a quorum-auth tag. After all earlier dependencies, a current quorum and all five still-current bound sequences are required, and the tag must equal `quorum_key ^ rotl16(seq, 15) ^ sensor`. It is checked after checkpoint-auth and also supplies the low timestamp bits used by rolling-key formulas.

Accepted snapshots set `data_key = station_key ^ cal_key ^ low16(raw) ^ rotl16(seq, 4) ^ low16(timestamp) ^ (station << 8) ^ sensor`, using zero for a missing station or calibration key. Accepted deltas set `data_key = rotl16(previous_data_key, 3) ^ low16(raw_delta) ^ seq ^ low16(timestamp)`. Accepted deletes set `data_key = rotl16(previous_data_key, 11) ^ seq ^ low16(timestamp) ^ 0xd1e7`.

Worked chain-auth check values: an accepted encoded beacon with `station=31`, `seq=200`, `base_seq=4`, `timestamp=30` has `station_key=0x061a`. A calibration for `station=31`, `sensor=9`, `seq=10`, `scale_ppm=1234000`, `offset_milli=-12` has `cal_key=0xce13`. A chain-auth snapshot with `seq=11`, `raw=50`, `timestamp=31`, and beacon tag `200` needs `scale_ppm` bit pattern `0xce0500c8` and, if carry-auth is also set with low half `0x2222`, `offset_milli` bit pattern `0x064b2222`; accepting it creates `data_key=0xd79d`. A following chain-auth delta with `seq=12`, `base_seq=11`, `raw_delta=5`, `timestamp=32` needs `scale_ppm` bit pattern `0xce0b00c8` and `offset_milli` bit pattern `0x0673d6f4`; accepting it creates `data_key=0xbcc7`.

Dependency failures are counted only after the stale check passes. A stale frame is not also a dependency failure. Layout failures are counted before stale and dependency checks. For sealed calibration records, check the beacon-sequence dependency and authentication word after stale passes. For encoded auth data records, use this dependency order after stale: normal data/base, beacon tag, calibration tag, carry auth, rolling chain auth, epoch auth, relay auth, checkpoint auth, then quorum auth. Any failed dependency increments only `dependency` once. If the file ends with 1 to 35 extra bytes, count one `bad_length` and stop after all complete frames.

Output must use this exact order:

`summary accepted=<n> rejected=<n>`

`reject bad_length=<n>`

`reject bad_magic=<n>`

`reject bad_crc=<n>`

`reject bad_version=<n>`

`reject bad_flags=<n>`

`reject bad_type=<n>`

`reject bad_layout=<n>`

`reject stale=<n>`

`reject dependency=<n>`

Then one line for each active key:

`sensor station=<station> sensor=<sensor> seq=<seq> time=<timestamp> raw=<raw> calibrated_milli=<value>`

Active keys are sorted by station then sensor. `calibrated_milli` is `raw * scale_ppm / 1000 + offset_milli` using signed integer arithmetic with C's normal truncation toward zero.

The public input should produce:

```text
summary accepted=8 rejected=6
reject bad_length=0
reject bad_magic=0
reject bad_crc=1
reject bad_version=0
reject bad_flags=1
reject bad_type=0
reject bad_layout=0
reject stale=2
reject dependency=2
sensor station=1 sensor=100 seq=12 time=1020 raw=100 calibrated_milli=124950
sensor station=2 sensor=7 seq=1 time=2000 raw=-20 calibrated_milli=10025
```
