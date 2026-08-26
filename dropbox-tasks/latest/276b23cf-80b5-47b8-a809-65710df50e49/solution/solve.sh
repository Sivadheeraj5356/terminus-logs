#!/usr/bin/env bash
set -euo pipefail

cat > /app/environment/r3/r3_compile.rs <<'RSEOF'
use std::collections::BTreeMap;

use crate::ingest::lab_ctx::{LabCtx, SlotCtx};
use crate::ingest::lane_k2::pick_mux_context;
use crate::ingest::lane_p9::pick_material_arm;
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
    policy_rows: &[BTreeMap<String, String>],
) -> Vec<RoutePlanEntry> {
    let mut policy_map: BTreeMap<(String, String, String), (u32, String, String)> =
        BTreeMap::new();
    for row in policy_rows {
        let key = (
            row.get("host_id").cloned().unwrap_or_default(),
            row.get("lane_id").cloned().unwrap_or_default(),
            row.get("cohort_label").cloned().unwrap_or_default(),
        );
        let plan_index = row
            .get("plan_index")
            .and_then(|v| v.parse().ok())
            .unwrap_or(0);
        let negotiation_class = row
            .get("negotiation_class")
            .cloned()
            .unwrap_or_else(|| "challenge".to_string());
        let dispatch_id = row
            .get("dispatch_id")
            .cloned()
            .unwrap_or_else(|| "mux".to_string());
        policy_map.insert(key, (plan_index, negotiation_class, dispatch_id));
    }

    let mut entries: Vec<RoutePlanEntry> = Vec::new();
    for row in layout_rows {
        let key = (
            row.get("host_id").cloned().unwrap_or_default(),
            row.get("lane_id").cloned().unwrap_or_default(),
            row.get("cohort_label").cloned().unwrap_or_default(),
        );
        let (plan_index, negotiation_class, dispatch_id) = policy_map
            .get(&key)
            .cloned()
            .unwrap_or((0, "challenge".to_string(), "mux".to_string()));
        entries.push(RoutePlanEntry {
            host_id: key.0.clone(),
            lane_id: key.1.clone(),
            cohort_label: key.2.clone(),
            mux_id: row.get("mux_id").cloned().unwrap_or_default(),
            probe_kind: row.get("probe_kind").cloned().unwrap_or_default(),
            plan_index,
            negotiation_class,
            dispatch_id,
        });
    }
    entries.sort_by_key(|entry| entry.plan_index);
    entries
}

fn field_value(
    entry: &RoutePlanEntry,
    field: &str,
    mux_arm: &str,
    material_arm: &str,
) -> String {
    match field {
        "plan_index" => entry.plan_index.to_string(),
        "host_id" => entry.host_id.clone(),
        "lane_id" => entry.lane_id.clone(),
        "cohort_label" => entry.cohort_label.clone(),
        "negotiation_class" => entry.negotiation_class.clone(),
        "mux_arm" => mux_arm.to_string(),
        "material_arm" => material_arm.to_string(),
        _ => String::new(),
    }
}

pub fn hash_route_plan(
    entries: &[RoutePlanEntry],
    manifest: &BTreeMap<String, String>,
    compile_generation: u32,
    policy_revision: &str,
    prior_digest: &str,
    ctx: &LabCtx,
    chal_ctx: SlotCtx,
    app_ctx: SlotCtx,
) -> String {
    let fields: Vec<&str> = manifest
        .get("fields")
        .map(|s| s.split(',').collect())
        .unwrap_or_default();
    let sep = manifest.get("field_sep").map(|s| s.as_str()).unwrap_or("|");
    let join = manifest.get("body_join").map(|s| s.as_str()).unwrap_or("\n");
    let mut lines: Vec<String> = Vec::new();
    for entry in entries {
        let mux_ctx = pick_mux_context(
            ctx,
            &entry.mux_id,
            &entry.probe_kind,
            chal_ctx.clone(),
            app_ctx.clone(),
        );
        let material_arm = pick_material_arm(ctx, &entry.dispatch_id, &mux_ctx.slot);
        let parts: Vec<String> = fields
            .iter()
            .map(|f| field_value(entry, f, &mux_ctx.slot, &material_arm))
            .collect();
        lines.push(parts.join(sep));
    }
    let mut body = lines.join(join);
    let min_gen: u32 = manifest
        .get("prior_min_generation")
        .and_then(|s| s.parse().ok())
        .unwrap_or(2);
    for step in manifest
        .get("bind_sequence")
        .map(|s| s.as_str())
        .unwrap_or("body")
        .split(',')
    {
        match step.trim() {
            "body" => {}
            "revision" => {
                let rev_sep = manifest
                    .get("revision_sep")
                    .map(|s| s.as_str())
                    .unwrap_or("|");
                body = format!("{body}{rev_sep}{policy_revision}");
            }
            "prior" if compile_generation >= min_gen => {
                let prior_sep = manifest
                    .get("prior_sep")
                    .map(|s| s.as_str())
                    .unwrap_or("|");
                body = format!("{body}{prior_sep}{prior_digest}");
            }
            "generation" => {
                let gen_sep = manifest
                    .get("generation_sep")
                    .map(|s| s.as_str())
                    .unwrap_or("|");
                body = format!("{body}{gen_sep}{compile_generation}");
            }
            _ => {}
        }
    }
    sha256_hex(body.as_bytes())
}

RSEOF

cat > /app/environment/n2/n2_alpn.rs <<'RSEOF'
use crate::ingest::lab_ctx::LabCtx;
use crate::shared::tls_codec::{has_marker, negotiate_alpn};

pub fn resolve_alpn(
    ctx: &LabCtx,
    negotiation_class: &str,
    material: &[u8],
    rewrite_count: u32,
) -> u32 {
    let rules = &ctx.alpn_rules;
    if rules.get("retain_challenge_on_retain_local").map(|s| s.as_str()) == Some("true")
        && rewrite_count > 0
        && has_marker(material, &ctx.marker)
    {
        if negotiation_class == rules.get("app_class").map(|s| s.as_str()).unwrap_or("app") {
            return ctx.alpn_codes.get("app_default").copied().unwrap_or(0);
        }
        return ctx.alpn_codes.get("challenge").copied().unwrap_or(0);
    }
    if rules.get("strip_alpn_without_marker").map(|s| s.as_str()) == Some("true")
        && rewrite_count > 0
        && !has_marker(material, &ctx.marker)
    {
        return ctx.alpn_codes.get("stripped").copied().unwrap_or(0);
    }
    negotiate_alpn(
        negotiation_class,
        material,
        &ctx.marker,
        rewrite_count,
        &ctx.alpn_codes,
    )
}

RSEOF

cat > /app/environment/n7/n7_seal.rs <<'RSEOF'
use std::fs;

use serde_json::Value;

use crate::ingest::lab_ctx::LabCtx;
use crate::seg::wal::route_plan_path;
use crate::shared::tls_codec::sha256_hex;

fn compact_json_value(value: &Value) -> String {
    match value {
        Value::Object(map) => {
            let mut keys: Vec<&str> = map.keys().map(|k| k.as_str()).collect();
            keys.sort_unstable();
            let inner: Vec<String> = keys
                .into_iter()
                .map(|k| format!("\"{}\":{}", k, compact_json_value(&map[k])))
                .collect();
            format!("{{{}}}", inner.join(","))
        }
        Value::Array(items) => {
            let inner: Vec<String> = items.iter().map(compact_json_value).collect();
            format!("[{}]", inner.join(","))
        }
        Value::String(s) => serde_json::to_string(s).unwrap_or_else(|_| "\"\"".into()),
        Value::Number(n) => n.to_string(),
        Value::Bool(b) => b.to_string(),
        Value::Null => "null".into(),
    }
}

pub fn apply_seal_manifest(ctx: &LabCtx, rows: &[Value]) -> String {
    let raw = fs::read_to_string(route_plan_path()).unwrap_or_default();
    let cached = serde_json::from_str::<Value>(&raw).unwrap_or(Value::Null);
    let plan_hash = cached
        .get("plan_hash")
        .and_then(|h| h.as_str())
        .unwrap_or("");
    let compile_generation = cached
        .get("compile_generation")
        .and_then(|g| g.as_u64())
        .unwrap_or(0) as u32;
    let seal = &ctx.seal_manifest;
    let prefix_sep = seal.get("prefix_sep").map(|s| s.as_str()).unwrap_or("|");
    let prefix_fields: Vec<&str> = seal
        .get("prefix_fields")
        .map(|s| s.split(',').collect())
        .unwrap_or_else(|| vec!["plan_hash"]);
    let mut parts: Vec<String> = Vec::new();
    for field in prefix_fields {
        match field.trim() {
            "plan_hash" => parts.push(plan_hash.to_string()),
            "compile_generation" => parts.push(compile_generation.to_string()),
            _ => {}
        }
    }
    let prefix = parts.join(prefix_sep);
    let row_body: String = rows.iter().map(compact_json_value).collect::<Vec<_>>().join(",");
    let layout = seal
        .get("body_layout")
        .map(|s| s.as_str())
        .unwrap_or("{prefix}|[{rows}]");
    let body = layout
        .replace("{prefix}", &prefix)
        .replace("{rows}", &row_body);
    sha256_hex(body.as_bytes())
}

RSEOF

cat > /app/environment/ingest/lane_n7.rs <<'RSEOF'
use serde_json::Value;

use crate::ingest::lab_ctx::LabCtx;
use crate::n7::n7_seal::apply_seal_manifest;

pub fn bind_observation_seal(ctx: &LabCtx, rows: &[Value]) -> String {
    apply_seal_manifest(ctx, rows)
}

RSEOF

cat > /app/environment/s6/s6_seal.rs <<'RSEOF'
use serde_json::Value;

use crate::ingest::lab_ctx::LabCtx;
use crate::ingest::lane_n7::bind_observation_seal;

pub fn seal_observation(ctx: &LabCtx, rows: &[Value]) -> String {
    bind_observation_seal(ctx, rows)
}

RSEOF

cat > /app/environment/ingest/lane_s6.rs <<'RSEOF'
use serde_json::Value;

use crate::ingest::lab_ctx::LabCtx;
use crate::s6::s6_seal::seal_observation;

pub fn seal_report(ctx: &LabCtx, rows: &[Value]) -> String {
    seal_observation(ctx, rows)
}

RSEOF

cat > /app/environment/h9/h9_bind.rs <<'RSEOF'
use std::collections::HashMap;

use crate::ingest::lab_ctx::LabCtx;
use crate::shared::key_w8::{SLOT_PRIMARY, SLOT_SECONDARY, SLOT_TERTIARY};
use crate::shared::tls_codec::{epoch_for_slot, has_marker};

pub fn bind_remote_epoch(
    ctx: &LabCtx,
    material_arm: &str,
    remote_material: &[u8],
    rewrite_count: u32,
    epoch_map: &HashMap<String, u32>,
) -> u32 {
    let slot = if has_marker(remote_material, &ctx.marker) {
        SLOT_SECONDARY
    } else if material_arm == SLOT_TERTIARY && rewrite_count == 0 {
        SLOT_TERTIARY
    } else {
        SLOT_PRIMARY
    };
    let mut epoch = epoch_for_slot(slot, epoch_map);
    if rewrite_count > 0 && !has_marker(remote_material, &ctx.marker) {
        let substituted = ctx
            .epoch_bind
            .get("strip_substituted_epoch")
            .map(|s| s.as_str())
            .unwrap_or(SLOT_PRIMARY);
        epoch = epoch_for_slot(substituted, epoch_map);
    }
    epoch
}

RSEOF

cat > /app/environment/k2/k2_mux.rs <<'RSEOF'
use crate::ingest::lab_ctx::{LabCtx, SlotCtx};

pub fn op_k7(
    ctx: &LabCtx,
    mux_id: &str,
    probe_kind: &str,
    frag_a: SlotCtx,
    frag_b: SlotCtx,
) -> SlotCtx {
    let rec = ctx.muxes.get(mux_id);
    let sni = rec
        .and_then(|r| r.get("sni_slot"))
        .map(|s| s.as_str())
        .unwrap_or("");
    if sni == "chal" || probe_kind == "chal" {
        return frag_a;
    }
    frag_b
}

RSEOF

cat > /app/environment/m4/m4_select.rs <<'RSEOF'
use crate::ingest::lab_ctx::LabCtx;

pub fn reconcile_m4(
    _ctx: &LabCtx,
    slot_id: &str,
    row_a: &[u8],
    row_b: &[u8],
    row_c: &[u8],
) -> Vec<u8> {
    match slot_id {
        "secondary" => row_b.to_vec(),
        "tertiary" => row_c.to_vec(),
        _ => row_a.to_vec(),
    }
}

RSEOF

cat > /app/environment/w8/w8_lane.rs <<'RSEOF'
use crate::ingest::lab_ctx::LabCtx;
use crate::shared::tls_codec::has_marker;

pub fn finalize_w8(ctx: &LabCtx, lane_id: &str, sink_a: &[u8], _sink_b: &[u8]) -> (Vec<u8>, u32) {
    let lane = ctx.lanes.get(lane_id);
    let sim_kind = lane
        .and_then(|l| l.get("sim_kind"))
        .map(|s| s.as_str())
        .unwrap_or("");
    let strip_count: u32 = ctx
        .strip_rules
        .get("strip_rewrite_count")
        .and_then(|s| s.parse().ok())
        .unwrap_or(1);
    let pass_count: u32 = ctx
        .strip_rules
        .get("pass_rewrite_count")
        .and_then(|s| s.parse().ok())
        .unwrap_or(0);
    if sim_kind == "strip" {
        if has_marker(sink_a, &ctx.marker) {
            return (sink_a.to_vec(), strip_count);
        }
        return (ctx.primary_bytes.clone(), strip_count);
    }
    (sink_a.to_vec(), pass_count)
}

RSEOF

cat > /app/environment/p9/p9_cohort.rs <<'RSEOF'
use crate::ingest::lab_ctx::LabCtx;

pub fn resolve_arm(ctx: &LabCtx, dispatch_id: &str, mux_slot: &str) -> String {
    let arm = ctx
        .arm_dispatch
        .get(dispatch_id)
        .map(|s| s.as_str())
        .unwrap_or("mux");
    if arm == "mux" {
        return mux_slot.to_string();
    }
    arm.to_string()
}

RSEOF

cat > /app/environment/seg/wal.rs <<'RSEOF'
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

use crate::shared::tls_codec::{observation_digest, sha256_hex};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LaneStamp {
    pub host_id: String,
    pub lane_id: String,
    pub cohort_label: String,
    pub stamp_hex: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RunWal {
    pub generation: u32,
    pub prior_digest: String,
    pub last_digest: String,
    pub plan_hash: String,
    pub lane_stamps: Vec<LaneStamp>,
    pub recovered: bool,
}

impl Default for RunWal {
    fn default() -> Self {
        Self {
            generation: 0,
            prior_digest: String::new(),
            last_digest: String::new(),
            plan_hash: String::new(),
            lane_stamps: Vec::new(),
            recovered: false,
        }
    }
}

pub fn digest_valid(d: &str) -> bool {
    d.len() == 64 && d.chars().all(|c| c.is_ascii_hexdigit())
}

pub fn wal_path() -> PathBuf {
    Path::new("/app/var/run_journal.json").to_path_buf()
}

pub fn route_plan_path() -> PathBuf {
    Path::new("/app/var/route_plan.json").to_path_buf()
}

pub fn ensure_var_dir() {
    let _ = std::fs::create_dir_all("/app/var");
}

pub fn load_wal(path: &Path) -> RunWal {
    let raw = match std::fs::read_to_string(path) {
        Ok(s) => s,
        Err(_) => return RunWal::default(),
    };
    match serde_json::from_str::<RunWal>(&raw) {
        Ok(j) => j,
        Err(_) => {
            let mut wal = RunWal {
                recovered: true,
                ..RunWal::default()
            };
            if let Some(generation) = scrape_json_u32(&raw, "generation") {
                wal.generation = generation;
            }
            if let Some(prior_digest) = scrape_json_string(&raw, "prior_digest") {
                wal.prior_digest = prior_digest;
            }
            if let Some(last_digest) = scrape_json_string(&raw, "last_digest") {
                wal.last_digest = last_digest;
            }
            if let Some(plan_hash) = scrape_json_string(&raw, "plan_hash") {
                wal.plan_hash = plan_hash;
            }
            wal
        }
    }
}

fn scrape_json_u32(raw: &str, key: &str) -> Option<u32> {
    let needle = format!("\"{key}\":");
    let start = raw.find(&needle)? + needle.len();
    let rest = raw[start..].trim_start();
    let end = rest
        .find(|c: char| !c.is_ascii_digit())
        .unwrap_or(rest.len());
    rest[..end].parse().ok()
}

fn scrape_json_string(raw: &str, key: &str) -> Option<String> {
    let needle = format!("\"{key}\":\"");
    let start = raw.find(&needle)? + needle.len();
    let rest = &raw[start..];
    if let Some(end) = rest.find('"') {
        Some(rest[..end].to_string())
    } else {
        Some(rest.to_string())
    }
}

pub fn lane_stamp_hex(
    host_id: &str,
    lane_id: &str,
    cohort_label: &str,
    rewrite_count: u32,
    fingerprint: &str,
) -> String {
    let body = format!(
        "{host_id}|{lane_id}|{cohort_label}|{rewrite_count}|{fingerprint}"
    );
    sha256_hex(body.as_bytes())
}

pub fn commit_wal(
    path: &Path,
    prev: &RunWal,
    lane_stamps: &[LaneStamp],
    observation_digest: &str,
    plan_hash: &str,
) -> RunWal {
    let next = RunWal {
        generation: prev.generation.saturating_add(1),
        prior_digest: prev.last_digest.clone(),
        last_digest: observation_digest.to_string(),
        plan_hash: plan_hash.to_string(),
        lane_stamps: lane_stamps.to_vec(),
        recovered: false,
    };
    let body = serde_json::to_string_pretty(&next).unwrap_or_else(|_| "{}".into());
    let _ = std::fs::write(path, format!("{body}\n"));
    next
}

pub fn wal_chain_digest(wal: &RunWal, observation_digest: &str) -> String {
    let stamp_body = serde_json::to_string(&wal.lane_stamps).unwrap_or_else(|_| "[]".into());
    let body = format!(
        "{}|{}|{}|{}|{}",
        wal.generation,
        wal.prior_digest,
        observation_digest,
        wal.plan_hash,
        stamp_body
    );
    sha256_hex(body.as_bytes())
}

pub fn reconcile_truncated(
    wal: &mut RunWal,
    rows: &[serde_json::Value],
    plan_hash: &str,
) {
    if !wal.recovered {
        return;
    }
    wal.plan_hash = plan_hash.to_string();
    wal.lane_stamps = rows
        .iter()
        .map(|row| LaneStamp {
            host_id: row["host_id"].as_str().unwrap_or("").to_string(),
            lane_id: row["lane_id"].as_str().unwrap_or("").to_string(),
            cohort_label: row["cohort_label"].as_str().unwrap_or("").to_string(),
            stamp_hex: lane_stamp_hex(
                row["host_id"].as_str().unwrap_or(""),
                row["lane_id"].as_str().unwrap_or(""),
                row["cohort_label"].as_str().unwrap_or(""),
                row["rewrite_count"].as_u64().unwrap_or(0) as u32,
                row["material_fingerprint"].as_str().unwrap_or(""),
            ),
        })
        .collect();
    wal.recovered = false;
}

pub fn digest_rows(rows: &[serde_json::Value]) -> String {
    observation_digest(rows)
}

RSEOF

cat > /app/environment/ingest/lab_drv.rs <<'RSEOF'
use std::collections::{BTreeMap, HashMap};
use std::path::Path;

use serde_json::{json, Value};

use crate::ingest::lab_ctx::{LabCtx, SlotCtx};
use crate::ingest::lane_h9::resolve_remote_epoch;
use crate::ingest::lane_k2::pick_mux_context;
use crate::ingest::lane_n2::pick_alpn_code;
use crate::ingest::lane_m4::select_material;
use crate::ingest::lane_p9::pick_material_arm;
use crate::ingest::lane_r3::compile_route_plan;
use crate::ingest::lane_s6::seal_report;
use crate::ingest::lane_w8::simulate_remote;
use crate::ingest::layout_load::{
    dispatch_to_map, lanes_to_maps, load_alpn_codes, load_arm_dispatch, load_epoch_map, load_lanes,
    load_muxes, load_plan_manifest, load_policy, load_policy_revision, load_epoch_bind,
    load_seal_manifest, load_alpn_rules, load_rows, load_strip_rules, load_wal_manifest,
    rows_to_maps,
};
use crate::k2::aux_meter::socket_buffer_depth;
use crate::m4::stamp_echo::stamp_table_version;
use crate::p9::cohort_meter::cohort_table_revision;
use crate::r3::plan_meter::policy_revision_counter;
use crate::s6::seal_meter::seal_table_revision;
use crate::r3::r3_compile::RoutePlanEntry;
use crate::seg::wal::{
    commit_wal, digest_valid, lane_stamp_hex, load_wal, reconcile_truncated, route_plan_path,
    wal_path, LaneStamp,
};
use crate::shared::key_w8::{SLOT_PRIMARY, SLOT_SECONDARY, SLOT_TERTIARY};
use crate::shared::tls_codec::{
    epoch_for_slot, has_marker, read_bytes, sha256_hex,
};

const MARKER: &str = "TLS-LAB-01";

fn telemetry_probe() {
    let _ = socket_buffer_depth(0);
    let _ = stamp_table_version("mux");
    let _ = cohort_table_revision("layout_t9");
    let _ = policy_revision_counter("cohort_policy");
    let _ = seal_table_revision("observation");
}

fn persist_route_plan(plan_hash: &str, generation: u32) {
    let body = json!({
        "plan_hash": plan_hash,
        "compile_generation": generation,
    });
    let _ = std::fs::write(
        route_plan_path(),
        format!("{}\n", serde_json::to_string_pretty(&body).unwrap_or_else(|_| "{}".into())),
    );
}

fn build_path_report(
    ctx: &LabCtx,
    route_plan: &[RoutePlanEntry],
    chal_ctx: &SlotCtx,
    app_ctx: &SlotCtx,
    primary: &[u8],
    secondary: &[u8],
    tertiary: &[u8],
    epoch_map: &HashMap<String, u32>,
) -> Vec<Value> {
    let mut path_report: Vec<Value> = Vec::new();
    for entry in route_plan {
        let mux_ctx = pick_mux_context(
            ctx,
            &entry.mux_id,
            &entry.probe_kind,
            chal_ctx.clone(),
            app_ctx.clone(),
        );
        let material_arm = pick_material_arm(&ctx, &entry.dispatch_id, &mux_ctx.slot);

        let local_material =
            select_material(&ctx, &material_arm, primary, secondary, tertiary);
        let local_slot = if has_marker(&local_material, MARKER) {
            SLOT_SECONDARY
        } else if material_arm == SLOT_TERTIARY {
            SLOT_TERTIARY
        } else {
            SLOT_PRIMARY
        };
        let local_epoch = epoch_for_slot(local_slot, epoch_map);

        let (remote_material, rewrite_count) =
            simulate_remote(&ctx, &entry.lane_id, &local_material, primary);
        let remote_epoch = resolve_remote_epoch(
            &ctx,
            &material_arm,
            &remote_material,
            rewrite_count,
            epoch_map,
        );

        let alpn_code = pick_alpn_code(
            &ctx,
            &entry.negotiation_class,
            &remote_material,
            rewrite_count,
        );

        path_report.push(json!({
            "host_id": entry.host_id,
            "lane_id": entry.lane_id,
            "cohort_label": entry.cohort_label,
            "plan_index": entry.plan_index,
            "alpn_code": alpn_code,
            "material_fingerprint": sha256_hex(&remote_material),
            "local_sink_epoch": local_epoch,
            "remote_sink_epoch": remote_epoch,
            "rewrite_count": rewrite_count,
        }));
    }
    path_report
}

fn replay_last_digest(
    ctx: &LabCtx,
    layout_rows: &[BTreeMap<String, String>],
    policy_rows: &[BTreeMap<String, String>],
    manifest_map: &BTreeMap<String, String>,
    policy_revision: &str,
    target_generation: u32,
    chal_ctx: &SlotCtx,
    app_ctx: &SlotCtx,
    primary: &[u8],
    secondary: &[u8],
    tertiary: &[u8],
    epoch_map: &HashMap<String, u32>,
) -> String {
    let mut prior = String::new();
    let mut last_obs = String::new();
    for gen in 1..=target_generation {
        let (route_plan, plan_hash) = compile_route_plan(
            ctx,
            layout_rows,
            policy_rows,
            manifest_map,
            gen,
            policy_revision,
            &prior,
            chal_ctx.clone(),
            app_ctx.clone(),
        );
        persist_route_plan(&plan_hash, gen);
        let path_report = build_path_report(
            ctx,
            &route_plan,
            chal_ctx,
            app_ctx,
            primary,
            secondary,
            tertiary,
            epoch_map,
        );
        last_obs = seal_report(ctx, &path_report);
        prior = last_obs.clone();
    }
    last_obs
}

pub fn build_report(env_root: &Path) -> (Value, crate::seg::wal::RunWal) {
    telemetry_probe();
    let data = env_root.join("data");
    let mux_rows = load_muxes(&data);
    let lane_rows = load_lanes(&data);
    let layout_rows = load_rows(&data);
    let policy_rows = load_policy(&data);
    let arm_rows = load_arm_dispatch(&data);
    let plan_manifest = load_plan_manifest(&data);
    let seal_manifest = load_seal_manifest(&data);
    let alpn_rules = load_alpn_rules(&data);
    let strip_rules = load_strip_rules(&data);
    let epoch_bind = load_epoch_bind(&data);
    let _wal_manifest = load_wal_manifest(&data);
    let policy_revision = load_policy_revision(&data);

    let muxes = rows_to_maps(&mux_rows);
    let lanes = lanes_to_maps(&lane_rows);
    let arm_dispatch = dispatch_to_map(&arm_rows);

    let primary = read_bytes(env_root, "data/pem_w8/primary.pem");
    let secondary = read_bytes(env_root, "data/pem_w8/secondary.pem");
    let tertiary = read_bytes(env_root, "data/pem_w8/tertiary.pem");

    let epoch_map = load_epoch_map(&data);
    let alpn_codes = load_alpn_codes(&data);

    let ctx = LabCtx {
        muxes,
        lanes,
        arm_dispatch,
        strip_rules,
        plan_manifest,
        seal_manifest,
        alpn_rules,
        epoch_bind,
        policy_revision: policy_revision.clone(),
        marker: MARKER.to_string(),
        primary_bytes: primary.clone(),
        epoch_map: epoch_map.clone(),
        alpn_codes: alpn_codes.clone(),
    };

    let chal_ctx = SlotCtx {
        slot: SLOT_SECONDARY.to_string(),
        kind: "chal".to_string(),
    };
    let app_ctx = SlotCtx {
        slot: SLOT_PRIMARY.to_string(),
        kind: "app".to_string(),
    };

    let manifest_map: BTreeMap<String, String> = ctx
        .plan_manifest
        .iter()
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect();

    let jpath = wal_path();
    let prev_wal = load_wal(&jpath);
    let compile_generation = prev_wal.generation.saturating_add(1);

    let prior_tail = if compile_generation > 1 {
        if prev_wal.recovered
            && prev_wal.generation > 0
            && !digest_valid(&prev_wal.last_digest)
        {
            replay_last_digest(
                &ctx,
                &layout_rows,
                &policy_rows,
                &manifest_map,
                &policy_revision,
                prev_wal.generation,
                &chal_ctx,
                &app_ctx,
                &primary,
                &secondary,
                &tertiary,
                &epoch_map,
            )
        } else {
            prev_wal.last_digest.clone()
        }
    } else {
        String::new()
    };

    let (route_plan, plan_hash) = compile_route_plan(
        &ctx,
        &layout_rows,
        &policy_rows,
        &manifest_map,
        compile_generation,
        &policy_revision,
        &prior_tail,
        chal_ctx.clone(),
        app_ctx.clone(),
    );

    persist_route_plan(&plan_hash, compile_generation);

    let path_report = build_path_report(
        &ctx,
        &route_plan,
        &chal_ctx,
        &app_ctx,
        &primary,
        &secondary,
        &tertiary,
        &epoch_map,
    );

    let obs_digest = seal_report(&ctx, &path_report);
    let lane_stamps: Vec<LaneStamp> = path_report
        .iter()
        .map(|row| LaneStamp {
            host_id: row["host_id"].as_str().unwrap_or("").to_string(),
            lane_id: row["lane_id"].as_str().unwrap_or("").to_string(),
            cohort_label: row["cohort_label"].as_str().unwrap_or("").to_string(),
            stamp_hex: lane_stamp_hex(
                row["host_id"].as_str().unwrap_or(""),
                row["lane_id"].as_str().unwrap_or(""),
                row["cohort_label"].as_str().unwrap_or(""),
                row["rewrite_count"].as_u64().unwrap_or(0) as u32,
                row["material_fingerprint"].as_str().unwrap_or(""),
            ),
        })
        .collect();

    let mut prev = load_wal(&jpath);
    if prev.recovered && prev.generation > 0 && !digest_valid(&prev.last_digest) {
        prev.last_digest = prior_tail.clone();
    }
    reconcile_truncated(&mut prev, &path_report, &plan_hash);
    let wal = commit_wal(&jpath, &prev, &lane_stamps, &obs_digest, &plan_hash);

    let report = json!({
        "observation_digest": obs_digest,
        "plan_hash": plan_hash,
        "journal_generation": wal.generation,
        "prior_digest": wal.prior_digest,
        "journal_chain_digest": crate::seg::wal::wal_chain_digest(&wal, &obs_digest),
        "path_report": path_report,
    });
    (report, wal)
}

RSEOF

/app/environment/scripts/rebuild_pathlab.sh
/app/bin/run_lab
