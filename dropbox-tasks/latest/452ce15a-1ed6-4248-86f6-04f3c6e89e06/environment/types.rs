use serde::{Deserialize, Serialize};
use std::collections::HashMap;

pub const REPORT_SCHEMA_VERSION: u32 = 4;
pub const MANIFEST_SCHEMA_VERSION: u32 = 3;

#[derive(Debug, Clone)]
pub struct SegmentOverride {
    pub alpha_override: f64,
    pub nominal_hz_override: f64,
}

#[derive(Debug, Clone)]
pub struct ChipReading {
    pub line_index: u32,
    pub segment_id: String,
    pub temp_c: f64,
    pub freq_hz: f64,
}

#[derive(Debug, Clone)]
pub struct ChipProfile {
    pub family_id: String,
    pub chip_id: String,
    pub alias: String,
    pub profile_id: String,
    pub nominal_hz: f64,
    pub readings: Vec<ChipReading>,
    pub segment_overrides: HashMap<String, SegmentOverride>,
}

#[derive(Debug, Clone)]
pub struct ProfileRevision {
    pub profile_id: String,
    pub effective_date: String,
    pub inherits: String,
    pub alpha: f64,
    pub nominal_hz_override: f64,
    pub deprecation_window_days: u32,
    pub alpha_raw: String,
    pub nominal_hz_override_raw: String,
}

#[derive(Debug, Clone)]
pub struct ResolvedProfile {
    pub revision: ProfileRevision,
    pub parent_effective_date: String,
    pub resolved_alpha: f64,
    pub resolved_nominal_override: f64,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub struct ReadingRow {
    pub line_index: u32,
    pub segment_id: String,
    pub temp_c: f64,
    pub freq_hz: f64,
    pub freq_25_hz: f64,
    pub ppm_pull: f64,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub struct SourceProvenance {
    pub path: String,
    pub family_id: String,
    pub chip_id: String,
    pub alias: String,
    pub profile_id: String,
    pub profile_effective_date: String,
    pub profile_parent_effective_date: String,
    pub segment_ids: Vec<String>,
    pub reading_count: u32,
    pub source_digest: String,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub struct ProfileLineageEntry {
    pub profile_id: String,
    pub effective_date: String,
    pub inherits: String,
    pub alpha: f64,
    pub nominal_hz_override: f64,
    pub deprecation_window_days: u32,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub struct FamilyReport {
    pub family_id: String,
    pub chip_id: String,
    pub alias: String,
    pub profile_id: String,
    pub nominal_hz: f64,
    pub reading_count: usize,
    pub readings: Vec<ReadingRow>,
    pub weighted_mean_ppm: f64,
    pub branch_generation: u32,
    pub source_provenance: Vec<SourceProvenance>,
    pub resonance_digest: String,
}

#[derive(Debug, Serialize, Deserialize, PartialEq)]
pub struct BatchReport {
    pub schema_version: u32,
    pub as_of_date: String,
    pub input_fingerprint: String,
    pub profile_graph_hash: String,
    pub batch_generation: u32,
    pub family_count: usize,
    pub families: Vec<FamilyReport>,
    pub batch_digest: String,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub struct ManifestHistoryEntry {
    pub batch_generation: u32,
    pub input_fingerprint: String,
    pub profile_graph_hash: String,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub struct ManifestBranch {
    pub family_id: String,
    pub branch_generation: u32,
    pub input_fingerprint: String,
    pub profile_graph_hash: String,
    pub parent_branch_generation: Option<u32>,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub struct ResonanceManifest {
    pub schema_version: u32,
    pub batch_generation: u32,
    pub last_input_fingerprint: String,
    pub last_profile_graph_hash: String,
    pub branches: Vec<ManifestBranch>,
    pub history: Vec<ManifestHistoryEntry>,
}
