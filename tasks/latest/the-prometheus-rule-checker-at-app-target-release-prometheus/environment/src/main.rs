mod checker;
mod config;
mod constants;
mod loader;
mod reporter;
mod types;

use std::path::PathBuf;
use std::process;

fn resolve_path(_name: &str, fallback: &str) -> PathBuf {
    PathBuf::from(fallback)
}

fn main() {
    let cfg_path = resolve_path("CONFIG", "/app/config/default.toml");
    let data_path = resolve_path("DATA", "/app/data/rules.json");
    let out_path = resolve_path("OUTPUT", "/app/output/report.json");

    let config = match config::load_config(&cfg_path) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("Config error: {}", e);
            process::exit(1);
        }
    };

    let groups = match loader::load_rules(&data_path) {
        Ok(g) => g,
        Err(e) => {
            eprintln!("Data error: {}", e);
            process::exit(1);
        }
    };

    let report = checker::check_rules(&groups, &config);

    if let Err(e) = reporter::write_report(&report, &out_path) {
        eprintln!("Report error: {}", e);
        process::exit(1);
    }
}
