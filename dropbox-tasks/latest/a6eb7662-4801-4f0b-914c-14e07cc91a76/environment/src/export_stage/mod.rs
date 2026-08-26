use crate::atlas;
use crate::model::AssayBundle;
use std::path::Path;

/// Publish stage — projects snapshot records into output products.
pub fn publish_from_bundle(bundle: &AssayBundle) -> Result<(), String> {
    atlas::publish_outputs(
        Path::new("/app/output/composition-results.json"),
        Path::new("/app/output/derivation-trace.json"),
        Path::new("/app/output/inconsistent-coins.json"),
        Path::new("/app/output/audit.json"),
        bundle,
    )
}
