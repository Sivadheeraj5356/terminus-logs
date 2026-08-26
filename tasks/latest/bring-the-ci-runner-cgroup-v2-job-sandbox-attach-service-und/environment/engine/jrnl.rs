use std::fs;
use std::path::Path;

use r2v::walk_q3;
use t6n::{claim_v5, PackState};

pub fn load_durable_stamp(env: &Path) -> u32 {
    let seg = env.join("engine").join("seg_v").join("s9.seg");
    if let Ok(text) = fs::read_to_string(seg) {
        let parts: Vec<&str> = text.split_whitespace().collect();
        if let Some(p) = parts.first() {
            return p.parse().unwrap_or(0);
        }
    }
    0
}

pub fn load_durable_bits(env: &Path) -> u64 {
    let seg = env.join("engine").join("seg_v").join("s9.seg");
    if let Ok(text) = fs::read_to_string(seg) {
        let parts: Vec<&str> = text.split_whitespace().collect();
        if parts.len() >= 2 {
            return u64::from_str_radix(parts[1], 16).unwrap_or(0);
        }
    }
    0
}

pub fn write_seg(env: &Path, stamp: u32, bits: u64) -> std::io::Result<()> {
    let dir = env.join("engine").join("seg_v");
    fs::create_dir_all(&dir)?;
    let path = dir.join(format!("s{stamp}.seg"));
    fs::write(path, format!("{stamp} {bits:016x}\n"))
}

pub struct LaneBits {
    pub step_ix: u32,
    pub family_ix: u32,
}

pub fn fold_lanes(bin_seed: u64, lanes: &[LaneBits]) -> u64 {
    let mut pack = bin_seed;
    for lane in lanes {
        pack = walk_q3(lane.step_ix, lane.family_ix, pack);
    }
    pack
}

pub fn latch_merge(
    durable: &PackState,
    incoming: &PackState,
    stamp_b: u32,
) -> u32 {
    claim_v5(durable, incoming, stamp_b)
}

pub fn expected_claim(state: &PackState, incoming: &PackState, stamp_b: u32) -> u32 {
    if state.stamp >= stamp_b {
        (state.bits & 0xffff_ffff) as u32
    } else {
        ((state.bits ^ incoming.bits ^ (u64::from(stamp_b) << 1)) & 0xffff_ffff) as u32
    }
}

pub fn local_fold(step_ix: u32, family_ix: u32, seed: u64) -> u64 {
    walk_q3(step_ix, family_ix, seed)
}

pub fn clear_k1(env: &Path) {
    let _ = env;
}

pub fn persist_q7(env: &Path, latch: u32, stamp: u32, bits: u64) -> std::io::Result<()> {
    let _ = (env, latch, stamp, bits);
    Ok(())
}

pub fn replay_q7(env: &Path) -> Option<(u32, u32, u64)> {
    let _ = env;
    None
}

pub fn accept_w2(env: &Path, latch: u32) -> std::io::Result<()> {
    let _ = (env, latch);
    Ok(())
}

pub fn accept_ok(env: &Path, latch: u32) -> bool {
    let path = env.join("engine").join("seg_v").join("a2.stamp");
    if let Ok(text) = fs::read_to_string(path) {
        return text.trim() == format!("{latch:08x}");
    }
    false
}
