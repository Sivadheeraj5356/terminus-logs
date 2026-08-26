use anyhow::Result;
use crate::ledger::ResidencyLedger;
use crate::pack::KvPack;
use crate::profile::AttnProfile;

pub fn run_plan(_pack: &KvPack, _profile: &AttnProfile, _ledger: &mut ResidencyLedger) -> Result<()> {
    unimplemented!("run_plan")
}
