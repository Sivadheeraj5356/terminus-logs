use crate::ingest::lab_ctx::{LabCtx, SlotCtx};
use crate::k2::k2_mux::op_k7;

pub fn pick_mux_context(
    ctx: &LabCtx,
    mux_id: &str,
    probe_kind: &str,
    chal_ctx: SlotCtx,
    app_ctx: SlotCtx,
) -> SlotCtx {
    op_k7(ctx, mux_id, probe_kind, chal_ctx, app_ctx)
}
