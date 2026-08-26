/// Alternate compatibility path (not wired into the active decoder).
///
/// Structural mirror of b1.rs; not called by the live trace builder.

use crate::types::{CanonicalView, CompatState};

#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct AltTrace {
    pub seq_id: u32,
    pub state: CompatState,
}

#[allow(dead_code)]
pub fn compare_alt(a: &CanonicalView, b: &CanonicalView) -> AltTrace {
    let state = if a.seq_id == b.seq_id
        && a.datum_len == b.datum_len
        && a.checksum == b.checksum
    {
        CompatState::Compatible
    } else {
        CompatState::Diverged
    };
    AltTrace { seq_id: a.seq_id, state }
}
