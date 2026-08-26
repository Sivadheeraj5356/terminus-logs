#!/bin/bash
set -euo pipefail

sync_hier() {
  cat > "/app/environment/r2v/mod_a.rs" <<'RS'
mod scan_help;

pub fn walk_q3(step_ix: u32, family_ix: u32, prev: u64) -> u64 {
    let step_term = (step_ix as u64).wrapping_mul(149);
    let family_term = (family_ix as u64).wrapping_mul(23);
    let tag = step_term ^ family_term;
    let rot_l = prev.rotate_left(2);
    let rot_r = prev.rotate_right(7);
    let mut mixed = rot_l ^ tag;
    mixed ^= rot_r;
    if prev == 0 {
        mixed ^= 0x9e37_79b9_7f4a_7c15;
    }
    mixed
}
RS
}

sync_claim() {
  cat > "/app/environment/t6n/mod_b.rs" <<'RS'
mod hist_help;

#[derive(Clone, Copy, Debug)]
pub struct PackState {
    pub bits: u64,
    pub stamp: u32,
}

impl PackState {
    pub fn new(bits: u64, stamp: u32) -> Self {
        Self { bits, stamp }
    }
}

pub fn claim_v5(pack: &PackState, incoming: &PackState, stamp_b: u32) -> u32 {
    let durable_mask = (pack.bits & 0xffff_ffff) as u32;
    let runtime_mask = (incoming.bits & 0xffff_ffff) as u32;
    let durable_wins = pack.stamp >= stamp_b;
    if durable_wins {
        return durable_mask;
    }
    let stamp_mix = (u64::from(stamp_b) << 1) & 0xffff_ffff_ffff_ffff;
    let merged = pack.bits ^ incoming.bits ^ stamp_mix;
    let out = (merged & 0xffff_ffff) as u32;
    if runtime_mask == out && stamp_b == 0 {
        return out;
    }
    out
}
RS
}

sync_nest() {
  cat > "/app/environment/u9p/mod_c.rs" <<'RS'
mod list_help;

pub fn stamp_n8(gate_first: bool, side: impl FnOnce(), gate: impl FnOnce()) -> u32 {
    if gate_first {
        gate();
        side();
        1
    } else {
        side();
        gate();
        0
    }
}
RS
}

sync_emit() {
  cat > "/app/environment/w3h/mod_d.rs" <<'RS'
mod hash_help;

#[derive(Clone, Debug)]
pub struct TargetRow {
    pub arm_key: String,
    pub pack_bits: u64,
    pub latch_val: u32,
    pub base_v: f64,
    pub held_flag: bool,
    pub gate_first: bool,
}

#[derive(Clone, Debug)]
pub struct SeedBundle {
    pub pin: i32,
    pub lane_count: i32,
    pub bin_seed: u64,
}

#[derive(Clone, Debug)]
pub struct StampWitness {
    pub fold_seed: u64,
    pub coherent: bool,
}

#[derive(Clone, Debug)]
pub struct EmittedRow {
    pub arm_key: String,
    pub vec_core: Vec<String>,
    pub bag_a: Vec<i32>,
    pub bag_b: Vec<i32>,
    pub mag: f64,
    pub lane_n: i32,
    pub emit_hx: String,
    pub held: f64,
    pub band_lo: f64,
    pub band_hi: f64,
    pub res_delta: f64,
}

fn slot_vec(pack_bits: u64) -> Vec<i32> {
    let mut bag = Vec::with_capacity(4);
    for i in 0..4 {
        bag.push(((pack_bits >> (i * 8)) & 0xff) as i32);
    }
    bag
}

fn fold_key(key: &str) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for b in key.as_bytes() {
        h ^= u64::from(*b);
        h = h.wrapping_mul(0x0100_0000_01b3);
    }
    h
}

pub fn fold_z1(targets: &[TargetRow], seeds: &SeedBundle, witness: &StampWitness) -> Vec<EmittedRow> {
    let mut out = Vec::new();
    for t in targets {
        let held_xor: u64 = if t.held_flag { 0xC3C3 } else { 0 };
        let hx = fold_key(&t.arm_key)
            ^ t.pack_bits
            ^ u64::from(t.latch_val)
            ^ held_xor
            ^ witness.fold_seed
            ^ seeds.bin_seed;
        let emit_hx = format!("{hx:016x}");
        let bag_a = slot_vec(t.pack_bits);
        let bag_b = if witness.coherent {
            bag_a.clone()
        } else {
            let mut b = Vec::with_capacity(bag_a.len());
            for i in 0..bag_a.len() {
                b.push(bag_a[(i + 1) % bag_a.len()]);
            }
            b
        };
        let vec_core: Vec<String> = bag_a.iter().map(|v| format!("{v:02x}")).collect();
        let res = ((t.pack_bits & 0xffff) as f64) / 65536.0 - t.base_v;
        out.push(EmittedRow {
            arm_key: t.arm_key.clone(),
            vec_core,
            bag_a,
            bag_b,
            mag: res.abs(),
            lane_n: seeds.lane_count,
            emit_hx,
            held: if t.held_flag { 1.0 } else { 0.0 },
            band_lo: -1.0,
            band_hi: 1.0,
            res_delta: res,
        });
    }
    out
}
RS
}

sync_jrnl() {
  cat > "/app/environment/engine/jrnl.rs" <<'RS'
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
    let dir = env.join("engine").join("seg_v");
    let _ = fs::remove_file(dir.join("c7.jrnl"));
    let _ = fs::remove_file(dir.join("a2.stamp"));
}

pub fn persist_q7(env: &Path, latch: u32, stamp: u32, bits: u64) -> std::io::Result<()> {
    let dir = env.join("engine").join("seg_v");
    fs::create_dir_all(&dir)?;
    let path = dir.join("c7.jrnl");
    fs::write(path, format!("lat {latch:08x} {stamp} {bits:016x}\n"))
}

pub fn replay_q7(env: &Path) -> Option<(u32, u32, u64)> {
    let path = env.join("engine").join("seg_v").join("c7.jrnl");
    let text = fs::read_to_string(path).ok()?;
    let parts: Vec<&str> = text.split_whitespace().collect();
    if parts.len() < 4 || parts[0] != "lat" {
        return None;
    }
    let latch = u32::from_str_radix(parts[1], 16).ok()?;
    let stamp = parts[2].parse().ok()?;
    let bits = u64::from_str_radix(parts[3], 16).ok()?;
    Some((latch, stamp, bits))
}

pub fn accept_w2(env: &Path, latch: u32) -> std::io::Result<()> {
    let dir = env.join("engine").join("seg_v");
    fs::create_dir_all(&dir)?;
    fs::write(dir.join("a2.stamp"), format!("{latch:08x}\n"))
}

pub fn accept_ok(env: &Path, latch: u32) -> bool {
    let path = env.join("engine").join("seg_v").join("a2.stamp");
    if let Ok(text) = fs::read_to_string(path) {
        return text.trim() == format!("{latch:08x}");
    }
    false
}
RS
}

sync_orch() {
  cat > "/app/environment/engine/orch.rs" <<'RS'
pub mod gauge;
mod jrnl;

use std::fs;
use std::path::Path;

use t6n::PackState;
use w3h::{SeedBundle, StampWitness, TargetRow};

pub use gauge::steady_label;

pub fn seq_h4(gate_first: bool, side: impl FnOnce(), gate: impl FnOnce()) -> u32 {
    if gate_first {
        gate();
        side();
        1
    } else {
        side();
        gate();
        0
    }
}

struct AnnexLane {
    lane_id: String,
    step_ix: u32,
    family_ix: u32,
    base_v: f64,
}

struct ArmSpec {
    held: bool,
    gate_first: bool,
    lane_ref: usize,
}

fn distinct_lanes(lanes: &[AnnexLane]) -> i32 {
    let mut seen = Vec::new();
    for l in lanes {
        if !seen.contains(&l.lane_id) {
            seen.push(l.lane_id.clone());
        }
    }
    seen.len() as i32
}

fn read_annex(path: &Path) -> Vec<AnnexLane> {
    let text = fs::read_to_string(path).unwrap_or_default();
    let mut out = Vec::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let lane_id = extract_str(line, "lane_id").unwrap_or_default();
        let step_ix = extract_u32(line, "step_ix").unwrap_or(0);
        let family_ix = extract_u32(line, "family_ix").unwrap_or(0);
        let base_v = extract_f64(line, "base_v").unwrap_or(0.0);
        out.push(AnnexLane {
            lane_id,
            step_ix,
            family_ix,
            base_v,
        });
    }
    out
}

fn read_arms(path: &Path) -> Vec<(String, ArmSpec)> {
    let text = fs::read_to_string(path).unwrap_or_default();
    let mut out = Vec::new();
    for chunk in text.split("[[arm]]").skip(1) {
        let key = extract_toml_str(chunk, "key").unwrap_or_default();
        let held = extract_toml_bool(chunk, "held").unwrap_or(false);
        let gate_first = extract_toml_bool(chunk, "gate_first").unwrap_or(false);
        let lane_ref = extract_toml_u32(chunk, "lane_ref").unwrap_or(0) as usize;
        out.push((
            key,
            ArmSpec {
                held,
                gate_first,
                lane_ref,
            },
        ));
    }
    out
}

fn extract_str(line: &str, key: &str) -> Option<String> {
    let pat = format!("\"{key}\"");
    let idx = line.find(&pat)?;
    let rest = &line[idx + pat.len()..];
    let colon = rest.find(':')?;
    let rest = rest[colon + 1..].trim();
    if rest.starts_with('"') {
        let end = rest[1..].find('"')?;
        Some(rest[1..1 + end].to_string())
    } else {
        None
    }
}

fn extract_u32(line: &str, key: &str) -> Option<u32> {
    let pat = format!("\"{key}\"");
    let idx = line.find(&pat)?;
    let rest = &line[idx + pat.len()..];
    let colon = rest.find(':')?;
    let rest = rest[colon + 1..].trim();
    let num: String = rest
        .chars()
        .take_while(|c| c.is_ascii_digit())
        .collect();
    num.parse().ok()
}

fn extract_f64(line: &str, key: &str) -> Option<f64> {
    let pat = format!("\"{key}\"");
    let idx = line.find(&pat)?;
    let rest = &line[idx + pat.len()..];
    let colon = rest.find(':')?;
    let rest = rest[colon + 1..].trim();
    let num: String = rest
        .chars()
        .take_while(|c| c.is_ascii_digit() || *c == '.' || *c == '-')
        .collect();
    num.parse().ok()
}

fn extract_toml_str(chunk: &str, key: &str) -> Option<String> {
    for line in chunk.lines() {
        let line = line.trim();
        if let Some(rest) = line.strip_prefix(key) {
            let rest = rest.trim().trim_start_matches('=').trim();
            if rest.starts_with('"') {
                let end = rest[1..].find('"')?;
                return Some(rest[1..1 + end].to_string());
            }
        }
    }
    None
}

fn extract_toml_bool(chunk: &str, key: &str) -> Option<bool> {
    for line in chunk.lines() {
        let line = line.trim();
        if let Some(rest) = line.strip_prefix(key) {
            let rest = rest.trim().trim_start_matches('=').trim();
            return Some(rest == "true");
        }
    }
    None
}

fn extract_toml_u32(chunk: &str, key: &str) -> Option<u32> {
    for line in chunk.lines() {
        let line = line.trim();
        if let Some(rest) = line.strip_prefix(key) {
            let rest = rest.trim().trim_start_matches('=').trim();
            return rest.parse().ok();
        }
    }
    None
}

fn to_json(pin: i32, rows: &[w3h::EmittedRow], mag: f64, viol: i32, wit_hx: &str) -> String {
    let mut s = String::new();
    s.push_str("{\n");
    s.push_str(&format!("  \"pin\": {pin},\n"));
    s.push_str("  \"rows\": [\n");
    for (i, r) in rows.iter().enumerate() {
        s.push_str("    {\n");
        s.push_str(&format!("      \"arm_key\": \"{}\",\n", r.arm_key));
        s.push_str("      \"vec_core\": [");
        for (j, v) in r.vec_core.iter().enumerate() {
            if j > 0 {
                s.push_str(", ");
            }
            s.push_str(&format!("\"{v}\""));
        }
        s.push_str("],\n");
        s.push_str("      \"bag_a\": [");
        for (j, v) in r.bag_a.iter().enumerate() {
            if j > 0 {
                s.push_str(", ");
            }
            s.push_str(&format!("{v}"));
        }
        s.push_str("],\n");
        s.push_str("      \"bag_b\": [");
        for (j, v) in r.bag_b.iter().enumerate() {
            if j > 0 {
                s.push_str(", ");
            }
            s.push_str(&format!("{v}"));
        }
        s.push_str("],\n");
        s.push_str(&format!("      \"mag\": {mag:.12},\n"));
        s.push_str(&format!("      \"lane_n\": {},\n", r.lane_n));
        s.push_str(&format!("      \"emit_hx\": \"{}\",\n", r.emit_hx));
        s.push_str(&format!("      \"held\": {:.12},\n", r.held));
        s.push_str(&format!("      \"band_lo\": {:.12},\n", r.band_lo));
        s.push_str(&format!("      \"band_hi\": {:.12},\n", r.band_hi));
        s.push_str(&format!("      \"res_delta\": {:.12}\n", r.res_delta));
        if i + 1 == rows.len() {
            s.push_str("    }\n");
        } else {
            s.push_str("    },\n");
        }
    }
    s.push_str("  ],\n");
    s.push_str("  \"summary\": {\n");
    s.push_str("    \"label\": \"protocol\",\n");
    s.push_str(&format!("    \"n_rows\": {},\n", rows.len()));
    s.push_str(&format!("    \"wit_hx\": \"{wit_hx}\",\n"));
    s.push_str(&format!("    \"viol\": {viol}\n"));
    s.push_str("  }\n");
    s.push_str("}\n");
    s
}

pub fn run_pipeline(pin: i32, env: &Path, out: &Path) {
    jrnl::clear_k1(env);

    let annex = env.join("fixtures").join("fx_h49.jsonl");
    let arms_path = env.join("fixtures").join("arm_tbl.toml");
    let bin_path = env.join("fixtures").join("hier").join("tc.bin");
    let bin = fs::read(&bin_path).unwrap_or_default();
    let mut bin_seed: u64 = 0;
    for b in bin {
        bin_seed = bin_seed.wrapping_mul(149) ^ u64::from(b);
    }

    let lanes = read_annex(&annex);
    let arms = read_arms(&arms_path);
    let durable_stamp = jrnl::load_durable_stamp(env);
    let durable_bits = jrnl::load_durable_bits(env);
    let durable = PackState::new(durable_bits, durable_stamp);

    let lane_bits: Vec<jrnl::LaneBits> = lanes
        .iter()
        .map(|l| jrnl::LaneBits {
            step_ix: l.step_ix,
            family_ix: l.family_ix,
        })
        .collect();
    let pack_final = jrnl::fold_lanes(bin_seed, &lane_bits);
    let incoming = PackState::new(pack_final, durable_stamp.wrapping_add(lanes.len() as u32));

    let mut latch_box = 0u32;
    let ds = durable_stamp;
    let db = durable_bits;
    seq_h4(
        true,
        || {
            latch_box = jrnl::latch_merge(&durable, &incoming, ds);
        },
        || {
            let bits = if db != 0 { db } else { pack_final };
            let _ = jrnl::write_seg(env, ds.max(1), bits);
        },
    );

    let _ = jrnl::persist_q7(env, latch_box, ds, db);
    let (latch_val, _, _) = match jrnl::replay_q7(env) {
        Some(v) => v,
        None => (latch_box, ds, db),
    };
    let expect = jrnl::expected_claim(&durable, &incoming, durable_stamp);
    let coherent = latch_val == expect;

    let mut targets = Vec::new();
    let mut prev_pack: u64 = 0;
    for (key, a) in &arms {
        let lane = &lanes[a.lane_ref % lanes.len()];
        let seed = bin_seed ^ (a.lane_ref as u64).wrapping_mul(23);
        let base = jrnl::local_fold(lane.step_ix, lane.family_ix, seed);
        let acc = gauge::combine_arm(a.gate_first, base ^ prev_pack);
        prev_pack = acc;
        targets.push(TargetRow {
            arm_key: key.clone(),
            pack_bits: acc,
            latch_val,
            base_v: lane.base_v,
            held_flag: a.held,
            gate_first: a.gate_first,
        });
    }

    let seeds = SeedBundle {
        pin,
        lane_count: distinct_lanes(&lanes),
        bin_seed,
    };
    let wit = StampWitness {
        fold_seed: u64::from(durable_stamp) ^ durable_bits ^ bin_seed,
        coherent,
    };
    let mut emitted = gauge::emit_rows(&targets, &seeds, &wit);

    let mut mag = 0.0f64;
    for er in &emitted {
        mag = mag.max(er.res_delta.abs());
    }
    for er in &mut emitted {
        er.mag = mag;
    }

    let mut wit_acc: u64 = 0;
    let mut viol = 0i32;
    for er in &emitted {
        if let Ok(v) = u64::from_str_radix(&er.emit_hx, 16) {
            wit_acc ^= v;
        }
        if er.res_delta.abs() > 1.0 {
            viol += 1;
        }
        if coherent && er.bag_a != er.bag_b {
            viol += 1;
        }
        if !coherent && er.bag_a == er.bag_b {
            viol += 1;
        }
    }
    let wit_hx = format!("{wit_acc:016x}");
    let json = to_json(pin, &emitted, mag, viol, &wit_hx);
    if let Some(parent) = out.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let _ = fs::write(out, json);
    let _ = jrnl::accept_w2(env, latch_val);
}
RS
}

# Rematerialize attach-path packing, durable claim, nest combine, emit,
# latch-journal persist/replay, temporal arm chain, and accept stamp.
sync_hier
sync_claim
sync_nest
sync_emit
sync_jrnl
sync_orch

export PATH="/usr/local/cargo/bin:/opt/verifier/bin:${PATH}"
bash "/app/environment/k4m/build_wrap.sh" "/app/environment" /app/bin/cg_xmit
/app/bin/cg_xmit run --pin 49 --env "/app/environment" --out /app/output/protocol_transcript.json
