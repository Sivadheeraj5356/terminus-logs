/// Shared record type definitions for the decoder library.
///
/// A LegacyRecord represents a single logical entry read from either
/// a binary dump or a text export.  The canonical view is the
/// normalised form that both surfaces align on after decoding.

#[derive(Debug, Clone, PartialEq)]
pub struct LegacyRecord {
    /// Sequential record identifier, 1-based.
    pub seq_id: u32,
    /// Primary payload field – raw byte count of the data region.
    pub datum_len: u32,
    /// Secondary payload field – checksum word stored in the record.
    pub checksum: u16,
    /// Status nibble stored in the header byte.
    pub status_nibble: u8,
    /// Revision tag embedded in the control byte.
    pub revision_tag: u8,
    /// Optional label present when the record carries metadata.
    pub label: Option<String>,
}

/// Canonical view used for round-trip comparison and bundle emission.
/// Field names here align with the JSON keys tested by the verifier.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct CanonicalView {
    pub seq_id: u32,
    pub datum_len: u32,
    pub checksum: u16,
    pub status_nibble: u8,
    pub revision_tag: u8,
    pub label: Option<String>,
}

impl From<LegacyRecord> for CanonicalView {
    fn from(r: LegacyRecord) -> Self {
        CanonicalView {
            seq_id: r.seq_id,
            datum_len: r.datum_len,
            checksum: r.checksum,
            status_nibble: r.status_nibble,
            revision_tag: r.revision_tag,
            label: r.label,
        }
    }
}

/// Compatibility state for a record pair (binary vs text).
#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum CompatState {
    Compatible,
    Diverged,
    Malformed,
}

/// Error kind for a malformed record.
#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ErrorKind {
    TruncatedHeader,
    InvalidChecksum,
    OverflowField,
    ReservedBitSet,
    Unknown,
}
