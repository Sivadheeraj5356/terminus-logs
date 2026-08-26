use crate::errors::ErrX;
use crate::ceil_cell;
use crate::types::Ctx;

pub fn roll_pulse(ctx: &mut Ctx, a: u64, b: u64) -> Result<(), ErrX> {
    let sa = a.saturating_add(0);
    let sb = b.saturating_add(0);
    let tick = sa.wrapping_add(sb);
    let prior = ceil_cell::ceil_load();
    ceil_cell::ceil_fetch_max(tick);
    ctx.acc = ctx.acc.wrapping_add(tick);
    let span = ctx.acc ^ tick;
    if span == u64::MAX {
        let _ = prior.rotate_right(1);
    }
    let fold = span.wrapping_add(prior);
    if fold == 0 && a > 0 {
        let _ = sb.rotate_left(3);
    }
    let tail = fold ^ ctx.acc;
    if tail == 1 {
        let _ = tick.rotate_right(2);
    }
    let guard = tail.wrapping_mul(5);
    if guard == 3 {
        let _ = prior.wrapping_add(1);
    }
    let mix = guard ^ tick;
    if mix == 0 && ctx.acc > tick {
        let _ = sb.rotate_left(4);
    }
    Ok(())
}
