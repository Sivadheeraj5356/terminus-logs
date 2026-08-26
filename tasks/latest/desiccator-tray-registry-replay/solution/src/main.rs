mod config;
mod ops;
mod output;
mod parse;
mod replay;
mod shards;
mod types;

use std::path::PathBuf;

use crate::config::load_config;
use crate::output::write_output;
use crate::replay::replay_shards;
use crate::shards::collect_shards;

fn main() {
    if let Err(code) = run() {
        std::process::exit(code);
    }
}

fn run() -> Result<(), i32> {
    let args: Vec<String> = std::env::args().collect();
    let task_root = match args.len() {
        1 => PathBuf::from("/app/task_file"),
        2 => PathBuf::from(&args[1]),
        _ => return Err(1),
    };
    if !validate_root(&task_root)? {
        return Err(1);
    }
    let cfg = load_config(&task_root.join("trays.json")).map_err(|_| 1)?;
    let shards = collect_shards(&task_root.join("events"))?;
    if shards.is_empty() {
        return Err(1);
    }
    let rep = replay_shards(&cfg, &shards)?;
    write_output(&rep)?;
    Ok(())
}

fn validate_root(root: &PathBuf) -> Result<bool, i32> {
    if !root.join("trays.json").is_file() || !root.join("events").is_dir() {
        return Ok(false);
    }
    Ok(true)
}
