mod hinge;
mod loom;

pub use hinge::fold_v2;
pub use loom::{caption, meta_tag};

/// Journal event kinds packed into the byte stream.
pub const EV_PLACE: u8 = 1;
pub const EV_CLEAR: u8 = 2;

/// Rebuild the digests retained for admission from a packed event stream.
pub fn restore_marks(p: &mut Vec<[u8; 32]>, q: &[u8]) -> usize {
    fold_v2(p, q)
}
