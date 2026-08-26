use crate::ledger::SeatLedger;

pub fn recorded_mass(ledger: &SeatLedger) -> u64 {
    ledger.total_tonnage()
}
