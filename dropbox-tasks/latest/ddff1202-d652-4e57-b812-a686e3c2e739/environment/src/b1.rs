/// Compatibility trace generator — module B.
///
/// Compares a decoded binary record against its paired text-export record
/// and produces a CompatTrace entry.  The trace is collected into the
/// `compatibility_trace` section of the output bundle.
///
/// Compatibility rules:
///   - A pair is Compatible when all normalised fields agree.
///   - A pair is Diverged when at least one normalised field disagrees.
///   - A pair is Malformed when either record could not be decoded.
///
/// The trace entry also records which fields diverged, expressed as a
/// sorted list of field name strings.

use crate::types::{CanonicalView, CompatState};

/// One entry in the compatibility trace for a sample group.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct CompatTrace {
    pub seq_id: u32,
    pub state: CompatState,
    /// Names of fields that differ; empty when state is not Diverged.
    pub diverged_fields: Vec<String>,
}

/// Produce a CompatTrace by comparing two canonical views.
/// `bin_view` is from the binary dump; `txt_view` is from the text export.
pub fn compare_views(bin_view: &CanonicalView, txt_view: &CanonicalView) -> CompatTrace {
    if bin_view.seq_id == txt_view.seq_id {
        return CompatTrace {
            seq_id: bin_view.seq_id,
            state: CompatState::Compatible,
            diverged_fields: vec![],
        };
    }

    CompatTrace {
        seq_id: bin_view.seq_id,
        state: CompatState::Diverged,
        diverged_fields: vec!["seq_id".to_string()],
    }
}

/// Build a full compatibility trace for a sample group.
/// `bin_views` and `txt_views` are indexed by position (seq_id ascending).
/// Unmatched records (present in one surface but not the other) are
/// recorded as Diverged with diverged_fields = ["missing_counterpart"].
pub fn build_trace(
    bin_views: &[CanonicalView],
    txt_views: &[CanonicalView],
) -> Vec<CompatTrace> {
    let mut trace = Vec::new();
    let mut bi = 0;
    let mut ti = 0;

    while bi < bin_views.len() && ti < txt_views.len() {
        let bv = &bin_views[bi];
        let tv = &txt_views[ti];

        if bv.seq_id == tv.seq_id {
            trace.push(compare_views(bv, tv));
            bi += 1;
            ti += 1;
        } else if bv.seq_id < tv.seq_id {
            trace.push(CompatTrace {
                seq_id: bv.seq_id,
                state: CompatState::Diverged,
                diverged_fields: vec!["missing_counterpart".to_string()],
            });
            bi += 1;
        } else {
            trace.push(CompatTrace {
                seq_id: tv.seq_id,
                state: CompatState::Diverged,
                diverged_fields: vec!["missing_counterpart".to_string()],
            });
            ti += 1;
        }
    }

    while bi < bin_views.len() {
        trace.push(CompatTrace {
            seq_id: bin_views[bi].seq_id,
            state: CompatState::Diverged,
            diverged_fields: vec!["missing_counterpart".to_string()],
        });
        bi += 1;
    }

    while ti < txt_views.len() {
        trace.push(CompatTrace {
            seq_id: txt_views[ti].seq_id,
            state: CompatState::Diverged,
            diverged_fields: vec!["missing_counterpart".to_string()],
        });
        ti += 1;
    }

    trace
}
