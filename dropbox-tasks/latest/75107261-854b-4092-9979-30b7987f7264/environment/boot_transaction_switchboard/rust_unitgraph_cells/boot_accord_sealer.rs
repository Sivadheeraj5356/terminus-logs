//! Receipt commitment and reopen verification.
use std::fs;
use std::process::Command;

use crate::bootyard_boundary;
use crate::logical_seal;
use crate::order_reader::Order;
use crate::reconcile_failure;
use crate::yard_inventory::{self, Yard};

pub fn seal_and_reopen(yard: &str, order: &Order, inv: &Yard) -> Result<String, i32> {
    let receipt = compute_receipt(yard, order, inv)?;
    let path = bootyard_boundary::logical_join(yard, "var/lib/unitgraph/reconcile.receipt");
    fs::write(&path, format!("{}\n", receipt)).map_err(|_| e())?;
    let exe = std::env::current_exe().map_err(|_| e())?;
    let out = Command::new(exe)
        .args(["--receipt-reopen", yard])
        .output()
        .map_err(|_| e())?;
    if !out.status.success() {
        return Err(e());
    }
    let got = String::from_utf8_lossy(&out.stdout).trim().to_string();
    if got != receipt {
        return Err(e());
    }
    Ok(receipt)
}

pub fn reopen_and_verify(yard: &str) -> Result<String, i32> {
    let sem = crate::boot_semantics::Semantics::load().map_err(|c| c)?;
    let inv = yard_inventory::load_yard(yard, &sem)?;
    let accepted = fs::read_to_string(bootyard_boundary::logical_join(yard, "var/lib/unitgraph/accepted.order"))
        .map_err(|_| e())?;
    let order_id = accepted
        .lines()
        .find_map(|l| l.strip_prefix("order_id="))
        .unwrap_or("")
        .to_string();
    let seal = accepted
        .lines()
        .find_map(|l| l.strip_prefix("order_seal="))
        .unwrap_or("")
        .to_string();
    // rebuild receipt without full order struct
    let mut fake = order_stub(&order_id, &seal, inv.generation);
    let r = compute_receipt(yard, &fake, &inv)?;
    let on_disk = fs::read_to_string(bootyard_boundary::logical_join(yard, "var/lib/unitgraph/reconcile.receipt"))
        .map_err(|_| e())?;
    if on_disk.trim() != r {
        return Err(e());
    }
    let _ = fake;
    Ok(r)
}

fn order_stub(order_id: &str, seal: &str, gen: u64) -> Order {
    Order {
        root: String::new(),
        order_id: order_id.into(),
        expected_generation: gen.saturating_sub(1),
        next_generation: gen,
        final_target: String::new(),
        job_mode: "fail".into(),
        intents: vec![],
        presets: vec![],
        acceptance: vec![],
        target_members: vec![],
        access_triggers: vec![],
        seal: seal.into(),
        record: Default::default(),
    }
}

fn compute_receipt(yard: &str, order: &Order, inv: &Yard) -> Result<String, i32> {
    let mut parts = Vec::new();
    parts.push(format!("host={}", inv.host_label));
    parts.push(format!("machine={}", inv.machine_id));
    parts.push(format!("vendor_seal={}", logical_seal::sha256_hex(inv.vendor_seal.as_bytes())));
    parts.push(format!("order_seal={}", order.seal));
    parts.push(format!("admin={}", yard_inventory::digest_admin_tree(yard)?));
    for name in [
        "generation",
        "accepted.order",
        "effective.units",
        "enablement.state",
        "transaction.jobs",
        "boot.trace",
        "change.account",
    ] {
        let p = bootyard_boundary::logical_join(yard, &format!("var/lib/unitgraph/{}", name));
        let bytes = fs::read(&p).map_err(|_| e())?;
        parts.push(format!("{}={}", name, logical_seal::sha256_hex(&bytes)));
    }
    Ok(logical_seal::sha256_hex(parts.join("\n").as_bytes()))
}

fn e() -> i32 {
    crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_CLOSURE, "receipt");
    reconcile_failure::EXIT_CLOSURE
}
