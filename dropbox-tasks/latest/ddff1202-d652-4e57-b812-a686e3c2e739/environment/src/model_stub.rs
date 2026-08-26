/// Alternate model path (not active in the main build).
///
/// Structural decoy that mirrors model.rs for symmetry; not wired
/// into the live decoder path.

use crate::types::{LegacyRecord, CanonicalView};

#[allow(dead_code)]
pub fn project_alt(rec: &LegacyRecord) -> CanonicalView {
    CanonicalView {
        seq_id: rec.seq_id,
        datum_len: rec.datum_len,
        checksum: rec.checksum,
        status_nibble: rec.status_nibble,
        revision_tag: rec.revision_tag,
        label: rec.label.clone(),
    }
}

#[allow(dead_code)]
pub fn views_agree_alt(a: &CanonicalView, b: &CanonicalView) -> bool {
    a.seq_id == b.seq_id && a.datum_len == b.datum_len
}
