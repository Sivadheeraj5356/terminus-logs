use crate::yard_index::{cached_shift_table, reset_shift_cache_for_tests};
use crate::ledger::{RamRecord, SeatLedger};
use crate::shift_table::materialize_shift_table;
use serde_json::json;

pub fn run_probe() -> Result<(), String> {
    reset_shift_cache_for_tests();
    let mut ledger = SeatLedger::new();
    ledger.bump_cycle_epoch();
    let first = cached_shift_table(&ledger);
    ledger.bump_journal_revision();
    ledger.record_ram(RamRecord {
        ram_id: "probe_ram".into(),
        checksum: 88,
        tonnage_kg: 600,
        cycle_epoch: 1,
    });
    let second = cached_shift_table(&ledger);
    let truth = json!({
        "cycle_epoch": ledger.cycle_epoch(),
        "journal_revision": ledger.journal_revision(),
        "ram_count": ledger.ram_count(),
    });

    reset_shift_cache_for_tests();
    let mut ledger_a = SeatLedger::new();
    ledger_a.bump_cycle_epoch();
    ledger_a.record_ram(RamRecord {
        ram_id: "isolated_ram_a".into(),
        checksum: 41,
        tonnage_kg: 300,
        cycle_epoch: 1,
    });
    let _ = cached_shift_table(&ledger_a);

    let mut ledger_b = SeatLedger::new();
    ledger_b.bump_cycle_epoch();
    ledger_b.record_ram(RamRecord {
        ram_id: "isolated_ram_b".into(),
        checksum: 42,
        tonnage_kg: 400,
        cycle_epoch: 1,
    });
    let isolated = cached_shift_table(&ledger_b);
    let isolated_truth = materialize_shift_table(&ledger_b);

    println!(
        "{}",
        serde_json::to_string(&json!({
            "first": first,
            "second": second,
            "truth": truth,
            "isolated": isolated,
            "isolated_truth": isolated_truth,
        }))
        .unwrap()
    );
    Ok(())
}
