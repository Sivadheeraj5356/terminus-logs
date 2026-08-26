/// Compatibility shim — bridges the trace builder and the classifier.
///
/// Coordinates the output of b1 (compatibility trace) and c1 (error
/// classification) to produce a merged per-group result.  The xscope
/// engine calls into this module when assembling the final bundle.

use crate::b1::{build_trace, CompatTrace};
use crate::c1::{classify_record, classify_decode_error, ErrorClassification};
use crate::types::{CanonicalView, CompatState, LegacyRecord};

/// Full compatibility result for one sample group.
#[derive(Debug)]
pub struct GroupCompat {
    pub trace: Vec<CompatTrace>,
    pub errors: Vec<ErrorClassification>,
}

/// Build the compatibility result for a group, incorporating both the
/// paired-surface trace and the error classification for malformed records.
pub fn assess_group(
    bin_records: &[(LegacyRecord, u8)],  // (record, raw_status_byte)
    txt_views: &[CanonicalView],
    decode_errors: &[(u32, String)],     // (seq_hint, error_string)
) -> GroupCompat {
    // Project binary records into canonical views.
    let bin_views: Vec<CanonicalView> = bin_records
        .iter()
        .map(|(r, _)| CanonicalView::from(r.clone()))
        .collect();

    // Build the raw compatibility trace.
    let mut trace = build_trace(&bin_views, txt_views);

    // Classify each binary record for structural malformation.
    let mut errors: Vec<ErrorClassification> = Vec::new();
    for (rec, raw_status) in bin_records {
        if let Some(ec) = classify_record(rec, *raw_status) {
            // Upgrade the corresponding trace entry to Malformed.
            if let Some(entry) = trace.iter_mut().find(|t| t.seq_id == rec.seq_id) {
                entry.state = CompatState::Malformed;
                entry.diverged_fields.clear();
            }
            errors.push(ec);
        }
    }

    // Incorporate decode-level errors.
    for (seq_hint, err_str) in decode_errors {
        errors.push(classify_decode_error(*seq_hint, err_str));
    }

    GroupCompat { trace, errors }
}
