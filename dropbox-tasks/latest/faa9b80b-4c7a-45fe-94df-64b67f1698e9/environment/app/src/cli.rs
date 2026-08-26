//! CLI argument parsing for lunar-regolith-solver.

use std::env;
use std::path::PathBuf;

pub struct Args {
    pub data_dir: PathBuf,
    pub output: PathBuf,
}

pub fn parse_args() -> Result<Args, String> {
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
            other => return Err(format!("Unrecognized argument: {other}")),
        }
    }

    Ok(Args {
        data_dir: data_dir.unwrap_or_else(|| PathBuf::from("/app/data")),
        output: output.unwrap_or_else(|| PathBuf::from("/app/output/report.json")),
    })
}
