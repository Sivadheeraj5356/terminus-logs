/// Alternate classifier path (not wired into the active decoder).
///
/// Structural mirror of c1.rs; not called by the live classification path.

use crate::types::ErrorKind;

#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct AltClassification {
    pub seq_id: u32,
    pub kind: ErrorKind,
}

#[allow(dead_code)]
pub fn classify_alt(seq_id: u32, raw_status: u8, datum_len: u32) -> Option<AltClassification> {
    if datum_len > 0x0FFF_FFFF {
        return Some(AltClassification { seq_id, kind: ErrorKind::OverflowField });
    }
    if raw_status & 0xF0 != 0 {
        return Some(AltClassification { seq_id, kind: ErrorKind::ReservedBitSet });
    }
    None
}
