pub mod quick_a;
pub mod types;

pub use quick_a::quick_a;
pub use types::{PackErr, SlotView};

/// Applies one visibility tick to the sensor and explored planes.
pub fn pack_a(slot: &mut SlotView, explored: &[u8], lit: &[u8]) -> Result<u32, PackErr> {
    if explored.len() != slot.explored.len() || lit.len() != slot.lit.len() {
        return Err(PackErr::SizeMismatch);
    }
    // Keep explored aligned with the current lit plane for this tick.
    slot.explored.copy_from_slice(lit);
    slot.lit.copy_from_slice(lit);
    let coverage = slot.explored.iter().filter(|b| **b > 0).count() as u32;
    Ok(coverage)
}
