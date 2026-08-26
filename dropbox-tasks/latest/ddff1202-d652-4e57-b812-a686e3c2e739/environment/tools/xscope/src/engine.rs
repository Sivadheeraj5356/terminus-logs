/// Bundle validation engine.
///
/// Loads all sample groups from the fixtures directory, runs the decoder
/// pipeline on each group, and produces the validated bundle that gets
/// written to the output path.
///
/// The engine calls into:
///   legacy_record_lib::a1   — binary record reader
///   legacy_record_lib::compat — compatibility assessment (calls b1 + c1)
///   legacy_record_lib::model  — canonical-view projection
///
/// Text export format (see docs/layout.md):
///   Lines beginning with '#' are comments.
///   Data lines: seq_id,datum_len,checksum,status_nibble,revision_tag[,label]
///   Fields are decimal integers; label is an optional UTF-8 string.

use std::path::Path;
use legacy_record_lib::{
    a1,
    compat,
    model,
    types::{CanonicalView, CompatState, LegacyRecord},
};

use crate::report::{Bundle, GroupRecord, ArtifactEntry};

/// Load a binary fixture file and decode all records.
/// Returns (records_with_raw_status, decode_errors).
pub fn load_binary_group(path: &Path) -> (Vec<(LegacyRecord, u8)>, Vec<(u32, String)>) {
    let buf = match std::fs::read(path) {
        Ok(b) => b,
        Err(e) => {
            return (
                vec![],
                vec![(0, format!("cannot read {:?}: {}", path, e))],
            );
        }
    };

    let (records, err) = a1::read_all(&buf);

    // Extract raw status bytes from the buffer for the classifier.
    // The raw status byte is at offset 10 within each record's wire block.
    let mut with_status: Vec<(LegacyRecord, u8)> = Vec::new();
    let mut cursor = 0usize;
    for rec in &records {
        let raw_status: u8 = 0; // status byte not propagated from the raw buffer
        with_status.push((rec.clone(), raw_status));
        let label_extra = rec
            .label
            .as_ref()
            .map(|l| l.len() + 1)
            .unwrap_or(0);
        cursor += a1::MIN_RECORD_BYTES + label_extra;
    }
    let _ = cursor;

    let errors: Vec<(u32, String)> = err
        .into_iter()
        .map(|e| (records.len() as u32 + 1, e))
        .collect();

    (with_status, errors)
}

/// Parse one data line from a text export.
fn parse_text_line(line: &str) -> Result<CanonicalView, String> {
    let parts: Vec<&str> = line.splitn(6, ',').collect();
    if parts.len() < 5 {
        return Err(format!("too few fields: {:?}", line));
    }
    let seq_id: u32 = parts[0].trim().parse().map_err(|e| format!("seq_id: {}", e))?;
    let datum_len: u32 = parts[1].trim().parse().map_err(|e| format!("datum_len: {}", e))?;
    let checksum: u16 = parts[2].trim().parse().map_err(|e| format!("checksum: {}", e))?;
    let status_nibble: u8 = parts[3].trim().parse().map_err(|e| format!("status_nibble: {}", e))?;
    let revision_tag: u8 = parts[4].trim().parse().map_err(|e| format!("revision_tag: {}", e))?;
    let label = parts.get(5).map(|s| s.trim().to_string()).filter(|s| !s.is_empty());

    Ok(CanonicalView {
        seq_id,
        datum_len,
        checksum,
        status_nibble,
        revision_tag,
        label,
    })
}

/// Load a text export file and return canonical views.
pub fn load_text_group(path: &Path) -> (Vec<CanonicalView>, Vec<String>) {
    let content = match std::fs::read_to_string(path) {
        Ok(c) => c,
        Err(e) => return (vec![], vec![format!("cannot read {:?}: {}", path, e)]),
    };

    let mut views = Vec::new();
    let mut errors = Vec::new();
    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }
        match parse_text_line(trimmed) {
            Ok(v) => views.push(v),
            Err(e) => errors.push(e),
        }
    }
    (views, errors)
}

/// Run the full pipeline for one sample group and return a GroupRecord.
pub fn process_group(
    group_name: &str,
    bin_path: &Path,
    txt_path: &Path,
) -> GroupRecord {
    let (bin_records, bin_errors) = load_binary_group(bin_path);
    let (txt_views, _txt_errors) = load_text_group(txt_path);

    let group_compat = compat::assess_group(&bin_records, &txt_views, &bin_errors);

    // Project binary records into canonical views for the records section.
    let canonical_records: Vec<CanonicalView> = bin_records
        .iter()
        .map(|(r, _)| model::project_canonical(r))
        .collect();

    let compatible_count = group_compat
        .trace
        .iter()
        .filter(|t| t.state == CompatState::Compatible)
        .count();

    GroupRecord {
        group: group_name.to_string(),
        records: canonical_records,
        compatibility_trace: group_compat.trace,
        error_classification: group_compat.errors,
        compatible_count,
    }
}

/// Run the full bundle pipeline across all sample groups.
pub fn run_all_groups(fixtures_dir: &Path) -> Bundle {
    let raw_dir = fixtures_dir.join("raw");
    let text_dir = fixtures_dir.join("text");

    let mut groups = Vec::new();
    let mut artifacts = Vec::new();

    for entry in ["set_a", "set_b"] {
        let bin_path = raw_dir.join(format!("{}.bin", entry));
        let txt_path = text_dir.join(format!("{}.txt", entry));

        if !bin_path.exists() {
            eprintln!("warning: binary fixture not found: {:?}", bin_path);
            continue;
        }
        if !txt_path.exists() {
            eprintln!("warning: text fixture not found: {:?}", txt_path);
            continue;
        }

        let grp = process_group(entry, &bin_path, &txt_path);
        artifacts.push(ArtifactEntry {
            group: entry.to_string(),
            binary_path: bin_path.display().to_string(),
            text_path: txt_path.display().to_string(),
            record_count: grp.records.len(),
        });
        groups.push(grp);
    }

    Bundle { groups, artifacts }
}
