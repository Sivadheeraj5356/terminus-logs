use crate::ledger::RamRecord;

pub fn epoch_still_seated(rec: &RamRecord, active_epoch: u32) -> bool {
    rec.cycle_epoch >= active_epoch
}
