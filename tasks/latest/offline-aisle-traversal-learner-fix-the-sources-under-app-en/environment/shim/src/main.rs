mod parse_r;
mod pack_t;
mod write_u;

use std::env;
use std::path::PathBuf;
use std::process;

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut fixtures = PathBuf::from("/app/fixtures");
    let mut spec = PathBuf::from("/app/spec");
    let mut out = PathBuf::from("/app/output/coverage_map.json");
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--fixtures" => {
                i += 1;
                if i < args.len() {
                    fixtures = PathBuf::from(&args[i]);
                }
            }
            "--spec" => {
                i += 1;
                if i < args.len() {
                    spec = PathBuf::from(&args[i]);
                }
            }
            "--out" => {
                i += 1;
                if i < args.len() {
                    out = PathBuf::from(&args[i]);
                }
            }
            "-h" | "--help" => {
                eprintln!(
                    "usage: lane_matrix --fixtures DIR --spec DIR --out FILE"
                );
                process::exit(0);
            }
            other => {
                eprintln!("unknown arg: {}", other);
                process::exit(2);
            }
        }
        i += 1;
    }

    let rows = match pack_t::load_rows(&fixtures, &spec) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("load failed: {}", e);
            process::exit(1);
        }
    };
    if let Err(e) = write_u::write_u(&out, &rows) {
        eprintln!("write failed: {}", e);
        process::exit(1);
    }
}
