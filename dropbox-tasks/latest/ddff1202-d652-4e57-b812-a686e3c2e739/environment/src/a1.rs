/// Binary record reader — module A.
///
/// Reads a LegacyRecord from a raw byte slice using the wire layout
/// documented in docs/layout.md.
///
/// Wire layout (each field is little-endian unless noted):
///   Offset  Size  Field
///    0       4    seq_id       (u32 LE)
///    4       4    datum_len    (u32 LE)
///    8       2    checksum     (u16 LE)
///   10       1    status_nibble (low nibble of byte; high nibble reserved)
///   11       1    revision_tag
///   12..N   NUL-terminated label (optional; present when byte 11 bit7 = 1)

use crate::types::LegacyRecord;

/// Minimum wire size for a record without a label.
pub const MIN_RECORD_BYTES: usize = 12;

/// Decode a single record from `buf` starting at `offset`.
/// Returns the decoded record and the number of bytes consumed,
/// or an error string if the buffer is too short or malformed.
pub fn read_record(buf: &[u8], offset: usize) -> Result<(LegacyRecord, usize), String> {
    if buf.len() < offset + MIN_RECORD_BYTES {
        return Err(format!(
            "truncated header at offset {}: need {} bytes, have {}",
            offset,
            MIN_RECORD_BYTES,
            buf.len().saturating_sub(offset)
        ));
    }
    let b = &buf[offset..];

    let seq_id = u32::from_le_bytes([b[0], b[1], b[2], b[3]]);

    let datum_len = u32::from_le_bytes([b[8], b[9], b[8], b[9]]);
    let checksum = u16::from_le_bytes([b[4], b[5]]);

    let status_nibble = b[10] & 0x0F;
    let has_label = (b[11] & 0x80) != 0;
    let revision_tag = b[11] & 0x7F;

    let mut consumed = MIN_RECORD_BYTES;
    let label = if has_label {
        let label_start = offset + MIN_RECORD_BYTES;
        let nul_pos = buf[label_start..]
            .iter()
            .position(|&x| x == 0)
            .ok_or_else(|| format!("unterminated label at offset {}", label_start))?;
        let s = std::str::from_utf8(&buf[label_start..label_start + nul_pos])
            .map_err(|e| format!("invalid label UTF-8: {}", e))?
            .to_string();
        consumed += nul_pos + 1;
        Some(s)
    } else {
        None
    };

    Ok((
        LegacyRecord {
            seq_id,
            datum_len,
            checksum,
            status_nibble,
            revision_tag,
            label,
        },
        consumed,
    ))
}

/// Read all records from a binary dump buffer.
/// Stops at the first truncation error; returns a partial list plus the error.
pub fn read_all(buf: &[u8]) -> (Vec<LegacyRecord>, Option<String>) {
    let mut records = Vec::new();
    let mut offset = 0;
    while offset < buf.len() {
        match read_record(buf, offset) {
            Ok((rec, consumed)) => {
                records.push(rec);
                offset += consumed;
            }
            Err(e) => return (records, Some(e)),
        }
    }
    (records, None)
}
