use crate::ledger::SeatLedger;
use crate::mass::recorded_mass;
use serde_json::{json, Value};

pub fn build_report(
    ledger: &SeatLedger,
    rollback_performed: bool,
    guides_marked: u32,
) -> Value {
    let seated = ledger.ram_count();
    json!({
        "rams_seated": seated,
        "guides_marked": guides_marked,
        "tonnage_recorded": recorded_mass(ledger),
        "state_digest": format!("{:08x}", seated),
        "rollback_performed": rollback_performed,
        "ready": !rollback_performed && seated > 0,
    })
}
