mod driver_core;

use driver_core::{health_ping, run_matrix_engine, GridCfg};
use std::env;
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = env::args().collect();
    let env_root = PathBuf::from("/app/environment");
    let mut witness_out = PathBuf::from("/app/output/rule_witness.json");
    let mut all_arms = false;
    let mut arm_filter = None;
    let mut band_filter = None;

    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--all-arms" => all_arms = true,
            "--witness-out" => {
                i += 1;
                witness_out = PathBuf::from(&args[i]);
            }
            "--arm" => {
                i += 1;
                arm_filter = Some(args[i].clone());
            }
            "--band" => {
                i += 1;
                band_filter = Some(args[i].clone());
            }
            "health" => {
                std::process::exit(health_ping(&env_root));
            }
            _ => {}
        }
        i += 1;
    }

    let cfg = GridCfg {
        env_root,
        witness_out,
        all_arms,
        arm_filter,
        band_filter,
    };
    let code = run_matrix_engine(&cfg);
    std::process::exit(code);
}
