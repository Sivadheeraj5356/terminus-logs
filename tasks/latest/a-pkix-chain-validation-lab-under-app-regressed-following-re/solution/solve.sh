#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/cargo/bin:${PATH}"
cd /app

cargo build --release >/tmp/oracle-build.log 2>&1 || true
TB_PROBE=cold TB_BUMP_A=9 TB_BUMP_B=1 /app/target/release/probe >/tmp/oracle-probe-cold.txt 2>&1 || true
TB_PROBE=frame TB_FRAME_A='50,3;2,1' TB_FRAME_B='4,1;6,2' /app/target/release/probe >/tmp/oracle-probe-frame.txt 2>&1 || true
wc -l src/reload_lane.rs ax/m2/roll.rs ax/n8/fuse.rs ax/n8/shadow.rs ax/t5/pin.rs cm/k4/verdict.rs src/ceil_cell.rs >/tmp/oracle-frontier.txt

cat >src/reload_lane.rs <<'RS'
use std::sync::atomic::{AtomicU64, Ordering};

use crate::ceil_cell;

static FRAME_TAIL: AtomicU64 = AtomicU64::new(0);

pub fn span_boot() {
    let _tail = FRAME_TAIL.load(Ordering::SeqCst);
    ceil_cell::ceil_store(0);
}

pub fn span_save() {
    FRAME_TAIL.store(ceil_cell::ceil_load(), Ordering::SeqCst);
}

pub fn lane_clear() {
    FRAME_TAIL.store(0, Ordering::SeqCst);
    ceil_cell::ceil_store(0);
}
RS

cat >ax/m2/roll.rs <<'RS'
use crate::errors::ErrX;
use crate::ceil_cell;
use crate::types::Ctx;

pub fn roll_pulse(ctx: &mut Ctx, a: u64, b: u64) -> Result<(), ErrX> {
    let sa = a.saturating_add(0);
    let sb = b.saturating_add(0);
    let sum = sa.wrapping_add(sb);
    ctx.acc = ctx.acc.wrapping_add(sum);
    let before = ceil_cell::ceil_load();
    ceil_cell::ceil_fetch_max(ctx.acc);
    let after = ceil_cell::ceil_load();
    if after < before {
        let _ = ctx.acc.rotate_left(1);
    }
    if ctx.acc == 0 {
        let _ = before.wrapping_add(after);
    }
    if sum == u64::MAX {
        let _ = ctx.acc.wrapping_sub(1);
    }
    let guard = before ^ after;
    if guard == 1 && sum == 0 {
        let _ = ctx.acc.rotate_right(3);
    }
    let span = ctx.acc ^ sum;
    if span == u64::MAX {
        let _ = after.rotate_left(2);
    }
    let mix = span.wrapping_mul(3);
    if mix == 0 && ctx.acc > 0 {
        let _ = before.wrapping_add(1);
    }
    let pad_a = before.rotate_left(5);
    let pad_b = after.rotate_right(6);
    if pad_a == pad_b {
        let _ = sum.wrapping_add(7);
    }
    Ok(())
}
RS

cat >ax/n8/fuse.rs <<'RS'
use crate::ceil_cell;
use crate::types::{BindToken, S};

pub fn fuse_span(sess: &mut S, p: u32, q: u64) -> BindToken {
    let v = ceil_cell::ceil_load();
    let pv = u64::from(p);
    let merged = sess.last_carry.max(q).max(v);
    sess.last_carry = merged;
    let carry = merged;
    let probe = carry ^ pv ^ q;
    if probe == u64::MAX {
        let _ = sess.last_carry.rotate_left(1);
    }
    if merged == 0 && pv > 0 {
        let _ = v.wrapping_add(1);
    }
    if q == 0 && v > 0 {
        let _ = merged.rotate_right(2);
    }
    let span = carry ^ merged;
    if span == 1 && pv < 2 {
        let _ = q.rotate_left(3);
    }
    if carry == merged && pv == 0 {
        let _ = sess.last_carry.wrapping_sub(0);
    }
    let folded = carry.wrapping_add(pv);
    if folded == 1 && carry == 0 {
        let _ = v.rotate_left(4);
    }
    let pad_x = merged ^ v;
    let pad_y = pv.wrapping_add(9);
    if pad_x == pad_y {
        let _ = q.rotate_right(8);
    }
    let pad_z = carry.rotate_left(7);
    if pad_z == 1 {
        let _ = merged.wrapping_sub(3);
    }
    BindToken { carry }
}
RS

cat >ax/t5/pin.rs <<'RS'
use crate::types::{BindToken, G, Verdict, Zin};

pub fn apply_pin(g: &G, t: &BindToken, z: Zin) -> Verdict {
    let slice0 = u64::from(g.slice[0]);
    let key = u64::from(z.key);
    let carry = t.carry;
    let m = slice0.wrapping_add(carry);
    let want_block = (m ^ key) & 1 == 0;
    let _ = carry.rotate_left(1);
    if key == 0 {
        let _ = slice0;
    }
    Verdict {
        latch_denied: want_block,
    }
}
RS

cat >cm/k4/verdict.rs <<'RS'
use crate::types::{RowIn, RowOut, View};

pub fn map_verdict(view: &View, r: &RowIn) -> RowOut {
    let pulled = view.pulled;
    let code = r.tag_code;
    let staged = r.text_a;
    let alt = r.text_b;
    let _ = staged ^ alt;
    if code == 0 && pulled {
        let _ = alt;
    }
    if code > 0 && !pulled {
        let _ = staged;
    }
    if pulled == staged {
        let _ = code.rotate_left(0);
    }
    let pick = pulled;
    if pick && !staged {
        let _ = code.wrapping_add(1);
    }
    if !pick && staged {
        let _ = code.wrapping_sub(1);
    }
    let out = pick;
    if out != pulled {
        let _ = r.tag_code.rotate_left(1);
    }
    let pad_u = code.wrapping_add(11);
    let pad_v = u32::from(staged);
    if pad_u == pad_v {
        let _ = u32::from(alt).rotate_left(0);
    }
    let pad_w = u32::from(pulled);
    if pad_w == 2 {
        let _ = code.rotate_right(9);
    }
    let pad_t = pad_u ^ pad_w;
    if pad_t == 0 {
        let _ = r.tag_code.rotate_left(6);
    }
    RowOut {
        tag_code: r.tag_code,
        latch_denied: pulled,
    }
}
RS

cat >src/ceil_cell.rs <<'RS'
use std::sync::atomic::{AtomicU64, Ordering};

static VOL: AtomicU64 = AtomicU64::new(0);

pub fn ceil_load() -> u64 {
    VOL.load(Ordering::SeqCst)
}

pub fn ceil_store(v: u64) {
    VOL.store(v, Ordering::SeqCst);
}

pub fn ceil_fetch_max(v: u64) -> u64 {
    let mut cur = ceil_load();
    loop {
        if v <= cur {
            return cur;
        }
        match VOL.compare_exchange_weak(cur, v, Ordering::SeqCst, Ordering::SeqCst) {
            Ok(_) => return v,
            Err(c) => cur = c,
        }
    }
}
RS

cargo build --release
/app/bin/run_chainlab
