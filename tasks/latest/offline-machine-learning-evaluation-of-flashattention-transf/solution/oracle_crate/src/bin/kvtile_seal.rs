use anyhow::{bail, Result};
use kvtile_residency::internal::{app_root, residency_ledger_hook};
use kvtile_residency::ledger::ResidencyLedger;
use kvtile_residency::profile::load_profile;
use kvtile_residency::seal::run_seal;
use std::process::ExitCode;

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("{e:#}");
            if e.to_string().contains("no resident pages") {
                ExitCode::from(2)
            } else {
                ExitCode::from(1)
            }
        }
    }
}

fn run() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let mut seq_id = None;
    let mut out = app_root::join_str("output/kvtile-residency-seal.json");
    let mut profile = app_root::join_str("config/attn-profile.json");
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--seq-id" => {
                i += 1;
                seq_id = Some(args.get(i).cloned().ok_or_else(|| anyhow::anyhow!("missing seq"))?);
            }
            "--out" => {
                i += 1;
                out = args.get(i).cloned().ok_or_else(|| anyhow::anyhow!("missing out"))?;
            }
            "--profile" => {
                i += 1;
                profile = args.get(i).cloned().ok_or_else(|| anyhow::anyhow!("missing profile"))?;
            }
            _ => bail!("unknown arg {}", args[i]),
        }
        i += 1;
    }
    let seq_id = seq_id.ok_or_else(|| anyhow::anyhow!("need --seq-id"))?;
    let profile = load_profile(&profile)?;
    let path = residency_ledger_hook::path_default();
    let ledger = ResidencyLedger::load(&path)?;
    run_seal(&ledger, &profile, &seq_id, &out)?;
    Ok(())
}
