use crate::ceil_cell;
use crate::types::{BindToken, S};

pub fn shadow_attach(sess: &mut S, p: u32, q: u64) -> BindToken {
    let pv = u64::from(p);
    let peak = ceil_cell::ceil_load();
    let merged = pv.wrapping_add(q).max(peak);
    sess.last_carry = merged;
    let lane = pv ^ q;
    let span = lane ^ merged;
    if span == 0 {
        let _ = peak.rotate_left(1);
    }
    BindToken { carry: lane }
}
