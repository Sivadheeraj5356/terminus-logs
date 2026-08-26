use clap::Parser;
use prlg_k4::Store;
use prlg_r6::{drive, load_policy, load_workload_file, resolve_shards, Phase, RunError, RunOpts};
use prlg_w5::emit_f;
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Debug, Parser)]
#[command(name = "relayctl")]
struct Cli {
    #[command(subcommand)]
    cmd: Commands,
}

#[derive(Debug, Parser)]
enum Commands {
    Run(RunArgs),
}

#[derive(Debug, Parser)]
struct RunArgs {
    #[arg(long)]
    policy: PathBuf,
    #[arg(long)]
    root: PathBuf,
    #[arg(long)]
    state: PathBuf,
    #[arg(long, default_value = "0")]
    seed: u64,
    #[arg(long)]
    report: PathBuf,
    #[arg(long)]
    journal: PathBuf,
    #[arg(long)]
    trace: PathBuf,
    #[arg(long, default_value = "all")]
    phase: String,
    #[arg(long)]
    workload_rounds: Option<u32>,
    #[arg(long, default_value = "all")]
    shard_profile: String,
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(RunError::DescriptorBudget) => ExitCode::from(5),
        Err(RunError::EffectiveLimit) => ExitCode::from(7),
        Err(RunError::Export(_)) => ExitCode::from(6),
        Err(RunError::GovernanceNotReady) => ExitCode::from(9),
        Err(RunError::BadPhase) => ExitCode::from(4),
        Err(RunError::WorkloadMismatch) => ExitCode::from(3),
        Err(RunError::Workload(_)) => ExitCode::from(4),
        Err(e) => {
            eprintln!("{e}");
            ExitCode::from(2)
        }
    }
}

fn run() -> Result<(), RunError> {
    let cli = Cli::parse();
    let Commands::Run(args) = cli.cmd;

    let phase = Phase::parse(&args.phase).ok_or(RunError::BadPhase)?;

    let policy = load_policy(args.policy.to_str().unwrap_or_default())?;
    let workload = load_workload_file(args.root.to_str().unwrap_or_default())?;
    let shards = resolve_shards(&policy, &args.shard_profile)?;
    let mut store = Store::open(&args.state)?;

    let output = drive(
        &policy,
        &workload,
        &shards,
        &mut store,
        &args.state,
        RunOpts {
            seed: args.seed,
            phase,
            workload_rounds: args.workload_rounds,
        },
    )?;

    emit_f(
        args.report.to_str().unwrap(),
        args.journal.to_str().unwrap(),
        args.trace.to_str().unwrap(),
        &output.report,
        &output.reclaims,
        &output.trace,
        output.require_full,
    )?;

    Ok(())
}
