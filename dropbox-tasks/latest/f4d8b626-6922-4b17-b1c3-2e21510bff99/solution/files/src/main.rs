mod cli;
mod config;
mod export;
mod hash;
mod ingest;
mod precedence;
mod reconcile;

use clap::Parser;

#[derive(Parser, Debug)]
#[command(name = "expeditctl")]
pub struct ExpeditCtlCli {
    #[command(subcommand)]
    pub command: cli::Command,
}

fn main() {
    let cli = ExpeditCtlCli::parse();
    if let Err(code) = run(cli) {
        std::process::exit(code);
    }
}

fn run(cli: ExpeditCtlCli) -> Result<(), i32> {
    match cli.command {
        cli::Command::IngestDiveLog(args) => ingest::run_ingest(&args),
        cli::Command::ResolvePrecedence(args) => precedence::run_resolve(&args),
        cli::Command::ReconcileObservations(args) => reconcile::run_reconcile(&args),
        cli::Command::ExportAtlas(args) => export::run_export(&args),
    }
}
