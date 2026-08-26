use clap::{Parser, Subcommand};
use skirmish::run_adjudicate;
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Parser)]
#[command(name = "skirmish")]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    Adjudicate {
        #[arg(long)]
        scenario: PathBuf,
        #[arg(long)]
        out: PathBuf,
    },
}

fn main() -> ExitCode {
    let cli = Cli::parse();
    match cli.cmd {
        Cmd::Adjudicate { scenario, out } => match run_adjudicate(&scenario, &out) {
            Ok(code) => ExitCode::from(code),
            Err(e) => {
                eprintln!("fatal: {e}");
                ExitCode::from(1)
            }
        },
    }
}
