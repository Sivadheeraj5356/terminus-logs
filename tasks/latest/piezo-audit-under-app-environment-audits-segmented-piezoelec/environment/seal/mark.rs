use sha2::{Digest, Sha256};

use crate::types::{ProfileRevision, ReadingRow, SourceProvenance};

fn json_string(value: &str) -> String {
    serde_json::to_string(value).expect("digest string must serialize")
}

fn json_float(value: f64) -> String {
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

pub fn resonance_seal(
    family_id: &str,
    chip_id: &str,
    profile_id: &str,
    profile_graph_hash: &str,
    as_of_date: &str,
    input_fingerprint: &str,
    branch_generation: u32,
    _lineage: &[ProfileRevision],
    _provenance: &[SourceProvenance],
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
    body.push_str(r#","reading_count":"#);
    body.push_str(&rows.len().to_string());
    body.push_str(r#","rows":["#);
    for (index, row) in rows.iter().enumerate() {
        if index > 0 {
            body.push(',');
        }
        body.push('{');
        body.push_str(r#""line_index":"#);
        body.push_str(&row.line_index.to_string());
        body.push_str(r#","ppm_pull":"#);
        body.push_str(&json_float(row.ppm_pull));
        body.push('}');
    }
    body.push_str("]}");
    let _ = (
        profile_graph_hash,
        as_of_date,
        input_fingerprint,
        branch_generation,
    );
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
    body.push_str(r#","batch_generation":"#);
    body.push_str(&batch_generation.to_string());
    body.push_str(r#","family_digests":["#);
    for (index, digest) in family_digests.iter().enumerate() {
        if index > 0 {
            body.push(',');
        }
        body.push_str(&json_string(digest));
    }
    body.push_str("]}");
    let _ = (profile_graph_hash, family_count);
    format!("sha256:{}", hex::encode(Sha256::digest(body.as_bytes())))
}
