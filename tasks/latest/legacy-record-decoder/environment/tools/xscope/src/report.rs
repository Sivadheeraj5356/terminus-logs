/// Bundle output writer.
///
/// Defines the JSON structure written to the output path and provides
/// the serialisation function called by main.rs.

use legacy_record_lib::{
    b1::CompatTrace,
    c1::ErrorClassification,
    types::CanonicalView,
};

/// Top-level bundle written to the output path.
/// The `records`, `compatibility_trace`, `error_classification`, and
/// `artifacts` sections are all required; the verifier asserts their presence.
#[derive(Debug, serde::Serialize, serde::Deserialize)]
pub struct Bundle {
    pub groups: Vec<GroupRecord>,
    pub artifacts: Vec<ArtifactEntry>,
}

/// Per-group section inside the bundle.
#[derive(Debug, serde::Serialize, serde::Deserialize)]
pub struct GroupRecord {
    pub group: String,
    pub records: Vec<CanonicalView>,
    pub compatibility_trace: Vec<CompatTrace>,
    pub error_classification: Vec<ErrorClassification>,
    pub compatible_count: usize,
}

/// Artifact metadata entry.
#[derive(Debug, serde::Serialize, serde::Deserialize)]
pub struct ArtifactEntry {
    pub group: String,
    pub binary_path: String,
    pub text_path: String,
    pub record_count: usize,
}

/// Serialise a Bundle to the given path, creating parent directories.
pub fn write_bundle(bundle: &Bundle, out_path: &std::path::Path) -> Result<(), String> {
    if let Some(parent) = out_path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("cannot create output directory: {}", e))?;
    }

    // Emit the bundle as a flat JSON object with the four required top-level keys.
    // records and compatibility_trace are merged across all groups.
    let records: Vec<&CanonicalView> = bundle
        .groups
        .iter()
        .flat_map(|g| g.records.iter())
        .collect();

    let compat_trace: Vec<&CompatTrace> = bundle
        .groups
        .iter()
        .flat_map(|g| g.compatibility_trace.iter())
        .collect();

    let error_classification: Vec<&ErrorClassification> = bundle
        .groups
        .iter()
        .flat_map(|g| g.error_classification.iter())
        .collect();

    let output = serde_json::json!({
        "records": records,
        "compatibility_trace": compat_trace,
        "error_classification": error_classification,
        "artifacts": bundle.artifacts,
    });

    let json_str = serde_json::to_string_pretty(&output)
        .map_err(|e| format!("serialisation error: {}", e))?;

    std::fs::write(out_path, json_str)
        .map_err(|e| format!("cannot write {:?}: {}", out_path, e))?;

    Ok(())
}
