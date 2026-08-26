//! Administrator entry for boot graph reconciliation.
#[path = "bootyard_boundary.rs"]
mod bootyard_boundary;
#[path = "yard_inventory.rs"]
mod yard_inventory;
#[path = "order_reader.rs"]
mod order_reader;
#[path = "logical_seal.rs"]
mod logical_seal;
#[path = "unit_name_codec.rs"]
mod unit_name_codec;
#[path = "fragment_locator.rs"]
mod fragment_locator;
#[path = "unit_parser.rs"]
mod unit_parser;
#[path = "dropin_merger.rs"]
mod dropin_merger;
#[path = "specifier_expander.rs"]
mod specifier_expander;
#[path = "install_graph.rs"]
mod install_graph;
#[path = "preset_resolver.rs"]
mod preset_resolver;
#[path = "alias_mask_state.rs"]
mod alias_mask_state;
#[path = "dependency_graph.rs"]
mod dependency_graph;
#[path = "transaction_builder.rs"]
mod transaction_builder;
#[path = "cycle_witness.rs"]
mod cycle_witness;
#[path = "mount_unit_codec.rs"]
mod mount_unit_codec;
#[path = "device_alias_resolver.rs"]
mod device_alias_resolver;
#[path = "condition_evaluator.rs"]
mod condition_evaluator;
#[path = "job_state_machine.rs"]
mod job_state_machine;
#[path = "boot_target_simulator.rs"]
mod boot_target_simulator;
#[path = "expected_job_checker.rs"]
mod expected_job_checker;
#[path = "mutation_journal.rs"]
mod mutation_journal;
#[path = "unit_file_writer.rs"]
mod unit_file_writer;
#[path = "symlink_custodian.rs"]
mod symlink_custodian;
#[path = "generation_guard.rs"]
mod generation_guard;
#[path = "cold_boot_replayer.rs"]
mod cold_boot_replayer;
#[path = "effective_unit_ledger.rs"]
mod effective_unit_ledger;
#[path = "boot_trace_writer.rs"]
mod boot_trace_writer;
#[path = "boot_accord_sealer.rs"]
mod boot_accord_sealer;
#[path = "diagnostic_surface.rs"]
mod diagnostic_surface;
#[path = "boot_semantics.rs"]
mod boot_semantics;
#[path = "embedded_boot_semantics.rs"]
mod embedded_boot_semantics;
#[path = "reconcile_failure.rs"]
mod reconcile_failure;

use std::env;
use std::process;

fn main() {
    let mut args: Vec<String> = env::args().collect();
    if args.len() >= 2 && args[1] == "--cold-replay" {
        // Internal cold replay: --cold-replay <yard> <order> <stage_dir>
        if args.len() != 5 {
            diagnostic_surface::emit_error(reconcile_failure::EXIT_INVOCATION, "cold replay arity");
            process::exit(reconcile_failure::EXIT_INVOCATION);
        }
        match cold_boot_replayer::run_cold(&args[2], &args[3], &args[4]) {
            Ok(()) => process::exit(0),
            Err(code) => {
                diagnostic_surface::emit_error(code, "cold replay rejected");
                process::exit(code);
            }
        }
    }
    if args.len() >= 2 && args[1] == "--receipt-reopen" {
        if args.len() != 3 {
            diagnostic_surface::emit_error(reconcile_failure::EXIT_INVOCATION, "receipt reopen arity");
            process::exit(reconcile_failure::EXIT_INVOCATION);
        }
        match boot_accord_sealer::reopen_and_verify(&args[2]) {
            Ok(receipt) => {
                print!("{}", receipt);
                process::exit(0);
            }
            Err(code) => {
                diagnostic_surface::emit_error(code, "receipt reopen failed");
                process::exit(code);
            }
        }
    }

    // Public: two absolute operands
    if args.len() != 3 {
        diagnostic_surface::emit_error(reconcile_failure::EXIT_INVOCATION, "expected yard and order paths");
        process::exit(reconcile_failure::EXIT_INVOCATION);
    }
    let yard = args[1].clone();
    let order = args[2].clone();
    match run_reconcile(&yard, &order) {
        Ok(receipt) => {
            print!("{}\n", receipt);
            process::exit(0);
        }
        Err(code) => process::exit(code),
    }
}

fn run_reconcile(yard: &str, order: &str) -> Result<String, i32> {
    let sem = boot_semantics::Semantics::load()?;
    bootyard_boundary::validate_operands(yard, order)?;
    let inv = yard_inventory::load_yard(yard, &sem)?;
    let ord = order_reader::load_order(order, &inv)?;
    generation_guard::check_generation(&inv, &ord)?;

    if let Some(receipt) = generation_guard::idempotent_receipt(&inv, &ord)? {
        return Ok(receipt);
    }

    let plan = install_graph::plan_mutations(&inv, &ord, &sem)?;
    let staged = match mutation_journal::stage_shadow(yard, &plan, &sem) {
        Ok(s) => s,
        Err(code) => {
            let _ = mutation_journal::cleanup_shadows(yard);
            return Err(code);
        }
    };
    let result = (|| {
        unit_file_writer::apply_plan(&staged, &plan, &sem)?;
        let effective = fragment_locator::build_effective(&staged, &ord, &sem)?;
        let enablement = alias_mask_state::classify_enablement(&staged, &effective, &ord, &sem)?;
        let dep = dependency_graph::build(&staged, &effective, &ord, &sem)?;
        let tx = transaction_builder::build(&dep, &effective, &ord, &sem)?;
        let tx = cycle_witness::resolve(tx, &sem)?;
        let jobs = boot_target_simulator::simulate(&tx, &effective, &inv, &ord, &sem)?;
        expected_job_checker::check(&jobs, &ord, &sem)?;
        let trace = boot_trace_writer::render(&jobs, &effective, &inv)?;
        let account = mutation_journal::render_account(&plan)?;
        effective_unit_ledger::write_all(&staged, &effective, &enablement, &tx, &jobs, &trace, &account, &ord)?;
        cold_boot_replayer::verify_staged(&staged, order, &sem)?;
        mutation_journal::publish_exchange(yard, &staged, &plan)?;
        boot_accord_sealer::seal_and_reopen(yard, &ord, &inv)
    })();
    let _ = mutation_journal::cleanup_shadows(yard);
    result
}
