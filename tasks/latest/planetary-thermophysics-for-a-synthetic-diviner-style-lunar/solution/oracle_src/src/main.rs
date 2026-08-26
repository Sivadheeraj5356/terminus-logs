mod data;
mod error;
mod inversion;
mod radiometry;
mod report;
mod thermal;

use error::SolverError;
use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::ExitCode;

struct Args {
    data_dir: PathBuf,
    output: PathBuf,
}

fn parse_args() -> Result<Args, String> {
    let raw: Vec<String> = env::args().collect();
    let mut data_dir: Option<PathBuf> = None;
    let mut output: Option<PathBuf> = None;

    let mut i = 1;
    while i < raw.len() {
        match raw[i].as_str() {
            "--data-dir" => {
                let value = raw
                    .get(i + 1)
                    .ok_or_else(|| "--data-dir requires a value".to_string())?;
                data_dir = Some(PathBuf::from(value));
                i += 2;
            }
            "--output" => {
                let value = raw
                    .get(i + 1)
                    .ok_or_else(|| "--output requires a value".to_string())?;
                output = Some(PathBuf::from(value));
                i += 2;
            }
            other => {
                return Err(format!("Unrecognized argument: {other}"));
            }
        }
    }

    Ok(Args {
        data_dir: data_dir.unwrap_or_else(data::default_data_dir),
        output: output.ok_or_else(|| "missing required --output <path>".to_string())?,
    })
}

fn run() -> Result<PathBuf, SolverError> {
    let args = parse_args().map_err(SolverError::new)?;
    let tmp_path = args.output.with_extension("tmp");

    // Always start from a clean slate: a stale report (or a leftover tmp
    // file from a previous crashed run) must never be mistaken for a
    // freshly produced one if this run fails partway through.
    let _ = fs::remove_file(&args.output);
    let _ = fs::remove_file(&tmp_path);

    let result = (|| -> Result<Vec<u8>, SolverError> {
        let solver_data = data::load_solver_data(&args.data_dir)?;
        let report = report::build_report(&solver_data)?;

        if report::contains_non_finite(&report) {
            return Err(SolverError::new(
                "solver produced a non-finite value (NaN/Infinity); refusing to emit an invalid report",
            ));
        }

        Ok(serde_json::to_vec_pretty(&report)?)
    })();

    let serialized = match result {
        Ok(bytes) => bytes,
        Err(err) => {
            let _ = fs::remove_file(&tmp_path);
            return Err(err);
        }
    };

    if let Some(parent) = args.output.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)?;
        }
    }

    if let Err(err) = fs::write(&tmp_path, &serialized) {
        let _ = fs::remove_file(&tmp_path);
        return Err(err.into());
    }
    if let Err(err) = fs::rename(&tmp_path, &args.output) {
        let _ = fs::remove_file(&tmp_path);
        return Err(err.into());
    }

    Ok(args.output)
}

fn main() -> ExitCode {
    match run() {
        Ok(path) => {
            println!("Wrote report to {}", path.display());
            ExitCode::SUCCESS
        }
        Err(err) => {
            eprintln!("solver failed: {err}");
            ExitCode::FAILURE
        }
    }
}
