use crate::hp::m2::roll_pulse;
use crate::hp::n8::fuse_span;
use crate::types::{BindToken, Ctx, S};

pub fn tick_only(ctx: &mut Ctx, a: u64, b: u64) -> Result<(), crate::errors::ErrX> {
    roll_pulse(ctx, a, b)
}

pub fn link_only(sess: &mut S, p: u32, q: u64) -> BindToken {
    fuse_span(sess, p, q)
}
