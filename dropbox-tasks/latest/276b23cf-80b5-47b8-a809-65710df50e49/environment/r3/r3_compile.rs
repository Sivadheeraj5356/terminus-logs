use std::collections::BTreeMap;

use crate::shared::tls_codec::sha256_hex;

#[derive(Debug, Clone)]
pub struct RoutePlanEntry {
    pub host_id: String,
    pub lane_id: String,
    pub cohort_label: String,
    pub mux_id: String,
    pub probe_kind: String,
    pub plan_index: u32,
    pub negotiation_class: String,
    pub dispatch_id: String,
}

pub fn build_route_plan(
    layout_rows: &[BTreeMap<String, String>],
    _policy_rows: &[BTreeMap<String, String>],
) -> Vec<RoutePlanEntry> {
    layout_rows
        .iter()
        .enumerate()
        .map(|(idx, row)| RoutePlanEntry {
            host_id: row.get("host_id").cloned().unwrap_or_default(),
            lane_id: row.get("lane_id").cloned().unwrap_or_default(),
            cohort_label: row.get("cohort_label").cloned().unwrap_or_default(),
            mux_id: row.get("mux_id").cloned().unwrap_or_default(),
            probe_kind: row.get("probe_kind").cloned().unwrap_or_default(),
            plan_index: idx as u32,
            negotiation_class: "challenge".to_string(),
            dispatch_id: "mux".to_string(),
        })
        .collect()
}

fn field_value(
    entry: &RoutePlanEntry,
    field: &str,
    _mux_arm: &str,
    _material_arm: &str,
) -> String {
    match field {
        "plan_index" => entry.plan_index.to_string(),
        "host_id" => entry.host_id.clone(),
        "lane_id" => entry.lane_id.clone(),
        "cohort_label" => entry.cohort_label.clone(),
        "negotiation_class" => entry.negotiation_class.clone(),
        "mux_arm" => String::new(),
        "material_arm" => String::new(),
        _ => String::new(),
    }
}

pub fn hash_route_plan(
    entries: &[RoutePlanEntry],
    manifest: &BTreeMap<String, String>,
    compile_generation: u32,
    _policy_revision: &str,
    _prior_digest: &str,
    _ctx: &crate::ingest::lab_ctx::LabCtx,
    _chal_ctx: crate::ingest::lab_ctx::SlotCtx,
    _app_ctx: crate::ingest::lab_ctx::SlotCtx,
) -> String {
    let fields: Vec<&str> = manifest
        .get("fields")
        .map(|s| s.split(',').collect())
        .unwrap_or_default();
    let sep = manifest.get("field_sep").map(|s| s.as_str()).unwrap_or("|");
    let join = manifest.get("body_join").map(|s| s.as_str()).unwrap_or("\n");
    let mut lines: Vec<String> = Vec::new();
    for entry in entries {
        let parts: Vec<String> = fields
            .iter()
            .map(|f| field_value(entry, f, "", ""))
            .collect();
        lines.push(parts.join(sep));
    }
    let body = lines.join(join);
    let gen_sep = manifest
        .get("generation_sep")
        .map(|s| s.as_str())
        .unwrap_or("|");
    let preimage = format!("{body}{gen_sep}{compile_generation}");
    sha256_hex(preimage.as_bytes())
}
