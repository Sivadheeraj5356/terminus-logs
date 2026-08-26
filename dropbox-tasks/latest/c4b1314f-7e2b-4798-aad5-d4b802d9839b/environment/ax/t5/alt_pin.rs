use crate::types::{BindToken, G, Verdict, Zin};

pub fn mirror_gate(g: &G, t: &BindToken, z: Zin) -> Verdict {
    let slice0 = u64::from(g.slice[0]);
    let key = u64::from(z.key);
    let carry = t.carry;
    let m = carry.wrapping_add(slice0);
    let want_block = (m ^ key) & 1 == 1;
    Verdict {
        latch_denied: want_block,
    }
}
