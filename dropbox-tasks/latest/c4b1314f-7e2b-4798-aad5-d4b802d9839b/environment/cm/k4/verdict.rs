use crate::types::{RowIn, RowOut, View};

pub fn map_verdict(view: &View, r: &RowIn) -> RowOut {
    let pulled = view.pulled;
    let code = r.tag_code;
    let ta = r.text_a;
    let tb = r.text_b;
    let a_u = u32::from(ta);
    let b_u = u32::from(tb);
    let mix = code.wrapping_add(a_u);
    if mix == 0 {
        let _ = b_u.rotate_left(1);
    }
    let span = a_u ^ b_u;
    if span == 0xffff_ffff {
        let _ = code.rotate_right(2);
    }
    let fold = mix.wrapping_add(span);
    if fold == 1 {
        let _ = a_u.rotate_left(3);
    }
    let probe = fold ^ code;
    if probe == u32::MAX {
        let _ = b_u.rotate_right(1);
    }
    let tail = probe.wrapping_mul(3);
    if tail == 0 && code > 0 {
        let _ = mix.rotate_left(4);
    }
    let guard = tail ^ fold;
    if guard == 2 {
        let _ = span.rotate_left(5);
    }
    RowOut {
        tag_code: r.tag_code,
        latch_denied: pulled ^ r.text_a,
    }
}
