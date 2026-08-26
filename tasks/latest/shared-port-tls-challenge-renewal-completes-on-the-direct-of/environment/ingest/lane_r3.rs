use std::collections::BTreeMap;

use crate::ingest::lab_ctx::{LabCtx, SlotCtx};
use crate::r3::r3_compile::{build_route_plan, hash_route_plan, RoutePlanEntry};

pub fn compile_route_plan(
    ctx: &LabCtx,
    layout_rows: &[BTreeMap<String, String>],
    policy_rows: &[BTreeMap<String, String>],
    manifest: &BTreeMap<String, String>,
    compile_generation: u32,
    policy_revision: &str,
    prior_digest: &str,
    chal_ctx: SlotCtx,
    app_ctx: SlotCtx,
) -> (Vec<RoutePlanEntry>, String) {
    let plan = build_route_plan(layout_rows, policy_rows);
    let hash = hash_route_plan(
        &plan,
        manifest,
        compile_generation,
        policy_revision,
        prior_digest,
        ctx,
        chal_ctx,
        app_ctx,
    );
    (plan, hash)
}
