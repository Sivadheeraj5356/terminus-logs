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
    let latch_val = latch_box;
    let expect = jrnl::expected_claim(&durable, &incoming, durable_stamp);
    let coherent = latch_val == expect;

    let mut targets = Vec::new();
    for (key, a) in &arms {
        let lane = &lanes[a.lane_ref % lanes.len()];
        let seed = bin_seed ^ (a.lane_ref as u64).wrapping_mul(23);
        let base = jrnl::local_fold(lane.step_ix, lane.family_ix, seed);
        let acc = gauge::combine_arm(a.gate_first, base);
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
    }
    let wit_hx = format!("{wit_acc:016x}");
    let json = to_json(pin, &emitted, mag, viol, &wit_hx);
    if let Some(parent) = out.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let _ = fs::write(out, json);
}
