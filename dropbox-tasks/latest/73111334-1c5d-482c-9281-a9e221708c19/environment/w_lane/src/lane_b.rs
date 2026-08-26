use blk_b::tick_b;
use blk_b::{CadenceState, TickErr};

pub fn apply_cadence(state: &mut CadenceState, tick_ix: u64) -> Result<u32, TickErr> {
    tick_b(state, tick_ix)
}
