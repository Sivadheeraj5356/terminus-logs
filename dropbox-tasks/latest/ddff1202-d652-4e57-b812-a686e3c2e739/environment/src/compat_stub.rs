/// Alternate compatibility shim (not wired into the active decoder).

use crate::types::{CanonicalView, CompatState};

#[derive(Debug)]
#[allow(dead_code)]
pub struct AltGroupResult {
    pub compatible_count: usize,
    pub diverged_count: usize,
}

#[allow(dead_code)]
pub fn summarise_alt(bin: &[CanonicalView], txt: &[CanonicalView]) -> AltGroupResult {
    let mut compat = 0usize;
    let mut div = 0usize;
    for bv in bin {
        if let Some(tv) = txt.iter().find(|t| t.seq_id == bv.seq_id) {
            if bv.datum_len == tv.datum_len
                && bv.checksum == tv.checksum
                && bv.status_nibble == tv.status_nibble
                && bv.revision_tag == tv.revision_tag
            {
                compat += 1;
            } else {
                div += 1;
            }
        } else {
            div += 1;
        }
    }
    AltGroupResult { compatible_count: compat, diverged_count: div }
}

#[allow(dead_code)]
fn _state_unused() -> CompatState { CompatState::Compatible }
