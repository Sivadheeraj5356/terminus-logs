use crate::ledger::SeatLedger;

pub fn recorded_mass(ledger: &SeatLedger) -> u32 {
    ledger.total_tonnage()
}
