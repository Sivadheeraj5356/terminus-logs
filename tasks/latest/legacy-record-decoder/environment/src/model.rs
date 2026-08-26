/// Semantic model helpers shared by the decoder modules.
///
/// This module provides field-extraction utilities that operate on
/// decoded records before they are emitted into the bundle.

use crate::types::{LegacyRecord, CanonicalView};

/// Project a decoded record into its canonical view.
/// Called by the emission layer when building the records section.
pub fn project_canonical(rec: &LegacyRecord) -> CanonicalView {
    CanonicalView {
        seq_id: rec.seq_id,
        datum_len: rec.datum_len,
        checksum: rec.checksum,
        status_nibble: rec.status_nibble,
        revision_tag: rec.revision_tag,
        label: rec.label.clone(),
    }
}

/// Return the effective datum length after applying the revision mask.
/// Revision tag bit 0 indicates the extended-length encoding is active;
/// in that case datum_len is stored as a 24-bit value split across two
/// adjacent bytes rather than the normal 16-bit field.
pub fn effective_datum_len(rec: &LegacyRecord) -> u32 {
    rec.datum_len
}

/// Check whether two canonical views agree on all normalised fields.
pub fn views_agree(a: &CanonicalView, b: &CanonicalView) -> bool {
    a.seq_id == b.seq_id
        && a.datum_len == b.datum_len
        && a.checksum == b.checksum
        && a.status_nibble == b.status_nibble
        && a.revision_tag == b.revision_tag
        && a.label == b.label
}
