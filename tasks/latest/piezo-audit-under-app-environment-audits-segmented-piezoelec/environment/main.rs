mod probe;
mod calib;
mod weight;
mod folio;
mod seal;
mod state;
mod cache;
mod workflow;
mod pipeline;
mod emit;
mod types;

use std::fs;
use std::path::PathBuf;

use clap::Parser;

use crate::state::manifest::manifest_path;

#[derive(Parser)]
#[command(name = "piezo-audit")]
struct Args {
    #[arg(long)]
    chip: Vec<PathBuf>,
    #[arg(long, default_value = "2099-12-31")]
    as_of: String,
    #[arg(long)]
    out: PathBuf,
}

fn main() {
    let args = Args::parse();
    if args.chip.is_empty() {
        eprintln!("at least one --chip required");
        std::process::exit(1);
    }
    match pipeline::run::audit_paths(&args.chip, &args.as_of) {
        Ok(report) => {
            let raw = serde_json::to_string_pretty(&report).unwrap();
            if let Some(parent) = args.out.parent() {
                let _ = fs::create_dir_all(parent);
            }
            if fs::write(&args.out, format!("{raw}\n")).is_err() {
                eprintln!("write failed");
                std::process::exit(1);
            }
        }
        Err(e) => {
            eprintln!("audit: {e}");
            let _ = fs::remove_file(&args.out);
            let _ = fs::remove_file(manifest_path());
            std::process::exit(1);
        }
    }
}
