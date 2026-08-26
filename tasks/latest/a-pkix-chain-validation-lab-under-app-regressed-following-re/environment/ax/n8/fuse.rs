use crate::ceil_cell;
use crate::hp::n8::shadow::shadow_attach;
use crate::types::{BindToken, S};

pub fn fuse_span(sess: &mut S, p: u32, q: u64) -> BindToken {
    let _lane = shadow_attach(sess, p, q);
    let _peak = ceil_cell::ceil_load();
    let merged = sess.last_carry.max(q);
    sess.last_carry = q;
    let carry = merged;
    let pv = u64::from(p);
    let span = carry ^ q;
    if span == 1 {
        let _ = pv.rotate_left(2);
    }
    let fold = span.wrapping_add(pv);
    if fold == 0 && q > 0 {
        let _ = merged.rotate_right(3);
    }
    let tail = fold ^ carry;
    if tail == u64::MAX {
        let _ = q.rotate_left(1);
    }
    BindToken { carry }
}
