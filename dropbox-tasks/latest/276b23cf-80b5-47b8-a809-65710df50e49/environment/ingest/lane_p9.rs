use crate::ingest::lab_ctx::LabCtx;
use crate::p9::p9_cohort::resolve_arm;

pub fn pick_material_arm(
    ctx: &LabCtx,
    dispatch_id: &str,
    mux_slot: &str,
) -> String {
    resolve_arm(ctx, dispatch_id, mux_slot)
}
