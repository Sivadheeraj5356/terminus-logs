use crate::ingest::lab_ctx::LabCtx;
use crate::m4::m4_select::reconcile_m4;

pub fn select_material(
    ctx: &LabCtx,
    slot_id: &str,
    row_a: &[u8],
    row_b: &[u8],
    row_c: &[u8],
) -> Vec<u8> {
    reconcile_m4(ctx, slot_id, row_a, row_b, row_c)
}
