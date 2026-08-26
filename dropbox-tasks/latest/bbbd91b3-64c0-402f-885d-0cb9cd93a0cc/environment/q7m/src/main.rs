use q7m::cli;
use std::env;
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 4 || args[1] != "run-seq" || args[2] != "--script" {
        eprintln!("usage: q7m run-seq --script <path> [--out <path>]");
        std::process::exit(2);
    }
    let script = PathBuf::from(&args[3]);
    let out = if args.len() >= 6 && args[4] == "--out" {
        PathBuf::from(&args[5])
    } else {
        PathBuf::from("/app/output/event_trace.jsonl")
    };
    if let Err(e) = cli::run_seq(&script, &out) {
        eprintln!("{e}");
        std::process::exit(1);
    }
}
