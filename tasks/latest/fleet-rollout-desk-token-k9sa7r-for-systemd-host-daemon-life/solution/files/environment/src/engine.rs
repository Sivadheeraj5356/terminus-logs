use crate::scan::{self, ScenarioInput};
use crate::wal::{
    self, compute_order_seal, phases_valid, read_chain, write_checkpoint, Checkpoint,
};
use crate::{sr5_gateway, fp3_gateway, sk8_gateway, xr4_gateway};
use serde_json::Value;
use std::fs;
use std::path::Path;

fn scenario_rows(input: &ScenarioInput, state_dir: &Path) -> Vec<Value> {
    let mut rows = Vec::new();
    rows.extend(sk8_gateway::build(input, state_dir));
    rows.extend(fp3_gateway::build(input));
    rows.extend(sr5_gateway::build(input, state_dir));
    rows.extend(xr4_gateway::build(input));
    rows
}

fn seal_checkpoint(state_dir: &Path, scenario_id: u32) {
    let chain = read_chain(state_dir);
    let cp = Checkpoint {
        last_scenario: scenario_id,
        wal_seq: chain.last().map(|r| r.seq).unwrap_or(0),
        order_seal: compute_order_seal(&chain),
        valid: phases_valid(&chain),
    };
    let _ = write_checkpoint(state_dir, &cp);
}

pub fn desk_run_scenario(scenario_id: u32, state_dir: &Path) -> Vec<Value> {
    let _ = fs::create_dir_all(wal::wal_dir(state_dir));
    let count_path = state_dir.join(format!("invoke_{scenario_id}.cnt"));
    let prior: u32 = fs::read_to_string(&count_path)
        .ok()
        .and_then(|t| t.trim().parse().ok())
        .unwrap_or(0);
    let _ = fs::write(&count_path, format!("{}\n", prior + 1));
    let input = scan::parse(scenario_id);
    let rows = scenario_rows(&input, state_dir);
    fp3_gateway::append_wal_steps(state_dir, scenario_id);
    seal_checkpoint(state_dir, scenario_id);
    rows
}

pub fn all_epoch_caches_present(state_dir: &Path, through: u32) -> bool {
    for n in 0..=through {
        if !state_dir.join(format!("epoch_{n}.json")).is_file() {
            return false;
        }
    }
    true
}

pub fn recover_from_wal(state_dir: &Path) -> bool {
    if !wal::wal_crc_chain_intact(state_dir) {
        return false;
    }
    let chain = read_chain(state_dir);
    if chain.is_empty() || !phases_valid(&chain) {
        return false;
    }
    let last_scenario = chain.iter().map(|r| r.scenario).max().unwrap_or(0);
    let cp = Checkpoint {
        last_scenario,
        wal_seq: chain.last().map(|r| r.seq).unwrap_or(0),
        order_seal: compute_order_seal(&chain),
        valid: phases_valid(&chain),
    };
    write_checkpoint(state_dir, &cp).is_ok()
}

pub fn checkpoint_ready(state_dir: &Path) -> bool {
    let chain = read_chain(state_dir);
    if !phases_valid(&chain) {
        return false;
    }
    if !wal::wal_crc_chain_intact(state_dir) {
        return false;
    }
    match wal::read_checkpoint(state_dir) {
        Some(cp) => {
            cp.valid
                && cp.order_seal == compute_order_seal(&chain)
                && cp.wal_seq == chain.last().map(|r| r.seq).unwrap_or(0)
        }
        None => false,
    }
}
