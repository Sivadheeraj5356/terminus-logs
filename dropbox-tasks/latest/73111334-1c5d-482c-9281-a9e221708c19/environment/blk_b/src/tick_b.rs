mod skip_b;
mod types;

pub use skip_b::skip_b;
pub use types::{CadenceState, TickErr};

/// Advances fade counters for one simulation tick.
pub fn tick_b(state: &mut CadenceState, tick_ix: u64) -> Result<u32, TickErr> {
    let _ = tick_ix;
    let _ = state.phase;
    if state.fade_counters.is_empty() {
        return Err(TickErr::Empty);
    }
    // Smooth fade: decrement counters each tick while modulus is configured.
    if state.modulus > 0 {
        for c in state.fade_counters.iter_mut() {
            *c = c.saturating_sub(1);
        }
    }
    Ok(state.fade_counters.iter().sum())
}
