use serde::Serialize;

#[derive(Debug, Clone)]
pub struct Manifest {
    pub bound_rotate: u32,
    pub slack: u32,
    pub sweep_mask: u32,
    pub window_width_ms: u64,
    pub manifest_gen: u32,
}

#[derive(Debug, Clone)]
pub struct JournalHeader {
    pub rotate_gen: u32,
    pub bound_rotate: u32,
    pub slack: u32,
}

#[derive(Debug, Clone)]
pub struct ScopeRecord {
    pub rotate_gen: u32,
    pub scope_id: u32,
    pub action_mask: u32,
    pub size_delta: i32,
    pub seq_num: u32,
    pub ts_ms: u64,
    pub rel_path: String,
    pub payload: Vec<u8>,
    pub journal_file: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct WindowRow {
    pub start_ms: u64,
    pub count: u32,
    pub size_delta_sum: i64,
    pub size_min: i32,
    pub size_max: i32,
    pub seq_gap_sum: u32,
}

#[derive(Debug, Clone, Serialize)]
pub struct SweepLedger {
    pub profile: String,
    pub workflow: String,
    pub included_records: u32,
    pub dropped_records: u32,
    pub windows: Vec<WindowRow>,
    pub rebuild_digest: Option<String>,
    pub merge_digest: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ScopeState {
    pub manifest_gen: u32,
    pub scope_count: u32,
    pub last_rotate_gen: u32,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProbeSnapshot {
    pub profile: String,
    pub effective_mask: u32,
    pub cache_width_ms: u64,
    pub manifest_gen: u32,
}
