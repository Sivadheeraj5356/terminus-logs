//! Symlink create/remove with relative target custody.
use std::fs;
use std::os::unix::fs::symlink;
use std::path::Path;

use crate::reconcile_failure;

pub fn ensure_parent(path: &str) -> Result<(), i32> {
    if let Some(p) = Path::new(path).parent() {
        fs::create_dir_all(p).map_err(|_| err("mkdir"))?;
    }
    Ok(())
}

pub fn write_symlink(path: &str, target: &str) -> Result<(), i32> {
    ensure_parent(path)?;
    if Path::new(path).exists() || fs::symlink_metadata(path).is_ok() {
        fs::remove_file(path).map_err(|_| err("replace"))?;
    }
    symlink(target, path).map_err(|_| err("symlink"))?;
    Ok(())
}

pub fn remove_path(path: &str) -> Result<(), i32> {
    if Path::new(path).exists() || fs::symlink_metadata(path).is_ok() {
        let meta = fs::symlink_metadata(path).map_err(|_| err("meta"))?;
        if meta.is_dir() {
            fs::remove_dir_all(path).map_err(|_| err("rmdir"))?;
        } else {
            fs::remove_file(path).map_err(|_| err("rm"))?;
        }
    }
    Ok(())
}

fn err(msg: &str) -> i32 {
    crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_MUTATION, msg);
    reconcile_failure::EXIT_MUTATION
}
