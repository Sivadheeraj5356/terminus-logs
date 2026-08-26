mod client;
mod invoke;
mod output;

use clap::{Parser, Subcommand};
use hx05::enact::StatePaths;

#[derive(clap::Args, Clone, Copy)]
struct OutputOpts {
    #[arg(long)]
    json: bool,
}

#[derive(Parser)]
#[command(name = "nxctl")]
struct Cli {
    #[arg(long, default_value = "/app/state")]
    state_dir: std::path::PathBuf,
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Validate(OutputOpts),
    Apply(OutputOpts),
    Recover(OutputOpts),
    Cleanup(OutputOpts),
    Status(OutputOpts),
    Inspect(OutputOpts),
    Simulate {
        #[command(flatten)]
        out: OutputOpts,
        #[arg(long)]
        packet: std::path::PathBuf,
        #[arg(long, default_value_t = 1)]
        repeat: u64,
    },
    ResetDemo(OutputOpts),
}

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}

fn run() -> hx01::Result<()> {
    let cli = Cli::parse();
    let paths = StatePaths::from_state_dir(&cli.state_dir);
    match cli.command {
        Commands::Validate(o) => invoke::validate(&paths, o.json)?,
        Commands::Apply(o) => invoke::apply(&paths, o.json)?,
        Commands::Recover(o) => invoke::recover(&paths, o.json)?,
        Commands::Cleanup(o) => invoke::cleanup(&paths, o.json)?,
        Commands::Status(o) => invoke::status(&paths, o.json)?,
        Commands::Inspect(o) => invoke::inspect(&paths, o.json)?,
        Commands::Simulate { out, packet, repeat } => {
            invoke::simulate(&paths, &packet, repeat, out.json)?
        }
        Commands::ResetDemo(o) => invoke::reset_demo(&paths, o.json)?,
    }
    Ok(())
}
