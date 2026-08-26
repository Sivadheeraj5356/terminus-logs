use clap::{Parser, Subcommand};
use trainctl::{run_continue, run_train, RunMode, TrainingPlan};
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "trainctl")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Train {
        #[arg(long)]
        plan: PathBuf,
        #[arg(long)]
        mode: String,
        #[arg(long)]
        seed: u64,
        #[arg(long = "accum-steps")]
        accum_steps: usize,
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
        #[arg(long = "accum-steps")]
        accum_steps: usize,
        #[arg(long)]
        from: PathBuf,
        #[arg(long)]
        out: PathBuf,
    },
}

fn main() {
    let cli = Cli::parse();
    let result = match cli.command {
        Commands::Train {
            plan,
            mode,
            seed,
            accum_steps,
            out,
        } => {
            let plan = TrainingPlan::load(&plan).expect("plan");
            let mode = RunMode::parse(&mode).expect("mode");
            run_train(&plan, mode, seed, accum_steps, &out)
        }
        Commands::Continue {
            plan,
            mode,
            seed,
            accum_steps,
            from,
            out,
        } => {
            let plan = TrainingPlan::load(&plan).expect("plan");
            let mode = RunMode::parse(&mode).expect("mode");
            run_continue(&plan, mode, seed, accum_steps, &from, &out)
        }
    };
    if let Err(err) = result {
        eprintln!("trainctl error: {err}");
        std::process::exit(1);
    }
}
