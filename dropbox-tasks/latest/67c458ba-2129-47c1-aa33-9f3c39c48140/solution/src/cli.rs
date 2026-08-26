use clap::Parser;
use std::path::PathBuf;

#[derive(Debug, Parser)]
#[command(name = "hospital_analytics")]
pub struct Args {
    #[arg(long, default_value = "/app/data")]
    pub input_dir: PathBuf,

    #[arg(long, default_value = "/app/output/analytics_report.json")]
    pub output: PathBuf,
}
