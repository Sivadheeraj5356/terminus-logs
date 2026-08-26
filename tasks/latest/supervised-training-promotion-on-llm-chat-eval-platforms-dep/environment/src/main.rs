#[path = "ctxhold/wc_ctxhold.rs"]
mod ctxhold;
#[path = "turnclock/wc_turnclock.rs"]
mod turnclock;
#[path = "causechain/wc_causechain.rs"]
mod causechain;
#[path = "featmetrics/wc_featmetrics.rs"]
mod featmetrics;
#[path = "freezeout/wc_freezeout.rs"]
mod freezeout;
#[path = "decoy/wc_tokendiag.rs"]
mod tokendiag;

use std::path::PathBuf;
use std::process;

use anyhow::Result;
use clap::{Parser, Subcommand};

use freezeout::freeze_emit::{absorb_hold, emit_bulletin, score_and_freeze};

#[derive(Parser)]
#[command(name = "wincontam", version, about = "Contamination-aware chat-eval metric and inference feature scoring")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    AbsorbContextHold {
        #[arg(long)]
        corpus: PathBuf,
        #[arg(long)]
        store: PathBuf,
    },
    ScoreContamWindow {
        #[arg(long)]
        corpus: PathBuf,
        #[arg(long)]
        store: PathBuf,
        #[arg(long)]
        cutoff: String,
        #[arg(long)]
        emitted_at: String,
        #[arg(long)]
        out: PathBuf,
    },
    EmitRiskBulletin {
        #[arg(long)]
        corpus: PathBuf,
        #[arg(long)]
        store: PathBuf,
        #[arg(long)]
        cutoff: String,
        #[arg(long)]
        emitted_at: String,
        #[arg(long)]
        out: PathBuf,
    },
}

fn main() {
    if let Err(err) = run() {
        eprintln!("{err:#}");
        process::exit(1);
    }
}

fn run() -> Result<()> {
    let _ = tokendiag::board_label();
    let cli = Cli::parse();
    match cli.command {
        Commands::AbsorbContextHold { corpus, store } => absorb_hold(&corpus, &store),
        Commands::ScoreContamWindow {
            corpus,
            store,
            cutoff,
            emitted_at,
            out,
        } => score_and_freeze(&corpus, &store, &cutoff, &emitted_at, &out),
        Commands::EmitRiskBulletin {
            corpus,
            store,
            cutoff,
            emitted_at,
            out,
        } => emit_bulletin(&corpus, &store, &cutoff, &emitted_at, &out),
    }
}
