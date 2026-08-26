use anyhow::{bail, Result};
use kvtile_residency::advance::run_advance;
use kvtile_residency::internal::residency_ledger_hook;
use kvtile_residency::ledger::ResidencyLedger;
use kvtile_residency::profile::load_profile;

fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let mut profile = None;
    let mut compact = false;
    let mut release_logicals: Vec<u32> = Vec::new();
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--profile" => {
                i += 1;
                profile = Some(args.get(i).cloned().ok_or_else(|| anyhow::anyhow!("missing profile"))?);
            }
            "--compact" => compact = true,
            "--release-logical" => {
                i += 1;
                let raw = args
                    .get(i)
                    .ok_or_else(|| anyhow::anyhow!("missing --release-logical value"))?;
                release_logicals.push(raw.parse::<u32>()?);
            }
            _ => bail!("unknown arg {}", args[i]),
        }
        i += 1;
    }
    let profile = load_profile(profile.as_deref().ok_or_else(|| anyhow::anyhow!("need --profile"))?)?;
    let path = residency_ledger_hook::path_default();
    let mut ledger = ResidencyLedger::load(&path)?;
    run_advance(&profile, &mut ledger, compact, &release_logicals)?;
    ledger.save(&path)?;
    Ok(())
}
