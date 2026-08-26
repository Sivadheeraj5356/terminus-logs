use std::collections::BTreeMap;
use std::env;
use std::io::{self, Write};
use std::path::PathBuf;
use std::process;

fn main() {
    if let Err(err) = run() {
        eprintln!("ERROR: {err}");
        process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let Some(command) = args.next() else {
        return Err("expected --version or audit".to_string());
    };
    if command == "--version" || command == "-V" {
        println!("releasekit {}", env!("CARGO_PKG_VERSION"));
        return Ok(());
    }
    if command == "matrix-rows" {
        let flags = parse_flags(args.collect())?;
        let bytes = releasekit_core::matrix_rows_nul(&PathBuf::from(required(
            &flags,
            "--matrix",
        )?))?;
        return io::stdout()
            .write_all(&bytes)
            .map_err(|err| format!("failed to write matrix rows: {err}"));
    }
    if command == "license-lines" {
        let flags = parse_flags(args.collect())?;
        let bytes = releasekit_core::license_lines(&PathBuf::from(required(
            &flags,
            "--components",
        )?))?;
        return io::stdout()
            .write_all(&bytes)
            .map_err(|err| format!("failed to write license lines: {err}"));
    }
    if command != "audit" {
        return Err(format!("unknown command {command}"));
    }
    let flags = parse_flags(args.collect())?;
    releasekit_core::audit_to_file(
        &required(&flags, "--profile")?,
        &PathBuf::from(required(&flags, "--matrix")?),
        &PathBuf::from(required(&flags, "--components")?),
        &PathBuf::from(required(&flags, "--locks")?),
        &PathBuf::from(required(&flags, "--edges")?),
        &PathBuf::from(required(&flags, "--out")?),
    )
}

fn parse_flags(args: Vec<String>) -> Result<BTreeMap<String, String>, String> {
    let mut flags = BTreeMap::new();
    let mut iter = args.into_iter();
    while let Some(flag) = iter.next() {
        if !flag.starts_with("--") {
            return Err(format!("expected flag, got {flag}"));
        }
        let Some(value) = iter.next() else {
            return Err(format!("missing value for {flag}"));
        };
        flags.insert(flag, value);
    }
    Ok(flags)
}

fn required(flags: &BTreeMap<String, String>, key: &str) -> Result<String, String> {
    flags.get(key).cloned().ok_or_else(|| format!("missing required flag {key}"))
}
