#!/usr/bin/env python3
"""Generate binary and text fixture files for the legacy-record-decoder task."""

import struct
import os

BASE = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def encode_record(seq_id, datum_len, checksum, status_nibble, revision_tag,
                  label=None, reserved_high=0):
    """Encode a single record in the wire format.

    Wire layout (all little-endian):
      0..4  seq_id       (u32 LE)
      4..8  datum_len    (u32 LE)
      8..10 checksum     (u16 LE)
      10    status byte  (reserved_high << 4 | status_nibble)
      11    ctrl byte    (has_label << 7 | revision_tag)
    If has_label: NUL-terminated UTF-8 label follows at byte 12.
    """
    status_byte = ((reserved_high & 0x0F) << 4) | (status_nibble & 0x0F)
    has_label = 1 if label else 0
    ctrl_byte = (has_label << 7) | (revision_tag & 0x7F)
    buf = struct.pack("<IIHBB", seq_id, datum_len, checksum, status_byte, ctrl_byte)
    if label:
        buf += label.encode("utf-8") + b"\x00"
    return buf


def write_text_export(path, records):
    """Write a text export with the CORRECT field values (ground truth)."""
    lines = [
        "# Legacy record text export",
        "# columns: seq_id,datum_len,checksum,status_nibble,revision_tag[,label]",
    ]
    for r in records:
        seq_id, datum_len, checksum, status_nibble, revision_tag = r[:5]
        label = r[5] if len(r) > 5 and r[5] else None
        row = f"{seq_id},{datum_len},{checksum},{status_nibble},{revision_tag}"
        if label:
            row += f",{label}"
        lines.append(row)
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    os.makedirs(os.path.join(BASE, "raw"), exist_ok=True)
    os.makedirs(os.path.join(BASE, "text"), exist_ok=True)
    os.makedirs(os.path.join(BASE, "bad"), exist_ok=True)
    os.makedirs(os.path.join(BASE, "interim"), exist_ok=True)

    # ------------------------------------------------------------------ set_a
    # 4 records.  datum_len and checksum have distinct values across each record
    # to exercise the full cross-surface field comparison in the decoder.
    set_a = [
        # (seq_id, datum_len, checksum, status_nibble, revision_tag, label)
        (1, 6720, 1234, 3, 5, None),
        (2, 8192, 2048, 1, 2, None),
        (3, 512,  4095, 7, 0, "alpha"),
        (4, 16384, 300, 2, 6, None),
    ]
    buf_a = b"".join(encode_record(*r) for r in set_a)
    with open(os.path.join(BASE, "raw", "set_a.bin"), "wb") as f:
        f.write(buf_a)
    write_text_export(os.path.join(BASE, "text", "set_a.txt"), set_a)

    # ------------------------------------------------------------------ set_b
    # 10 records: 4 normal, 1 with reserved bits, 5 with cross-format conflicts.
    # The conflicts force discovery of semantic coupling between systems.
    set_b_raw = [
        # Normal records
        (5, 2048, 512,  5, 3, None, 0),
        (6, 4096, 1024, 2, 1, None, 0),
        (7, 256,  88,   0, 4, None, 1),   # reserved_high=1 -> ReservedBitSet
        (8, 1024, 200,  6, 7, "beta", 0),
        # Conflict records (endian traps, field swaps, cross-surface ambiguities)
        (9, 256,  256,  3, 2, "endian_trap", 0),     # datum_len=checksum creates ambiguity
        (10, 4096, 4096, 1, 5, "endian_conflict", 0), # Both large; breaks if not careful
        (11, 512,  512,  4, 1, "mirror", 0),         # datum_len=checksum=512; perfect ambiguity
        (12, 300,  600,  7, 3, "near_swap", 0),      # 2x relationship; can appear swapped
        (13, 88,   176,  2, 6, "half_double", 0),    # Half/double relationship
        (14, 1000, 1000, 0, 0, "identity", 0),       # All repeated values
    ]
    buf_b = b""
    for r in set_b_raw:
        seq_id, datum_len, ck, sn, rt, lbl, rh = r
        buf_b += encode_record(seq_id, datum_len, ck, sn, rt, lbl, rh)
    with open(os.path.join(BASE, "raw", "set_b.bin"), "wb") as f:
        f.write(buf_b)
    # Text export for set_b: correct values including the malformed record
    set_b_text = [(r[0], r[1], r[2], r[3], r[4]) + ((r[5],) if r[5] else ())
                  for r in set_b_raw]
    write_text_export(os.path.join(BASE, "text", "set_b.txt"), set_b_text)

    # --------------------------------------------------------------- bad/bad_a
    # Truncated: only 8 bytes (less than MIN_RECORD_BYTES=12).
    buf_bad_a = struct.pack("<II", 99, 100)
    with open(os.path.join(BASE, "bad", "bad_a.bin"), "wb") as f:
        f.write(buf_bad_a)

    # --------------------------------------------------------------- bad/bad_b
    # One valid record followed by one with OverflowField datum_len.
    buf_bad_b = (
        encode_record(1, 100, 50, 1, 2)
        + encode_record(2, 0x2FFF_FFFF, 99, 0, 0)
    )
    with open(os.path.join(BASE, "bad", "bad_b.bin"), "wb") as f:
        f.write(buf_bad_b)

    # --------------------------------------------------------------- interim/stub.json
    # An example of a partially-consistent intermediate snapshot.
    # The full pipeline run is required to generate the graded bundle.
    stub = {
        "records": [{"seq_id": 1, "datum_len": 1234, "checksum": 6720,
                     "status_nibble": 3, "revision_tag": 5, "label": None}],
        "compatibility_trace": [{"seq_id": 1, "state": "compatible",
                                  "diverged_fields": []}],
        "error_classification": [],
        "artifacts": [],
        "_note": "interim snapshot only — not the graded bundle",
    }
    import json
    with open(os.path.join(BASE, "interim", "stub.json"), "w") as f:
        json.dump(stub, f, indent=2)

    print("Fixtures generated:")
    for dirpath, _, filenames in os.walk(BASE):
        for fn in sorted(filenames):
            fp = os.path.join(dirpath, fn)
            print(f"  {fp}  ({os.path.getsize(fp)} bytes)")


if __name__ == "__main__":
    main()
