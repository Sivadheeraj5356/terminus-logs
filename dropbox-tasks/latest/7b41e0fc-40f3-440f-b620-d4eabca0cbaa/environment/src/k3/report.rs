use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReportRow {
    pub lane_id: String,
    pub chain_stamp: String,
    pub parent_pick: String,
    pub rc_band: u32,
    pub sync_label: String,
    pub stream_tag: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReportSummary {
    pub rows_total: u32,
    pub span_band: u32,
    pub lineage_digest: String,
    pub sync_label: String,
    pub journal_seq: u32,
    pub wrap_epoch: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SendReport {
    pub rows: Vec<ReportRow>,
    pub summary: ReportSummary,
}
