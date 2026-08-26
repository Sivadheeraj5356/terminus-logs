use std::cell::Cell;
use std::path::Path;

use u9p::stamp_n8;
use w3h::{fold_z1, EmittedRow, SeedBundle, StampWitness, TargetRow};

use crate::jrnl;

pub fn steady_label(env: &Path) -> String {
    let _ = jrnl::load_durable_stamp(env);
    "status=steady".to_string()
}

pub fn combine_arm(gate_first: bool, acc: u64) -> u64 {
    let cell = Cell::new(acc);
    stamp_n8(
        gate_first,
        || {
            cell.set(cell.get().wrapping_mul(37) ^ 0x3131);
        },
        || {
            cell.set(cell.get().wrapping_mul(19) ^ 0x4242);
        },
    );
    cell.get()
}

pub fn emit_rows(
    targets: &[TargetRow],
    seeds: &SeedBundle,
    witness: &StampWitness,
) -> Vec<EmittedRow> {
    fold_z1(targets, seeds, witness)
}
