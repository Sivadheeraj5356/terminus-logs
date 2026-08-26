//! Operand and path custody checks.
use std::fs;
use std::path::{Component, Path};

use crate::reconcile_failure;

pub fn validate_operands(yard: &str, order: &str) -> Result<(), i32> {
    check_abs(yard, ".bootyard")?;
    check_abs(order, ".bootorder")?;
    if yard == order {
        return err(reconcile_failure::EXIT_INVOCATION, "aliased roots");
    }
    let y = Path::new(yard);
    let o = Path::new(order);
    if o.starts_with(y) {
        return err(reconcile_failure::EXIT_INVOCATION, "order beneath yard");
    }
    if y.symlink_metadata().map(|m| m.file_type().is_symlink()).unwrap_or(true) {
        return err(reconcile_failure::EXIT_YARD_CUSTODY, "yard symlink");
    }
    if o.symlink_metadata().map(|m| m.file_type().is_symlink()).unwrap_or(true) {
        return err(reconcile_failure::EXIT_YARD_CUSTODY, "order symlink");
    }
    if !y.is_dir() || !o.is_dir() {
        return err(reconcile_failure::EXIT_INVOCATION, "operands must be directories");
    }
    Ok(())
}

fn check_abs(p: &str, suffix: &str) -> Result<(), i32> {
    if p.is_empty() || !p.starts_with('/') {
        return err(reconcile_failure::EXIT_INVOCATION, "absolute path required");
    }
    if p.contains('\0') || p.chars().any(|c| c.is_control()) {
        return err(reconcile_failure::EXIT_INVOCATION, "control bytes");
    }
    if p.contains("//") || p.ends_with('/') {
        return err(reconcile_failure::EXIT_INVOCATION, "noncanonical separators");
    }
    if !p.ends_with(suffix) {
        return err(reconcile_failure::EXIT_INVOCATION, "suffix mismatch");
    }
    let path = Path::new(p);
    for c in path.components() {
        match c {
            Component::RootDir | Component::Normal(_) => {}
            _ => return err(reconcile_failure::EXIT_INVOCATION, "lexical escape"),
        }
    }
    let _ = fs::metadata(p).map_err(|_| reconcile_failure::EXIT_INVOCATION)?;
    Ok(())
}

fn err(code: i32, msg: &str) -> Result<(), i32> {
    crate::diagnostic_surface::emit_error(code, msg);
    Err(code)
}

pub fn logical_join(root: &str, rel: &str) -> String {
    format!("{}/{}", root.trim_end_matches('/'), rel.trim_start_matches('/'))
}
