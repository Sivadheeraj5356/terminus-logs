use crate::h9::f2::{encode_sidecar_blob, fold_digest_hex};
use crate::k3::report::{ReportRow, ReportSummary, SendReport};
use crate::n2::store::JournalTail;

pub struct RollupOutput {
    pub report: SendReport,
    pub stream_bytes: Vec<u8>,
}

pub fn seal_matrix(
    mut rows: Vec<ReportRow>,
    journal: &mut JournalTail,
    max_lane_epoch: u32,
) -> RollupOutput {
    let mut digest_order: Vec<ReportRow> = rows.clone();
    digest_order.sort_by(|a, b| b.lane_id.cmp(&a.lane_id));
    let digest_stamps: Vec<String> = digest_order
        .iter()
        .map(|row| row.chain_stamp.clone())
        .collect();

    rows.sort_by(|a, b| a.lane_id.cmp(&b.lane_id));

    let stamps: Vec<String> = rows.iter().map(|r| r.chain_stamp.clone()).collect();
    let min_band = rows.iter().map(|r| r.rc_band).min().unwrap_or(0);
    let max_band = rows.iter().map(|r| r.rc_band).max().unwrap_or(0);
    let summary_sync = if rows.iter().all(|r| r.sync_label == "steady") {
        "steady"
    } else {
        "drift"
    };

    journal.journal_seq = journal.journal_seq.saturating_add(rows.len() as u32);
    let digest = fold_digest_hex(&digest_stamps, journal.journal_seq, max_lane_epoch);
    let summary = ReportSummary {
        rows_total: rows.len() as u32,
        span_band: max_band.saturating_sub(min_band),
        lineage_digest: digest,
        sync_label: summary_sync.to_string(),
        journal_seq: journal.journal_seq,
        wrap_epoch: max_lane_epoch,
    };

    let report = SendReport {
        rows: rows.clone(),
        summary,
    };
    let stream_bytes = encode_sidecar_blob(&rows);
    let _ = stamps;
    RollupOutput {
        report,
        stream_bytes,
    }
}
