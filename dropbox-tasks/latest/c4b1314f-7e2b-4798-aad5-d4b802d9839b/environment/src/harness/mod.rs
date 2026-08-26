mod model;
mod out_lane;
mod tick_lane;

use model::{Bundle, CaseRec, TryRec};

use std::fs;
use std::io::Write;
use crate::ceil_cell;
use crate::reload_lane;
use crate::types::{Ctx, G, RowIn, S, Zin};

pub fn drive() -> Result<(), String> {
    fs::create_dir_all("/app/output").map_err(|e| e.to_string())?;
    reload_lane::span_boot();
    let spec = crate::rotation_spec::load()?;
    let g = G::unit();
    let mut ctx = Ctx::new();
    let mut cases: Vec<CaseRec> = Vec::new();

    {
        reload_lane::span_boot();
        let cfg = &spec.cold_tick;
        ceil_cell::ceil_store(0);
        let mut blk_marks: Vec<u64> = Vec::new();
        tick_lane::tick_only(&mut ctx, cfg.bump_a, cfg.bump_b).map_err(|e| format!("{e:?}"))?;
        blk_marks.push(ceil_cell::ceil_load());
        let mut s = S::new(0);
        let tok = tick_lane::link_only(&mut s, cfg.bind_p, ceil_cell::ceil_load());
        let gate = gate_profile(cfg.gate_slice);
        let v = out_lane::consult_only(&gate, &tok, Zin { key: cfg.consult_key });
        cases.push(CaseRec {
            tag: "cold_tick".to_string(),
            blk_marks,
            tries: vec![TryRec {
                wire_tag: cfg.wire_tag.clone(),
                carry_at_try: tok.carry,
                latch_denied: v.latch_denied,
                key: cfg.consult_key,
            }],
        });
        reload_lane::span_save();
    }

    {
        reload_lane::span_boot();
        let cfg = &spec.link_ticks;
        ceil_cell::ceil_store(0);
        ctx = Ctx::new();
        let mut blk_marks: Vec<u64> = Vec::new();
        for bump in &cfg.bumps {
            tick_lane::tick_only(&mut ctx, bump[0], bump[1]).map_err(|e| format!("{e:?}"))?;
            blk_marks.push(ceil_cell::ceil_load());
        }
        let mut s = S::new(0);
        let tok = tick_lane::link_only(&mut s, cfg.bind_p, ceil_cell::ceil_load());
        let v = out_lane::consult_only(&g, &tok, Zin { key: cfg.consult_key });
        cases.push(CaseRec {
            tag: "link_ticks".to_string(),
            blk_marks,
            tries: vec![TryRec {
                wire_tag: cfg.wire_tag.clone(),
                carry_at_try: tok.carry,
                latch_denied: v.latch_denied,
                key: cfg.consult_key,
            }],
        });
        reload_lane::span_save();
    }

    {
        reload_lane::span_boot();
        let cfg = &spec.rotate_hold;
        ceil_cell::ceil_store(0);
        ctx = Ctx::new();
        let mut blk_marks: Vec<u64> = Vec::new();
        let mut s = S::new(cfg.bind_seed);
        let held = tick_lane::link_only(&mut s, cfg.bind_p, ceil_cell::ceil_load());
        tick_lane::tick_only(&mut ctx, cfg.promo_a, cfg.promo_b).map_err(|e| format!("{e:?}"))?;
        blk_marks.push(ceil_cell::ceil_load());
        let v = out_lane::consult_only(&g, &held, Zin { key: cfg.consult_key });
        cases.push(CaseRec {
            tag: "rotate_hold".to_string(),
            blk_marks,
            tries: vec![TryRec {
                wire_tag: cfg.wire_tag.clone(),
                carry_at_try: held.carry,
                latch_denied: v.latch_denied,
                key: cfg.consult_key,
            }],
        });
        reload_lane::span_save();
    }

    {
        reload_lane::span_boot();
        ceil_cell::ceil_store(0);
        ctx = Ctx::new();
        let mut blk_marks: Vec<u64> = Vec::new();
        let mut s1 = S::new(0);
        let mut s2 = S::new(0);
        let mut tries = Vec::new();
        let t1a = tick_lane::link_only(&mut s1, 11, ceil_cell::ceil_load());
        tick_lane::tick_only(&mut ctx, 2, 2).map_err(|e| format!("{e:?}"))?;
        blk_marks.push(ceil_cell::ceil_load());
        let t2a = tick_lane::link_only(&mut s2, 13, ceil_cell::ceil_load());
        let v1 = out_lane::consult_only(&g, &t1a, Zin { key: 8 });
        tries.push(TryRec {
            wire_tag: "a1".to_string(),
            carry_at_try: t1a.carry,
            latch_denied: v1.latch_denied,
            key: 8,
        });
        tick_lane::tick_only(&mut ctx, 6, 1).map_err(|e| format!("{e:?}"))?;
        blk_marks.push(ceil_cell::ceil_load());
        let t1b = tick_lane::link_only(&mut s1, 11, ceil_cell::ceil_load());
        let v2 = out_lane::consult_only(&g, &t2a, Zin { key: 9 });
        tries.push(TryRec {
            wire_tag: "a2".to_string(),
            carry_at_try: t2a.carry,
            latch_denied: v2.latch_denied,
            key: 9,
        });
        let v3 = out_lane::consult_only(&g, &t1b, Zin { key: 8 });
        tries.push(TryRec {
            wire_tag: "a1b".to_string(),
            carry_at_try: t1b.carry,
            latch_denied: v3.latch_denied,
            key: 8,
        });
        cases.push(CaseRec {
            tag: "twin_leaf".to_string(),
            blk_marks,
            tries,
        });
        reload_lane::span_save();
    }

    let bundle = Bundle { cases: cases.clone() };
    let mut f = fs::File::create("/app/output/trace.json").map_err(|e| e.to_string())?;
    f.write_all(
        serde_json::to_string_pretty(&bundle)
            .map_err(|e| e.to_string())?
            .as_bytes(),
    )
    .map_err(|e| e.to_string())?;

    let mut csv = String::from("tag,latch_denied\n");
    for c in &cases {
        let last = c.tries.last().expect("try");
        let view = crate::types::View {
            pulled: last.latch_denied,
        };
        let rin = RowIn {
            tag_code: tag_hash(&c.tag),
            text_a: !last.latch_denied,
            text_b: false,
        };
        let row = out_lane::row_only(&view, &rin);
        csv.push_str(&format!("{},{}\n", c.tag, row.latch_denied));
    }
    fs::write("/app/output/readout.csv", csv).map_err(|e| e.to_string())?;
    Ok(())
}

fn tag_hash(tag: &str) -> u32 {
    tag.bytes().fold(0u32, |a, b| a.wrapping_mul(31).wrapping_add(u32::from(b)))
}

fn gate_profile(slice0: u8) -> G {
    let mut g = G::unit();
    g.slice[0] = slice0;
    g
}

/// Isolated cold_tick promotion: returns the sole blk_marks sample after one bump pair.
pub fn probe_cold_tick_vol(a: u64, b: u64) -> Result<u64, String> {
    ceil_cell::ceil_store(0);
    let mut ctx = Ctx::new();
    tick_lane::tick_only(&mut ctx, a, b).map_err(|e| format!("{e:?}"))?;
    Ok(ceil_cell::ceil_load())
}

/// Isolated link_ticks promotion cadence: returns the final blk_marks sample after the bump chain.
pub fn probe_link_ticks_final_vol(bumps: &[(u64, u64)]) -> Result<u64, String> {
    let ticks = probe_over_gen_samples(bumps)?;
    ticks.last().copied().ok_or_else(|| "no vol ticks".to_string())
}

/// Records blk_marks after each bump in an link_ticks-style chain.
pub fn probe_over_gen_samples(bumps: &[(u64, u64)]) -> Result<Vec<u64>, String> {
    ceil_cell::ceil_store(0);
    let mut ctx = Ctx::new();
    let mut ticks = Vec::new();
    for &(a, b) in bumps {
        tick_lane::tick_only(&mut ctx, a, b).map_err(|e| format!("{e:?}"))?;
        ticks.push(ceil_cell::ceil_load());
    }
    Ok(ticks)
}

/// Bind after a single bump; when bind_q is zero the live sequence value is used as q.
pub fn probe_link_carry(
    bump_a: u64,
    bump_b: u64,
    seed: u64,
    p: u32,
    bind_q: u64,
) -> Result<u64, String> {
    ceil_cell::ceil_store(0);
    let mut ctx = Ctx::new();
    tick_lane::tick_only(&mut ctx, bump_a, bump_b).map_err(|e| format!("{e:?}"))?;
    let vol = ceil_cell::ceil_load();
    let q = if bind_q == 0 { vol } else { bind_q };
    let mut s = S::new(seed);
    let tok = tick_lane::link_only(&mut s, p, q);
    Ok(tok.carry)
}

pub fn probe_consult_latch_denied(carry: u64, key: u32, gate_slice: u8) -> Result<bool, String> {
    let g = gate_profile(gate_slice);
    let tok = crate::types::BindToken { carry };
    let v = out_lane::consult_only(&g, &tok, Zin { key });
    Ok(v.latch_denied)
}

pub fn probe_row_latch_denied(pulled: bool, text_a: bool, text_b: bool) -> Result<bool, String> {
    let view = crate::types::View { pulled };
    let rin = RowIn {
        tag_code: 1,
        text_a,
        text_b,
    };
    Ok(out_lane::row_only(&view, &rin).latch_denied)
}

pub fn probe_rotate_hold() -> Result<(u64, u64), String> {
    ceil_cell::ceil_store(0);
    let mut ctx = Ctx::new();
    let mut s = S::new(7);
    let held = tick_lane::link_only(&mut s, 7, ceil_cell::ceil_load());
    tick_lane::tick_only(&mut ctx, 40, 2).map_err(|e| format!("{e:?}"))?;
    let vol = ceil_cell::ceil_load();
    Ok((vol, held.carry))
}

pub fn probe_dual_first_carry_vs_peak() -> Result<(u64, u64), String> {
    ceil_cell::ceil_store(0);
    let mut ctx = Ctx::new();
    let mut s1 = S::new(0);
    let t1a = tick_lane::link_only(&mut s1, 11, ceil_cell::ceil_load());
    tick_lane::tick_only(&mut ctx, 2, 2).map_err(|e| format!("{e:?}"))?;
    Ok((t1a.carry, ceil_cell::ceil_load()))
}

/// Frame probe: two bump chains separated by span_save/span_boot must not inherit peaks.
pub fn probe_frame_chain_pair(
    first: &[(u64, u64)],
    second: &[(u64, u64)],
) -> Result<(Vec<u64>, Vec<u64>), String> {
    reload_lane::lane_clear();
    let mut ctx = Ctx::new();
    let mut ticks_a = Vec::new();
    for &(a, b) in first {
        tick_lane::tick_only(&mut ctx, a, b).map_err(|e| format!("{e:?}"))?;
        ticks_a.push(ceil_cell::ceil_load());
    }
    reload_lane::span_save();
    reload_lane::span_boot();
    ctx = Ctx::new();
    let mut ticks_b = Vec::new();
    for &(a, b) in second {
        tick_lane::tick_only(&mut ctx, a, b).map_err(|e| format!("{e:?}"))?;
        ticks_b.push(ceil_cell::ceil_load());
    }
    Ok((ticks_a, ticks_b))
}
