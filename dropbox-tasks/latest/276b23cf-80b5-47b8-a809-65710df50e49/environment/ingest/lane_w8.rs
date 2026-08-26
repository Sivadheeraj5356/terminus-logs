use crate::ingest::lab_ctx::LabCtx;
use crate::w8::w8_lane::finalize_w8;

pub fn simulate_remote(
    ctx: &LabCtx,
    lane_id: &str,
    local_bytes: &[u8],
    aux_bytes: &[u8],
) -> (Vec<u8>, u32) {
    finalize_w8(ctx, lane_id, local_bytes, aux_bytes)
}
