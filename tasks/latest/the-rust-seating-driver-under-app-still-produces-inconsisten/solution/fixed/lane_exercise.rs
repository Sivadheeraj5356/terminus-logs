use crate::yard_index::{cached_shift_table, reset_shift_cache_for_tests};
use crate::ledger::{RamRecord, SeatLedger};
use crate::shift_table::materialize_shift_table;
use serde_json::json;
use std::collections::HashMap;

pub fn run_probe() -> Result<(), String> {
    reset_shift_cache_for_tests();
    let mut ledger = SeatLedger::new();
    ledger.set_cycle_epoch(1);
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
    ledger_a.set_cycle_epoch(1);
    ledger_a.record_ram(RamRecord {
        ram_id: "isolated_ram_a".into(),
        checksum: 41,
        tonnage_kg: 300,
        cycle_epoch: 1,
    });
    let _ = cached_shift_table(&ledger_a);

    let mut ledger_b = SeatLedger::new();
    ledger_b.set_cycle_epoch(1);
    ledger_b.record_ram(RamRecord {
        ram_id: "isolated_ram_b".into(),
        checksum: 42,
        tonnage_kg: 400,
        cycle_epoch: 1,
    });
    let isolated = cached_shift_table(&ledger_b);
    let isolated_truth = materialize_shift_table(&ledger_b);

    reset_shift_cache_for_tests();
    let mut map_a = HashMap::new();
    map_a.insert(
        "collision_ram_a".into(),
        RamRecord {
            ram_id: "collision_ram_a".into(),
            checksum: 11,
            tonnage_kg: 100,
            cycle_epoch: 7,
        },
    );
    let mut ledger_collision_a = SeatLedger::new();
    ledger_collision_a.restore_baseline(map_a, 7, 42);
    let collision_truth_a = materialize_shift_table(&ledger_collision_a);
    let collision_a = cached_shift_table(&ledger_collision_a);

    let mut map_b = HashMap::new();
    map_b.insert(
        "collision_ram_b".into(),
        RamRecord {
            ram_id: "collision_ram_b".into(),
            checksum: 22,
            tonnage_kg: 200,
            cycle_epoch: 7,
        },
    );
    let mut ledger_collision_b = SeatLedger::new();
    ledger_collision_b.restore_baseline(map_b, 7, 42);
    let collision_truth_b = materialize_shift_table(&ledger_collision_b);
    let collision_b = cached_shift_table(&ledger_collision_b);

    println!(
        "{}",
        serde_json::to_string(&json!({
            "first": first,
            "second": second,
            "truth": truth,
            "isolated": isolated,
            "isolated_truth": isolated_truth,
            "collision_a": collision_a,
            "collision_b": collision_b,
            "collision_truth_a": collision_truth_a,
            "collision_truth_b": collision_truth_b,
        }))
        .unwrap()
    );
    Ok(())
}
