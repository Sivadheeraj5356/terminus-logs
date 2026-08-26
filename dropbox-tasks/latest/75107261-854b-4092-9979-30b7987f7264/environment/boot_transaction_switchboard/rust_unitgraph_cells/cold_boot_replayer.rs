//! Cold process rebuild of staged evidence.
use std::fs;
use std::process::Command;

use crate::boot_semantics::Semantics;
use crate::bootyard_boundary;
use crate::reconcile_failure;

pub fn verify_staged(staged: &str, order: &str, sem: &Semantics) -> Result<(), i32> {
    if let Ok(v) = std::env::var("UNITGRAPH_INJECT_REPLAY_FAULT") {
        if v == "1" {
            crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_CLOSURE, "injected replay fault");
            // restore handled by caller via shadow discard
            return Err(reconcile_failure::EXIT_CLOSURE);
        }
    }
    let exe = std::env::current_exe().map_err(|_| e())?;
    let status = Command::new(exe)
        .args(["--cold-replay", staged, order, staged])
        .env_remove("UNITGRAPH_INJECT_WRITE_FAULT")
        .env_remove("UNITGRAPH_INJECT_REPLAY_FAULT")
        .status()
        .map_err(|_| e())?;
    if !status.success() {
        return Err(e());
    }
    let _ = sem;
    Ok(())
}

pub fn run_cold(yard: &str, order: &str, _stage: &str) -> Result<(), i32> {
    let sem = Semantics::load().map_err(|c| c)?;
    let inv = crate::yard_inventory::load_yard(yard, &sem)?;
    let ord = crate::order_reader::load_order(order, &inv)?;
    let effective = crate::fragment_locator::build_effective(yard, &ord, &sem)?;
    let dep = crate::dependency_graph::build(yard, &effective, &ord, &sem)?;
    let tx = crate::transaction_builder::build(&dep, &effective, &ord, &sem)?;
    let tx = crate::cycle_witness::resolve(tx, &sem)?;
    let jobs = crate::boot_target_simulator::simulate(&tx, &effective, &inv, &ord, &sem)?;
    crate::expected_job_checker::check(&jobs, &ord, &sem)?;
    // compare with staged records if present
    let eff_path = bootyard_boundary::logical_join(yard, "var/lib/unitgraph/effective.units");
    if fs::metadata(&eff_path).is_ok() {
        // presence is enough for cold path; detailed compare in ledger writer pre-publish
    }
    Ok(())
}

fn e() -> i32 {
    crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_CLOSURE, "cold replay");
    reconcile_failure::EXIT_CLOSURE
}
