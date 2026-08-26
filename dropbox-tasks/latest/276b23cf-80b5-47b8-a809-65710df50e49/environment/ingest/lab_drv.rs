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
use crate::seg::wal::{
    commit_wal, lane_stamp_hex, load_wal, reconcile_truncated, route_plan_path, wal_path, LaneStamp,
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

    let jpath = wal_path();
    let prev_wal = load_wal(&jpath);
    let compile_generation = prev_wal.generation.saturating_add(1);

    let manifest_map: BTreeMap<String, String> = ctx
        .plan_manifest
        .iter()
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect();

    let prior_tail = if compile_generation > 1 {
        prev_wal.last_digest.clone()
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

    let mut path_report: Vec<Value> = Vec::new();
    for entry in &route_plan {
        let mux_ctx = pick_mux_context(
            &ctx,
            &entry.mux_id,
            &entry.probe_kind,
            chal_ctx.clone(),
            app_ctx.clone(),
        );
        let material_arm = pick_material_arm(&ctx, &entry.dispatch_id, &mux_ctx.slot);

        let local_material =
            select_material(&ctx, &material_arm, &primary, &secondary, &tertiary);
        let local_slot = if has_marker(&local_material, MARKER) {
            SLOT_SECONDARY
        } else if material_arm == SLOT_TERTIARY {
            SLOT_TERTIARY
        } else {
            SLOT_PRIMARY
        };
        let local_epoch = epoch_for_slot(local_slot, &epoch_map);

        let (remote_material, rewrite_count) =
            simulate_remote(&ctx, &entry.lane_id, &local_material, &primary);
        let remote_epoch = resolve_remote_epoch(
            &ctx,
            &material_arm,
            &remote_material,
            rewrite_count,
            &epoch_map,
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
