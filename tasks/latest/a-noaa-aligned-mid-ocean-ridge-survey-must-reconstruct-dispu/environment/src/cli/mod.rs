use clap::{Args, Subcommand};
use std::path::PathBuf;

#[derive(Subcommand, Debug)]
pub enum Command {
    IngestDiveLog(IngestArgs),
    ResolvePrecedence(ResolveArgs),
    ReconcileObservations(ReconcileArgs),
    ExportAtlas(ExportArgs),
}

#[derive(Args, Debug)]
pub struct IngestArgs {
    #[arg(long)]
    pub bundle: PathBuf,
    #[arg(long, default_value = "/app/data/policies/default.json")]
    pub policy: PathBuf,
    #[arg(long)]
    pub staging: PathBuf,
}

#[derive(Args, Debug)]
pub struct ResolveArgs {
    #[arg(long)]
    pub staging: PathBuf,
    #[arg(long)]
    pub output: PathBuf,
}

#[derive(Args, Debug)]
pub struct ReconcileArgs {
    #[arg(long)]
    pub resolved: PathBuf,
    #[arg(long)]
    pub output: PathBuf,
}

#[derive(Args, Debug)]
pub struct ExportArgs {
    #[arg(long)]
    pub observations: PathBuf,
    #[arg(long, default_value = "/app/data/policies/default.json")]
    pub policy: PathBuf,
    #[arg(long)]
    pub atlas: PathBuf,
}
