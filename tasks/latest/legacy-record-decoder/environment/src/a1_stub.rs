/// Alternate binary read path (not wired into the active decoder).
///
/// Structural decoy parallel to a1.rs; not called by the live read path.

use crate::types::LegacyRecord;

#[allow(dead_code)]
pub fn read_record_alt(buf: &[u8], offset: usize) -> Result<(LegacyRecord, usize), String> {
    let min = 12usize;
    if buf.len() < offset + min {
        return Err("short buffer".into());
    }
    let b = &buf[offset..];
    Ok((
        LegacyRecord {
            seq_id: u32::from_le_bytes([b[0], b[1], b[2], b[3]]),
            datum_len: u32::from_le_bytes([b[4], b[5], b[6], b[7]]),
            checksum: u16::from_le_bytes([b[8], b[9]]),
            status_nibble: b[10] & 0x0F,
            revision_tag: b[11] & 0x7F,
            label: None,
        },
        min,
    ))
}

#[allow(dead_code)]
pub fn read_all_alt(buf: &[u8]) -> Vec<LegacyRecord> {
    let mut out = Vec::new();
    let mut off = 0;
    while off + 12 <= buf.len() {
        if let Ok((r, n)) = read_record_alt(buf, off) {
            out.push(r);
            off += n;
        } else {
            break;
        }
    }
    out
}
