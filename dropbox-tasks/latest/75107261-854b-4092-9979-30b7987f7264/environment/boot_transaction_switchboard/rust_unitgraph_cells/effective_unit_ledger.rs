//! Write var/lib/unitgraph state records into staged yard.
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

use crate::alias_mask_state::EnablementState;
use crate::boot_target_simulator::SimResult;
use crate::bootyard_boundary;
use crate::fragment_locator::EffectiveUnit;
use crate::logical_seal;
use crate::order_reader::Order;
use crate::reconcile_failure;
use crate::transaction_builder::Transaction;
use crate::unit_parser;

pub fn write_all(
    staged: &str,
    effective: &BTreeMap<String, EffectiveUnit>,
    enablement: &EnablementState,
    tx: &Transaction,
    jobs: &SimResult,
    trace: &str,
    account: &str,
    order: &Order,
) -> Result<(), i32> {
    let base = bootyard_boundary::logical_join(staged, "var/lib/unitgraph");
    fs::create_dir_all(&base).map_err(|_| e())?;
    // generation written at publish; write placeholder matching next
    fs::write(format!("{}/generation", base), format!("{}\n", order.next_generation)).map_err(|_| e())?;
    fs::write(
        format!("{}/accepted.order", base),
        format!(
            "order_id={}\norder_seal={}\npre_generation={}\npost_generation={}\n",
            order.order_id,
            order.seal,
            order.expected_generation,
            order.next_generation
        ),
    )
    .map_err(|_| e())?;
    let mut eff_lines = Vec::new();
    for (name, eu) in effective {
        let mut dirs = Vec::new();
        for (sec, keys) in &eu.parsed.sections {
            for (k, vals) in keys {
                for v in vals {
                    dirs.push(format!("{}:{}={}", sec, k, v));
                }
            }
        }
        dirs.sort();
        eff_lines.push(format!(
            "{}\t{}\t{}\t{}\t{}\t{}",
            name,
            eu.fragment_logical,
            eu.origin,
            if eu.masked { "masked" } else { "loaded" },
            eu.dropins.len(),
            logical_seal::sha256_hex(dirs.join(";").as_bytes())
        ));
    }
    eff_lines.sort();
    fs::write(format!("{}/effective.units", base), eff_lines.join("\n") + "\n").map_err(|_| e())?;
    let mut en = Vec::new();
    for (u, c) in &enablement.classes {
        en.push(format!("{}\t{}", u, c));
    }
    en.sort();
    en.extend(enablement.evidence.iter().cloned());
    fs::write(format!("{}/enablement.state", base), en.join("\n") + "\n").map_err(|_| e())?;
    let mut tj = Vec::new();
    for (u, job) in &tx.jobs {
        tj.push(format!("{}\t{}\t{}", u, job.kind, job.origins.join(",")));
    }
    for edge in &tx.edges {
        tj.push(format!("edge\t{}\t{}\t{}\t{}", edge.from, edge.to, edge.kind, edge.provenance));
    }
    tj.sort();
    fs::write(format!("{}/transaction.jobs", base), tj.join("\n") + "\n").map_err(|_| e())?;
    fs::write(format!("{}/boot.trace", base), trace).map_err(|_| e())?;
    fs::write(format!("{}/change.account", base), account).map_err(|_| e())?;
    // provisional receipt filled by sealer after publish
    fs::write(format!("{}/reconcile.receipt", base), "pending\n").map_err(|_| e())?;
    let _ = jobs;
    let _ = unit_parser::get_list;
    let _ = Path::new(&base);
    Ok(())
}

fn e() -> i32 {
    crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_CLOSURE, "ledger write");
    reconcile_failure::EXIT_CLOSURE
}
