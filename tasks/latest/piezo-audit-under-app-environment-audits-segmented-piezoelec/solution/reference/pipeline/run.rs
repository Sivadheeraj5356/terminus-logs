use std::path::Path;

use crate::types::BatchReport;
use crate::workflow::drive::audit_paths as drive_audit;

pub fn audit_paths(paths: &[impl AsRef<Path>], as_of: &str) -> Result<BatchReport, String> {
    drive_audit(paths, as_of)
}
