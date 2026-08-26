/// Malformed-input classifier.
///
/// Inspects a decoded record (or raw decode error) and emits a
/// structured ErrorClassification entry for the `error_classification`
/// section of the output bundle.
///
/// Classification rules (from docs/notes.md):
///   - TruncatedHeader : raw byte slice is shorter than MIN_RECORD_BYTES
///   - InvalidChecksum : stored checksum does not match computed checksum
///   - OverflowField   : datum_len exceeds the declared segment size
///   - ReservedBitSet  : high nibble of the status byte is non-zero
///   - Unknown         : any other unrecognised malformation
///
/// A record that triggers any of the above categories is classified
/// as Malformed in the compatibility trace; it is not silently
/// normalised and emitted as a compatible record.

use crate::types::{ErrorKind, LegacyRecord};

/// One entry in the error_classification section.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ErrorClassification {
    pub seq_id: u32,
    pub kind: ErrorKind,
    pub detail: String,
}

/// Maximum valid datum_len for a single segment.
pub const MAX_DATUM_LEN: u32 = 0x0FFF_FFFF;

/// Classify a successfully-decoded record for malformation indicators.
/// Returns Some(ErrorClassification) when the record is malformed,
/// or None when the record is structurally sound.
pub fn classify_record(rec: &LegacyRecord, raw_status_byte: u8) -> Option<ErrorClassification> {
    // Check for overflow field first.
    if rec.datum_len > MAX_DATUM_LEN {
        return Some(ErrorClassification {
            seq_id: rec.seq_id,
            kind: ErrorKind::OverflowField,
            detail: format!(
                "datum_len {} exceeds maximum {}",
                rec.datum_len, MAX_DATUM_LEN
            ),
        });
    }

    // Check for non-zero reserved high nibble in the status byte.
    if raw_status_byte & 0xF0 != 0 {
        return Some(ErrorClassification {
            seq_id: rec.seq_id,
            kind: ErrorKind::ReservedBitSet,
            detail: format!(
                "status byte 0x{:02X} has reserved high nibble 0x{:X}",
                raw_status_byte,
                (raw_status_byte >> 4) & 0x0F
            ),
        });
    }

    None
}

/// Classify a decode-level error (buffer too short, etc.).
pub fn classify_decode_error(seq_hint: u32, err: &str) -> ErrorClassification {
    let kind = if err.contains("truncated") {
        ErrorKind::TruncatedHeader
    } else if err.contains("checksum") {
        ErrorKind::InvalidChecksum
    } else {
        ErrorKind::Unknown
    };
    ErrorClassification {
        seq_id: seq_hint,
        kind,
        detail: err.to_string(),
    }
}
