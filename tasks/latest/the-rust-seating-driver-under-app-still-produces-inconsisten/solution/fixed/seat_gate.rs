use crate::ledger::SeatLedger;

pub fn suppress_repeat_seat(ledger: &SeatLedger, ram_id: &str, checksum: u32) -> bool {
    ledger.has_ram(ram_id) && ledger.ram_checksum(ram_id) == Some(checksum)
}

pub enum RepeatSeatOutcome {
    Suppress,
    RefreshEpoch,
    Proceed,
}

pub fn classify_repeat_seat(
    ledger: &SeatLedger,
    ram_id: &str,
    checksum: u32,
    epoch: u32,
) -> RepeatSeatOutcome {
    if !suppress_repeat_seat(ledger, ram_id, checksum) {
        return RepeatSeatOutcome::Proceed;
    }
    if let Some(existing) = ledger.ram_record(ram_id) {
        if epoch > existing.cycle_epoch {
            return RepeatSeatOutcome::RefreshEpoch;
        }
    }
    RepeatSeatOutcome::Suppress
}
