//! Generation and idempotent accepted-order checks.
use std::fs;
use std::path::Path;

use crate::bootyard_boundary;
use crate::order_reader::Order;
use crate::reconcile_failure;
use crate::yard_inventory::Yard;

pub fn check_generation(yard: &Yard, order: &Order) -> Result<(), i32> {
    if order.expected_generation != yard.generation {
        // allow idempotent path when already accepted at this gen handled separately
        let accepted = bootyard_boundary::logical_join(&yard.root, "var/lib/unitgraph/accepted.order");
        if Path::new(&accepted).is_file() {
            let text = fs::read_to_string(&accepted).unwrap_or_default();
            if text.contains(&order.order_id) && order.expected_generation + 1 == yard.generation {
                return Ok(());
            }
        }
        crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_ORDER_GRAMMAR, "stale generation");
        return Err(reconcile_failure::EXIT_ORDER_GRAMMAR);
    }
    Ok(())
}

pub fn idempotent_receipt(yard: &Yard, order: &Order) -> Result<Option<String>, i32> {
    let accepted = bootyard_boundary::logical_join(&yard.root, "var/lib/unitgraph/accepted.order");
    let receipt = bootyard_boundary::logical_join(&yard.root, "var/lib/unitgraph/reconcile.receipt");
    if !Path::new(&accepted).is_file() || !Path::new(&receipt).is_file() {
        return Ok(None);
    }
    let text = fs::read_to_string(&accepted).map_err(|_| e())?;
    if text.lines().any(|l| l.starts_with("order_id=") && l.ends_with(&order.order_id))
        || text.contains(&format!("order_id={}", order.order_id))
    {
        if yard.generation == order.next_generation {
            let r = fs::read_to_string(&receipt).map_err(|_| e())?;
            return Ok(Some(r.trim().to_string()));
        }
    }
    Ok(None)
}

fn e() -> i32 {
    crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_CLOSURE, "idempotent");
    reconcile_failure::EXIT_CLOSURE
}
