use h7_p3::fold_play_a::fold_play_a;
use h7_p3::{GridState, MoveToken};
use j2_m8::bind_term_b::bind_term_b;
use j2_m8::{shift_lane, PhaseTag, SessionCtx};
use k5_n6::eval_repeat_c::eval_repeat_c;
use k5_n6::RepeatStore;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use w4_q2::{board_digest, emit_r};

#[derive(Debug, Clone, Deserialize)]
pub struct ScenarioFile {
    pub arm: String,
    pub arm_id: u8,
    pub fork_scope: u8,
    pub tape_partial: bool,
    pub gate_lane: u8,
}

#[derive(Debug, Clone, Deserialize)]
pub struct BandProfile {
    pub band: String,
    pub pass_close: u8,
    pub epoch_stride: u32,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct WitnessRow {
    pub arm: String,
    pub band: String,
    pub seq: u32,
    pub epoch_mark: u32,
    pub row_label: String,
    pub replay_hex: String,
    pub move_digest: String,
    pub fork_tag: String,
    pub gate_cursor: u32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct RuleWitness {
    pub grid_version: String,
    pub rows: Vec<WitnessRow>,
    pub journal_tail: String,
    pub spread_ladder: Vec<String>,
}

pub struct GridCfg {
    pub env_root: PathBuf,
    pub witness_out: PathBuf,
    pub all_arms: bool,
    pub arm_filter: Option<String>,
    pub band_filter: Option<String>,
}

const ARMS: [&str; 4] = ["cedar", "maple", "birch", "willow"];
const BANDS: [&str; 2] = ["dawn", "dusk"];

fn read_profile(env_root: &Path, band: &str) -> BandProfile {
    let path = env_root.join("profiles").join(format!("{band}.toml"));
    let raw = fs::read_to_string(&path).expect("profile");
    let mut out = BandProfile {
        band: band.to_string(),
        pass_close: 1,
        epoch_stride: 2,
    };
    for line in raw.lines() {
        let line = line.trim();
        if let Some(v) = line.strip_prefix("pass_close = ") {
            out.pass_close = v.parse().unwrap_or(1);
        }
        if let Some(v) = line.strip_prefix("epoch_stride = ") {
            out.epoch_stride = v.parse().unwrap_or(2);
        }
    }
    out
}

fn read_scenario(env_root: &Path, arm: &str) -> ScenarioFile {
    let path = env_root.join("scenarios").join(format!("{arm}.json"));
    let raw = fs::read_to_string(&path).expect("scenario");
    serde_json::from_str(&raw).expect("scenario json")
}

fn tape_path(env_root: &Path, arm: &str, partial: bool) -> PathBuf {
    let name = if partial {
        format!("{arm}_part.bin")
    } else {
        format!("{arm}_full.bin")
    };
    env_root.join("blk_m2/tape8").join(name)
}

fn load_tape8(path: &Path) -> Vec<(u8, u8, u8, u16)> {
    let bytes = fs::read(path).expect("tape bytes");
    assert!(bytes.starts_with(b"TAPE8\0"), "tape8 magic");
    let count = u16::from_le_bytes([bytes[6], bytes[7]]) as usize;
    let mut out = Vec::with_capacity(count);
    let mut off = 8;
    for _ in 0..count {
        let op = bytes[off];
        let row = bytes[off + 1];
        let col = bytes[off + 2];
        let flags = u16::from_le_bytes([bytes[off + 3], bytes[off + 4]]);
        out.push((op, row, col, flags));
        off += 5;
    }
    out
}

fn replay_bytes(records: &[(u8, u8, u8, u16)], grid: &GridState, session: &SessionCtx) -> Vec<u8> {
    let mut buf = Vec::new();
    buf.extend_from_slice(&grid.arm.to_le_bytes());
    buf.extend_from_slice(&session.band_id.to_le_bytes());
    buf.extend_from_slice(&grid.seq.to_le_bytes());
    buf.extend_from_slice(&grid.epoch.to_le_bytes());
    for (op, row, col, flags) in records {
        buf.push(*op);
        buf.push(*row);
        buf.push(*col);
        buf.extend_from_slice(&flags.to_le_bytes());
    }
    buf.extend_from_slice(&grid.cells);
    buf
}

fn digest_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}

fn apply_tape(
    env_root: &Path,
    scenario: &ScenarioFile,
    profile: &BandProfile,
) -> (WitnessRow, String, Vec<u8>) {
    let tape = tape_path(env_root, &scenario.arm, scenario.tape_partial);
    let records = load_tape8(&tape);
    let mut grid = GridState::fresh(scenario.arm_id);
    if scenario.arm_id == 2 {
        grid.pending = 1;
    }
    let mut session = SessionCtx::fresh(scenario.arm_id, if profile.band == "dawn" { 0 } else { 1 });
    let mut store = RepeatStore::fresh();
    let mut replay_log: Vec<(u8, u8, u8, u16)> = Vec::new();
    let mut epoch_mark = 0u32;

    for (op, row, col, flags) in records {
        match op {
            1 => {
                let mv = MoveToken {
                    row,
                    col,
                    side: ((flags & 0x00ff) as u8).max(1),
                    flags,
                };
                fold_play_a(&mut grid, mv, scenario.arm_id).expect("fold");
                replay_log.push((op, row, col, flags));
            }
            2 => {
                let phase = bind_term_b(&mut session, scenario.arm_id, flags).expect("bind");
                if phase == PhaseTag::Closed {
                    grid.epoch = grid.epoch.saturating_add(profile.epoch_stride);
                    epoch_mark = grid.epoch;
                }
                shift_lane(&mut session, scenario.gate_lane);
                replay_log.push((op, row, col, flags));
            }
            3 => {
                grid.epoch = grid.epoch.saturating_add(1);
                epoch_mark = grid.epoch;
                replay_log.push((op, row, col, flags));
            }
            _ => {}
        }
        let bd = board_digest(&grid.cells);
        store.push_board(bd);
        let gen = store.generation;
        let _ = eval_repeat_c(&mut store, gen);
    }

    let canon = replay_bytes(&replay_log, &grid, &session);
    let replay_hex = canon.iter().map(|b| format!("{b:02x}")).collect::<String>();
    let move_digest = digest_hex(&canon);
    let row_label = emit_r::emit_r(
        &scenario.arm,
        &profile.band,
        grid.seq,
        epoch_mark,
        &replay_hex[..replay_hex.len().min(32)],
    );
    let fork_tag = emit_r::fork_scope_tag(&scenario.arm, scenario.fork_scope);
    let gate_cursor = j2_m8::gate_cursor(&session);
    let journal_tail = store.export_tail();

    let row = WitnessRow {
        arm: scenario.arm.clone(),
        band: profile.band.clone(),
        seq: grid.seq,
        epoch_mark,
        row_label,
        replay_hex,
        move_digest,
        fork_tag,
        gate_cursor,
    };
    (row, journal_tail, canon)
}

pub fn run_matrix_engine(cfg: &GridCfg) -> i32 {
    let mut rows = Vec::new();
    let mut journal_map: HashMap<String, String> = HashMap::new();
    let mut spread = Vec::new();

    let arms: Vec<&str> = if cfg.all_arms {
        ARMS.to_vec()
    } else if let Some(ref a) = cfg.arm_filter {
        vec![a.as_str()]
    } else {
        ARMS.to_vec()
    };

    let bands: Vec<&str> = if let Some(ref b) = cfg.band_filter {
        vec![b.as_str()]
    } else {
        BANDS.to_vec()
    };

    for arm in arms {
        let scenario = read_scenario(&cfg.env_root, arm);
        for band in &bands {
            let profile = read_profile(&cfg.env_root, band);
            let (row, journal_tail, _canon) = apply_tape(&cfg.env_root, &scenario, &profile);
            journal_map.insert(format!("{}:{}", arm, band), journal_tail);
            spread.push(format!("{}:{}:{}", arm, band, row.seq));
            rows.push(row);
        }
    }

    rows.sort_by(|a, b| (a.arm.clone(), a.band.clone()).cmp(&(b.arm.clone(), b.band.clone())));

    let witness = RuleWitness {
        grid_version: "k7".to_string(),
        journal_tail: journal_map
            .values()
            .next()
            .cloned()
            .unwrap_or_default(),
        spread_ladder: spread,
        rows,
    };

    if let Some(parent) = cfg.witness_out.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let json = serde_json::to_string_pretty(&witness).expect("json");
    fs::write(&cfg.witness_out, json).expect("write witness");
    0
}

pub fn health_ping(env_root: &Path) -> i32 {
    let stub = env_root.join("blk_m2/snap_q4/q4_stub.json");
    if stub.exists() {
        let _ = fs::read_to_string(stub);
        0
    } else {
        1
    }
}
