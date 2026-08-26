//! Typed input/output models matching the public report schema.
//! Starter provides shapes only; engine logic is intentionally absent.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Report {
    pub request_rows: Vec<RequestRow>,
    pub quote_rows: Vec<QuoteRow>,
    pub event_rows: Vec<EventRow>,
    pub pcr_rows: Vec<PcrRow>,
    pub reference_match_rows: Vec<ReferenceMatchRow>,
    pub counter_rows: Vec<CounterRow>,
    pub nonce_rows: Vec<NonceRow>,
    pub conflict_rows: Vec<ConflictRow>,
    pub summary: Summary,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RequestRow {
    pub request_id: String,
    pub received_at: u64,
    pub device_id: String,
    pub status: String,
    pub reason_or_null: Option<String>,
    pub nonce_consumed_by_this_request: bool,
    pub selected_pcr_count: u32,
    pub replayed_event_count: u32,
    pub matched_rule_count: u32,
    pub failed_rule_count: u32,
    pub counter_committed: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuoteRow {
    pub request_id: String,
    pub attestation_key_id: String,
    pub attestation_key_fingerprint: String,
    pub magic_hex: String,
    pub attestation_type: String,
    pub qualified_signer_hex: String,
    pub extra_data_hex: String,
    pub clock: u64,
    pub reset_count: u32,
    pub restart_count: u32,
    pub safe: u8,
    pub firmware_version: u64,
    pub selected_pcrs: Vec<u32>,
    pub quoted_pcr_digest: String,
    pub computed_pcr_digest_or_null: Option<String>,
    pub signature_status: String,
    pub pcr_digest_status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventRow {
    pub request_id: String,
    pub event_log_id: String,
    pub event_seq: u32,
    pub pcr_index: u32,
    pub event_type: String,
    pub component: String,
    pub version: String,
    pub measurement_digest: String,
    pub policy_status: String,
    pub matched_rule_id_or_null: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PcrRow {
    pub request_id: String,
    pub pcr_index: u32,
    pub selected: bool,
    pub policy_required: bool,
    pub replayed_value: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReferenceMatchRow {
    pub request_id: String,
    pub policy_id: String,
    pub rule_id: String,
    pub rule_kind: String,
    pub matched_event_sequences: Vec<u32>,
    pub status: String,
    pub reason_or_null: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CounterRow {
    pub request_id: String,
    pub device_id: String,
    pub prior_reset_count: u32,
    pub prior_restart_count: u32,
    pub prior_clock: u64,
    pub quoted_reset_count: u32,
    pub quoted_restart_count: u32,
    pub quoted_clock: u64,
    pub safe: u8,
    pub status: String,
    pub committed: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NonceRow {
    pub nonce_id: String,
    pub device_id: String,
    pub issued_at: u64,
    pub expires_at: u64,
    pub initial_status: String,
    pub final_status: String,
    pub consumed_by_request_id_or_null: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConflictRow {
    pub request_id: String,
    pub conflict_type: String,
    pub subject: String,
    pub reason_code: String,
    pub related_values: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Summary {
    pub request_count: u32,
    pub accepted_request_count: u32,
    pub rejected_request_count: u32,
    pub quote_row_count: u32,
    pub event_row_count: u32,
    pub pcr_row_count: u32,
    pub reference_match_row_count: u32,
    pub matched_rule_count: u32,
    pub failed_rule_count: u32,
    pub initially_consumed_nonce_count: u32,
    pub finally_consumed_nonce_count: u32,
    pub counter_commit_count: u32,
    pub conflict_count: u32,
}

/// Placeholder types for candidates (not used by the non-solving starter path).
#[derive(Debug, Clone)]
pub struct ParsedQuote {
    pub magic: u32,
    pub attestation_type: u16,
    pub qualified_signer: Vec<u8>,
    pub extra_data: Vec<u8>,
    pub clock: u64,
    pub reset_count: u32,
    pub restart_count: u32,
    pub safe: u8,
    pub firmware_version: u64,
    pub selected_pcrs: Vec<u32>,
    pub pcr_digest: Vec<u8>,
}

#[derive(Debug, Clone)]
pub struct ParsedSignature {
    pub r: Vec<u8>,
    pub s: Vec<u8>,
}

#[derive(Debug, Clone)]
pub struct DeviceState {
    pub reset_count: u32,
    pub restart_count: u32,
    pub clock: u64,
}

#[derive(Debug, Clone)]
pub struct PcrState {
    pub values: [Vec<u8>; 4],
}

pub fn empty_report() -> Report {
    Report {
        request_rows: vec![],
        quote_rows: vec![],
        event_rows: vec![],
        pcr_rows: vec![],
        reference_match_rows: vec![],
        counter_rows: vec![],
        nonce_rows: vec![],
        conflict_rows: vec![],
        summary: Summary {
            request_count: 0,
            accepted_request_count: 0,
            rejected_request_count: 0,
            quote_row_count: 0,
            event_row_count: 0,
            pcr_row_count: 0,
            reference_match_row_count: 0,
            matched_rule_count: 0,
            failed_rule_count: 0,
            initially_consumed_nonce_count: 0,
            finally_consumed_nonce_count: 0,
            counter_commit_count: 0,
            conflict_count: 0,
        },
    }
}
