use k9_desk::engine;
use k9_desk::sk8_gateway;
use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
    let mut scenario = 0u32;
    let args: Vec<String> = env::args().collect();
    let mut idx = 1;
    while idx < args.len() {
        if args[idx] == "--scenario" && idx + 1 < args.len() {
            scenario = args[idx + 1].parse().unwrap_or(0);
            idx += 2;
        } else {
            idx += 1;
        }
    }
    let state_dir = PathBuf::from("/app/desk-state");
    let _ = fs::create_dir_all(&state_dir);
    let rows = engine::desk_run_scenario(scenario, &state_dir);
    sk8_gateway::save_epoch_cache(scenario, &rows, &state_dir);
}
