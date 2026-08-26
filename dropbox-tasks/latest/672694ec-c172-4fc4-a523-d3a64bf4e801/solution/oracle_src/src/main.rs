//! Solving Oracle entrypoint.

mod appraise;
mod atomic;
mod cli;
mod crypto_helpers;
mod cursor;
mod engine;
mod hexutil;
mod load;
mod models;
mod quote_parse;
mod report_ser;

use std::path::PathBuf;
use std::process::ExitCode;

use crate::cli::Args;

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            eprintln!("{err}");
            ExitCode::from(1)
        }
    }
}

fn run() -> Result<(), String> {
    let args = Args::parse(std::env::args().skip(1))?;
    let output = PathBuf::from(&args.output);
    crate::atomic::cleanup_output(&output);
    let data_dir = PathBuf::from(&args.data_dir);
    match crate::engine::verify_data_dir(&data_dir) {
        Ok(report) => {
            let bytes = crate::report_ser::serialize_report(&report)?;
            crate::atomic::write_atomic(&output, &bytes)?;
            Ok(())
        }
        Err(e) => {
            crate::atomic::cleanup_output(&output);
            Err(e)
        }
    }
}
