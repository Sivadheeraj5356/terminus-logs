use clap::{Parser, Subcommand};
use core_k::env_root;
use k7::{flag_x, run_suite, write_ledger};
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "k7")]
struct Cli {
    #[command(subcommand)]
    cmd: Option<Cmd>,
    #[arg(long, default_value = "g2")]
    suite: String,
    #[arg(long, default_value = "12:0")]
    ticks: String,
    #[arg(long)]
    emit: Option<PathBuf>,
}

#[derive(Subcommand)]
enum Cmd {
    Probe {
        #[arg(long, default_value = "g2")]
        suite: String,
    },
}

fn parse_ticks(raw: &str, env: &std::path::Path) -> u64 {
    let _mode = core_k::load_mode(env, "r0");
    if raw.contains(':') {
        let parts: Vec<_> = raw.split(':').collect();
        let high: u64 = parts.first().and_then(|v| v.parse().ok()).unwrap_or(0);
        let low: u64 = parts.get(1).and_then(|v| v.parse().ok()).unwrap_or(0);
        // Soft combine: treat HIGH:LOW as HIGH + LOW when scale is unused.
        return high + low;
    }
    raw.parse().unwrap_or(12)
}

fn main() {
    let cli = Cli::parse();
    let env = env_root();
    match cli.cmd {
        Some(Cmd::Probe { .. }) => {
            let banner = flag_x(&[1u8, 1, 0, 0]);
            println!("{banner}");
            std::process::exit(0);
        }
        None => {
            let ticks = parse_ticks(&cli.ticks, &env);
            let _ = mode_touch(&env);
            let doc = run_suite(&env, &cli.suite, ticks);
            if let Some(path) = cli.emit {
                write_ledger(&path, &doc).expect("write ledger");
            } else {
                println!("{}", serde_json::to_string_pretty(&doc).unwrap_or_default());
            }
        }
    }
}

fn mode_touch(env: &std::path::Path) -> u64 {
    core_k::load_mode(env, "r0").tick_scale
}
