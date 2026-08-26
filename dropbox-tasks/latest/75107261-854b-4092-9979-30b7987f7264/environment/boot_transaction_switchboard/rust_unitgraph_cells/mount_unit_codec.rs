//! Mount unit name ↔ Where path consistency.
use crate::boot_semantics::Semantics;
use crate::reconcile_failure;
use crate::unit_name_codec;

pub fn mount_name_for_where(where_path: &str, sem: &Semantics) -> Result<String, i32> {
    if where_path == "/" {
        let v = sem.decide_or("MOUNT_ROOT_NAME", &["where", "/"], "root.mount");
        return Ok(v);
    }
    let stem = unit_name_codec::escape_path(where_path).map_err(|_| {
        crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_UNIT_LOADING, "mount escape");
        reconcile_failure::EXIT_UNIT_LOADING
    })?;
    Ok(format!("{}.mount", stem))
}

pub fn validate_mount_unit(unit: &str, where_path: &str, sem: &Semantics) -> Result<(), i32> {
    let expect = mount_name_for_where(where_path, sem)?;
    if expect != unit {
        crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_UNIT_LOADING, "mount name mismatch");
        return Err(reconcile_failure::EXIT_UNIT_LOADING);
    }
    Ok(())
}
