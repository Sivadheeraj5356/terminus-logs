//! Apply planned file/symlink mutations into a staged yard.
use std::fs;
use std::path::Path;

use crate::boot_semantics::Semantics;
use crate::bootyard_boundary;
use crate::install_graph::MutationPlan;
use crate::reconcile_failure;
use crate::symlink_custodian;

pub fn apply_plan(staged_root: &str, plan: &MutationPlan, _sem: &Semantics) -> Result<(), i32> {
    for ch in &plan.changes {
        let abs = bootyard_boundary::logical_join(staged_root, &ch.path_logical);
        match ch.kind.as_str() {
            "symlink" | "mask" => {
                let target = if ch.kind == "mask" { "/dev/null" } else { ch.after.as_str() };
                symlink_custodian::write_symlink(&abs, target)?;
            }
            "file" => {
                symlink_custodian::ensure_parent(&abs)?;
                let content = ch.after.strip_prefix("content:").unwrap_or(&ch.after);
                // payload_fields are escaped canonical field blocks using | as line sep
                let text = content.replace('|', "\n") + "\n";
                fs::write(&abs, text).map_err(|_| err())?;
            }
            "remove" => {
                symlink_custodian::remove_path(&abs)?;
            }
            _ => return Err(err()),
        }
        let _ = Path::new(&abs);
    }
    Ok(())
}

fn err() -> i32 {
    crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_MUTATION, "write");
    reconcile_failure::EXIT_MUTATION
}
