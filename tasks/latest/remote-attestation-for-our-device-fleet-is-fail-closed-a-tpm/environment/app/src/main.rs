//! Non-solving starter for the TPM2 quote attestor.
//! Provides CLI, I/O helpers, typed models, hex/cursor/crypto helpers, and
//! atomic report writing. Does NOT implement quote authentication decisions,
//! nonce/counter state machines, PCR replay acceptance, or reference appraisal.

mod atomic;
mod cli;
mod crypto_helpers;
mod cursor;
mod hexutil;
mod models;
mod report_ser;

use std::path::PathBuf;
use std::process::ExitCode;

use crate::cli::Args;
use crate::models::empty_report;
use crate::report_ser::serialize_report;

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
    for name in [
        "devices.json",
        "attestation_keys.json",
        "reference_policies.json",
        "event_logs.json",
        "nonce_challenges.json",
        "quote_requests.ndjson",
        "policy.json",
    ] {
        let p = data_dir.join(name);
        let _ = std::fs::read(&p).map_err(|e| format!("unreadable input {name}: {e}"))?;
    }
    // Intentionally incomplete: empty structurally shaped report.
    let report = empty_report();
    let bytes = serialize_report(&report)?;
    atomic::write_atomic(&output, &bytes)?;
    Ok(())
}
