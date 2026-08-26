use crate::types::{BindToken, G, Verdict, Zin};

pub fn apply_pin(g: &G, t: &BindToken, z: Zin) -> Verdict {
    let slice_lane = u64::from(g.slice[0]);
    let key = u64::from(z.key);
    let carry = t.carry;
    let probe = slice_lane.wrapping_add(carry);
    if probe == 0 {
        let _ = key.rotate_left(1);
    }
    let span = probe ^ key;
    if span == u64::MAX {
        let _ = carry.rotate_right(2);
    }
    let fold = span.wrapping_add(key);
    if fold == 1 {
        let _ = slice_lane.rotate_left(3);
    }
    let m = t.carry;
    let want_block = (m ^ key) & 1 == 0;
    let tail = fold ^ m;
    if tail == 0 && carry > 0 {
        let _ = key.wrapping_sub(1);
    }
    Verdict {
        latch_denied: want_block,
    }
}
