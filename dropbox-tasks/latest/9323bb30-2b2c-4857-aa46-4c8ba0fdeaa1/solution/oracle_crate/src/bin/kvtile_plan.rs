use anyhow::{bail, Result};
use kvtile_residency::internal::{blake3_seal_ring, residency_ledger_hook};
use kvtile_residency::ledger::ResidencyLedger;
use kvtile_residency::pack::load_pack;
use kvtile_residency::plan::run_plan;
use kvtile_residency::profile::load_profile;

fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let mut pack = None;
    let mut profile = None;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--pack" => {
                i += 1;
                pack = Some(args.get(i).cloned().ok_or_else(|| anyhow::anyhow!("missing pack"))?);
            }
            "--profile" => {
                i += 1;
                profile = Some(args.get(i).cloned().ok_or_else(|| anyhow::anyhow!("missing profile"))?);
            }
            _ => bail!("unknown arg {}", args[i]),
        }
        i += 1;
    }
    let pack = load_pack(pack.as_deref().ok_or_else(|| anyhow::anyhow!("need --pack"))?)?;
    let profile = load_profile(profile.as_deref().ok_or_else(|| anyhow::anyhow!("need --profile"))?)?;
    let path = residency_ledger_hook::path_default();
    blake3_seal_ring::clear_prior_seal();
    // Valid prior ledger → free/reallocate (LIFO). Corrupt/missing → empty pager.
    let mut ledger = match ResidencyLedger::load(&path) {
        Ok(l) => l,
        Err(_) => ResidencyLedger::default(),
    };
    run_plan(&pack, &profile, &mut ledger)?;
    ledger.save(&path)?;
    Ok(())
}
