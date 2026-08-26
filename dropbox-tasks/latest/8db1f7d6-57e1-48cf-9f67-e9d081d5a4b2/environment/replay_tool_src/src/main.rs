mod amount;
mod apply;
mod output;
mod parse;
mod precedence;
mod reject;
mod replay;
mod types;

use std::env;
use std::fs;
use std::path::Path;

use output::write_all;
use parse::{load_buffers, load_events};
use replay::run_replay;
use types::OUT_DIR;

fn run() -> Result<(), ()> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        return Err(());
    }
    let task = Path::new(&args[1]);
    if !task.is_dir() {
        return Err(());
    }

    let mut buffers = load_buffers(task)?;
    let events = load_events(task)?;

    fs::remove_dir_all(OUT_DIR).ok();
    fs::create_dir_all(OUT_DIR).map_err(|_| ())?;

    let replay = run_replay(&mut buffers, events);
    write_all(
        &buffers,
        &replay.audit,
        &replay.rejects,
        replay.duplicate_events,
    )
}

fn main() {
    std::process::exit(if run().is_ok() { 0 } else { 1 });
}
