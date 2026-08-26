use crate::ingest::lab_ctx::LabCtx;

pub fn resolve_arm(
    _ctx: &LabCtx,
    _dispatch_id: &str,
    mux_slot: &str,
) -> String {
    mux_slot.to_string()
}
