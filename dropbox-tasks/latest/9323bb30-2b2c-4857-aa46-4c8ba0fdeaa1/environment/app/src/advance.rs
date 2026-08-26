use anyhow::Result;
use crate::ledger::ResidencyLedger;
use crate::profile::AttnProfile;

pub fn run_advance(
    _profile: &AttnProfile,
    _ledger: &mut ResidencyLedger,
    _compact: bool,
    _release_logicals: &[u32],
) -> Result<()> {
    unimplemented!("run_advance")
}
