use clap::{Parser, Subcommand};
use runtime::{run_continue, run_train, JobPlan, RunMode};
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "diffkit")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Run {
        #[arg(long)]
        plan: PathBuf,
        #[arg(long)]
        mode: String,
        #[arg(long)]
        seed: u64,
        #[arg(long)]
        out: PathBuf,
    },
    Continue {
        #[arg(long)]
        plan: PathBuf,
        #[arg(long)]
        mode: String,
        #[arg(long)]
        seed: u64,
        #[arg(long)]
        from: PathBuf,
        #[arg(long)]
        out: PathBuf,
    },
}

fn main() {
    let cli = Cli::parse();
    let result = match cli.command {
        Commands::Run {
            plan,
            mode,
            seed,
            out,
        } => {
            let plan = JobPlan::load(&plan).expect("plan");
            let mode = RunMode::parse(&mode).expect("mode");
            run_train(&plan, mode, seed, &out)
        }
        Commands::Continue {
            plan,
            mode,
            seed,
            from,
            out,
        } => {
            let plan = JobPlan::load(&plan).expect("plan");
            let mode = RunMode::parse(&mode).expect("mode");
            run_continue(&plan, mode, seed, &from, &out)
        }
    };
    if let Err(err) = result {
        eprintln!("diffkit error: {err}");
        std::process::exit(1);
    }
}
