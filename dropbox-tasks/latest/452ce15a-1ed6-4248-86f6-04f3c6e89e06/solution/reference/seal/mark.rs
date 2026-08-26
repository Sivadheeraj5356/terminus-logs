use sha2::{Digest, Sha256};

use crate::types::{ProfileRevision, ReadingRow, SourceProvenance};

fn json_string(value: &str) -> String {
    serde_json::to_string(value).expect("digest string must serialize")
}

fn lineage_json_float(value: f64) -> String {
    if value == 0.0 {
        return "0.0".to_string();
    }
    let token = crate::calib::profile::hash_float_token(value);
    if token.contains('.') {
        token
    } else {
        format!("{token}.0")
    }
}

fn row_json_float(value: f64) -> String {
    if value == 0.0 {
        return "0.0".to_string();
    }
    let token = crate::calib::profile::digest_float_token(value);
    if token.contains('.') {
        token
    } else {
        format!("{token}.0")
    }
}

fn json_string_array(values: &[String]) -> String {
    let mut body = String::from("[");
    for (index, value) in values.iter().enumerate() {
        if index > 0 {
            body.push(',');
        }
        body.push_str(&json_string(value));
    }
    body.push(']');
    body
}

pub fn resonance_seal(
    family_id: &str,
    chip_id: &str,
    profile_id: &str,
    profile_graph_hash: &str,
    as_of_date: &str,
    input_fingerprint: &str,
    branch_generation: u32,
    lineage: &[ProfileRevision],
    provenance: &[SourceProvenance],
    rows: &[ReadingRow],
) -> String {
    let mut body = String::new();
    body.push('{');
    body.push_str(r#""family_id":"#);
    body.push_str(&json_string(family_id));
    body.push_str(r#","chip_id":"#);
    body.push_str(&json_string(chip_id));
    body.push_str(r#","profile_id":"#);
    body.push_str(&json_string(profile_id));
    body.push_str(r#","profile_graph_hash":"#);
    body.push_str(&json_string(profile_graph_hash));
    body.push_str(r#","as_of_date":"#);
    body.push_str(&json_string(as_of_date));
    body.push_str(r#","input_fingerprint":"#);
    body.push_str(&json_string(input_fingerprint));
    body.push_str(r#","branch_generation":"#);
    body.push_str(&branch_generation.to_string());
    body.push_str(r#","reading_count":"#);
    body.push_str(&rows.len().to_string());
    body.push_str(r#","profile_lineage":["#);
    for (index, entry) in lineage.iter().enumerate() {
        if index > 0 {
            body.push(',');
        }
        body.push('{');
        body.push_str(r#""profile_id":"#);
        body.push_str(&json_string(&entry.profile_id));
        body.push_str(r#","effective_date":"#);
        body.push_str(&json_string(&entry.effective_date));
        body.push_str(r#","inherits":"#);
        body.push_str(&json_string(&entry.inherits));
        body.push_str(r#","alpha":"#);
        body.push_str(&lineage_json_float(entry.alpha));
        let nom = if entry.nominal_hz_override > 0.0 {
            entry.nominal_hz_override
        } else {
            0.0
        };
        body.push_str(r#","nominal_hz_override":"#);
        body.push_str(&lineage_json_float(nom));
        body.push_str(r#","deprecation_window_days":"#);
        body.push_str(&entry.deprecation_window_days.to_string());
        body.push('}');
    }
    body.push_str(r#"],"provenance":["#);
    for (index, entry) in provenance.iter().enumerate() {
        if index > 0 {
            body.push(',');
        }
        body.push('{');
        body.push_str(r#""path":"#);
        body.push_str(&json_string(&entry.path));
        body.push_str(r#","family_id":"#);
        body.push_str(&json_string(&entry.family_id));
        body.push_str(r#","chip_id":"#);
        body.push_str(&json_string(&entry.chip_id));
        body.push_str(r#","alias":"#);
        body.push_str(&json_string(&entry.alias));
        body.push_str(r#","profile_id":"#);
        body.push_str(&json_string(&entry.profile_id));
        body.push_str(r#","profile_effective_date":"#);
        body.push_str(&json_string(&entry.profile_effective_date));
        body.push_str(r#","profile_parent_effective_date":"#);
        body.push_str(&json_string(&entry.profile_parent_effective_date));
        body.push_str(r#","segment_ids":"#);
        body.push_str(&json_string_array(&entry.segment_ids));
        body.push_str(r#","reading_count":"#);
        body.push_str(&entry.reading_count.to_string());
        body.push_str(r#","source_digest":"#);
        body.push_str(&json_string(&entry.source_digest));
        body.push('}');
    }
    body.push_str(r#"],"rows":["#);
    for (index, row) in rows.iter().enumerate() {
        if index > 0 {
            body.push(',');
        }
        body.push('{');
        body.push_str(r#""line_index":"#);
        body.push_str(&row.line_index.to_string());
        body.push_str(r#","segment_id":"#);
        body.push_str(&json_string(&row.segment_id));
        body.push_str(r#","ppm_pull":"#);
        body.push_str(&row_json_float(row.ppm_pull));
        body.push_str(r#","temp_c":"#);
        body.push_str(&row_json_float(row.temp_c));
        body.push('}');
    }
    body.push_str("]}");
    format!("sha256:{}", hex::encode(Sha256::digest(body.as_bytes())))
}

pub fn batch_seal(
    schema_version: u32,
    as_of_date: &str,
    input_fingerprint: &str,
    profile_graph_hash: &str,
    batch_generation: u32,
    family_count: usize,
    family_digests: &[String],
) -> String {
    let mut body = String::new();
    body.push('{');
    body.push_str(r#""schema_version":"#);
    body.push_str(&schema_version.to_string());
    body.push_str(r#","as_of_date":"#);
    body.push_str(&json_string(as_of_date));
    body.push_str(r#","input_fingerprint":"#);
    body.push_str(&json_string(input_fingerprint));
    body.push_str(r#","profile_graph_hash":"#);
    body.push_str(&json_string(profile_graph_hash));
    body.push_str(r#","batch_generation":"#);
    body.push_str(&batch_generation.to_string());
    body.push_str(r#","family_count":"#);
    body.push_str(&family_count.to_string());
    body.push_str(r#","family_digests":["#);
    for (index, digest) in family_digests.iter().enumerate() {
        if index > 0 {
            body.push(',');
        }
        body.push_str(&json_string(digest));
    }
    body.push_str("]}");
    format!("sha256:{}", hex::encode(Sha256::digest(body.as_bytes())))
}
