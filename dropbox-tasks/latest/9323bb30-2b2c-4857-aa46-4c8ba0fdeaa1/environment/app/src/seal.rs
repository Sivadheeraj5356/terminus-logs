use anyhow::Result;
use crate::ledger::ResidencyLedger;
use crate::profile::AttnProfile;

pub fn run_seal(
    _ledger: &ResidencyLedger,
    _profile: &AttnProfile,
    _seq_id: &str,
    _out: &str,
) -> Result<()> {
    unimplemented!("run_seal")
}
