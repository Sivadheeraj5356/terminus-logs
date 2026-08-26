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
use std::io::Write;
use std::path::PathBuf;

use clap::Parser;

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

fn atomic_write(path: &PathBuf, contents: &str) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("mkdir: {e}"))?;
    }
    let tmp = path.with_extension("tmp");
    let mut file = fs::File::create(&tmp).map_err(|e| format!("tmp create: {e}"))?;
    file.write_all(contents.as_bytes())
        .map_err(|e| format!("tmp write: {e}"))?;
    file.sync_all().map_err(|e| format!("tmp sync: {e}"))?;
    fs::rename(&tmp, path).map_err(|e| format!("rename: {e}"))
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
            if atomic_write(&args.out, &format!("{raw}\n")).is_err() {
                let _ = fs::remove_file(&args.out);
                eprintln!("write failed");
                std::process::exit(1);
            }
        }
        Err(e) => {
            eprintln!("audit: {e}");
            let _ = fs::remove_file(&args.out);
            std::process::exit(1);
        }
    }
}
